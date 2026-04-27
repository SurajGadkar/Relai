from time import time
from openai import OpenAI
import os
import sqlite3
import uuid
import json
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import base64
from typing import List 
from fastapi import BackgroundTasks, UploadFile, File, Form

# --- Config & Initialization ---
load_dotenv()

DATABASE_NAME = "database.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

cloudinary.config( 
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
    api_key = os.getenv("CLOUDINARY_API_KEY"), 
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure = True
)

# LLM URL logic
tunnel_url = os.getenv("LLM_PUBLIC_URL", "http://localhost:1234")
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row 
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS closet (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default_user',
        image_path TEXT,
        tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    if DATABASE_URL:
        cursor.execute(create_table_query)
    else:
        cursor.execute(create_table_query.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP"))

    conn.commit()
    cursor.close()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# --- Middleware ---
allowed_origins = [os.getenv("FRONTEND_URL", "http://localhost:5173"), "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# For serving local files (if still needed)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

client = OpenAI(
    api_key="ollama",
    base_url=f"{tunnel_url}/v1",
)

# --- Endpoints ---

@app.get("/suggest")
async def suggest_outfit(weather: str, vibe: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, tags, image_path FROM closet")
    rows = cursor.fetchall()
    
    closet_items = []
    for row in rows:
        if isinstance(row, dict):
            closet_items.append({"id": row['id'], "description": row['tags'], "path": row['image_path']})
        else:
            closet_items.append({"id": row[0], "description": row[1], "path": row[2]})
    
    cursor.close()
    conn.close()

    if not closet_items:
        return {"suggestions": [], "message": "Your closet is empty!"}

    closet_menu = "\n".join([f"ID {item['id']}: {item['description']}" for item in closet_items])

    # NOTE: I used double braces {{ }} for the JSON structure so Python's .format() doesn't break
    prompt = f"""You are a master fashion stylist. Weather: {weather}, Vibe: {vibe}.
    Rules:
    1. Only use provided IDs. 
    2. Provide 3 distinct outfit suggestions. 
    3. For each, provide a 'style_score' (1-10) and 'reasoning' (color theory, 60-30-10 rule).
    4. Return ONLY a JSON object in this format:
    5. Do not return any extra characters, explanations, or apologies. Strictly follow the format.
    {{
        "suggestions": [
            {{
                "rank": 1,
                "style_score": 9.2,
                "items": {{
                    "top": {{ "id": "ID_HERE", "label": "Name" }},
                    "bottom": {{ "id": "ID_HERE", "label": "Name" }},
                    "shoes": {{ "id": "ID_HERE", "label": "Name" }}
                }},
                "reasoning": "...",
                "logic": "60% color, 30% color, 10% color"
            }}
        ]
    }}

    Available Closet:
    {closet_menu}
    """
    
    try:
        response = client.chat.completions.create(
            model="google/gemma-4-e4b",
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)

        if json_match:
            data = json.loads(json_match.group())
            # We return the whole 'data' object now, not just a filtered list
            # Your React frontend will use the IDs inside 'suggestions' to find images
            return data 
        else:
            return {"suggestions": [], "error": "AI returned invalid format."}

    except Exception as e:
        print(f"AI Error: {e}")
        return {"suggestions": [], "error": str(e)}
    
    
async def process_ai_tags(item_id: str, base64_image: str):
    try:
        vision_response = client.chat.completions.create(
            model="google/gemma-4-e4b", 
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Identify this clothing item: Color, Style, Type. Max 5 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }]
        )
        ai_tags = vision_response.choices[0].message.content.strip()
        
        # Update the DB with the actual tags
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = "%s" if DATABASE_URL else "?"
        cursor.execute(
            f"UPDATE closet SET tags = {placeholder} WHERE id = {placeholder}",
            (ai_tags, item_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Background AI Error: {e}")


@app.post("/upload")
async def upload_clothing_items(
    background_tasks: BackgroundTasks, 
    files: List[UploadFile] = File(...), 
    user_id: str = Form("default_user")
):
    uploaded_results = []
    
    for file in files:
        # 1. Prepare for AI (Base64)
        file_content = await file.read()
        base64_image = base64.b64encode(file_content).decode('utf-8')
        await file.seek(0)

        # 2. Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(file.file)
        image_url = upload_result.get("secure_url") 

        # 3. Save to DB immediately with placeholder tags
        item_id = str(uuid.uuid4())
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = "%s" if DATABASE_URL else "?"
        
        query = f"INSERT INTO closet (id, user_id, image_path, tags) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})"
        cursor.execute(query, (item_id, user_id, image_url, "Processing AI tags..."))
        
        conn.commit()
        cursor.close()
        conn.close()

        # 4. Queue the AI task to run in the background
        background_tasks.add_task(process_ai_tags, item_id, base64_image)
        
        uploaded_results.append({"id": item_id, "url": image_url})

    return {"message": f"Successfully queued {len(files)} items", "items": uploaded_results}


@app.get("/items")
async def get_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, image_path, tags FROM closet ORDER BY id DESC")
    rows = cursor.fetchall()
    
    items = []
    for row in rows:
        if isinstance(row, dict):
            items.append(row)
        else:
            items.append({"id": row[0], "image_path": row[1], "tags": row[2]})
        
    cursor.close()
    conn.close()
    return items

# Placeholder for next step (Login)
# @app.post("/register")
# def register_user(user: dict):
#    pass