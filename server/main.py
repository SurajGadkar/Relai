from time import time
from urllib import response
from openai import OpenAI
import os
import sqlite3
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import base64
import uuid
import json
import re

# --- Database & Folder Initialization ---
DATABASE_NAME = "database.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Grab the ngrok URL from Railway settings
# Fallback to localhost:11434 for when you work locally
tunnel_url = os.getenv("LLM_PUBLIC_URL", "http://localhost:1234")

def init_db():
    # Ensure the upload folder exists so the app doesn't crash on first upload
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Updated schema: matches your upload logic (image_path, tags)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS closet (
            id TEXT PRIMARY KEY, 
            image_path TEXT, 
            tags TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database initialized and tables created.")

# This runs when the server starts
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# --- Middleware ---
allowed_origins = [os.getenv("FRONTEND_URL", "http://localhost:5173")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- OpenAI Client (Local Ollama) ---
client = OpenAI(
    api_key="ollama", # Key is required but ignored by Ollama
    base_url=f"{tunnel_url}/v1",
)

# --- Endpoints ---

@app.get("/suggest")
async def suggest_outfit(weather: str, vibe: str):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, tags, image_path FROM closet")
    closet_items = [{"id": row[0], "description": row[1], "path": row[2]} for row in cursor.fetchall()]
    conn.close()

    if not closet_items:
        return {"outfit": [], "message": "Your closet is empty!"}

    closet_menu = "\n".join([f"ID {item['id']}: {item['description']}" for item in closet_items])

    prompt = f"""You are the best fashion advisor, taking the weather: {weather} and the vibe: {vibe} into consideration.
    Rules:
    1. Always suggest a complete outfit but within the given clothes.
    2. Consider the weather and vibe when suggesting an outfit.
    3. You have boundaries, you can only suggest outfits, if any prompts like weather, vibe or clothes are not making sense, or seems invalid
    do not take it into consideration and ask user to provide valid inputs only.
    4. Your output should be in a strict format, only outfit suggestion within the given clothes, no explanations or extra text.
    5. You can only suggest outfits using the clothes available in the closet, you cannot suggest any outfit that is not present in the closet.
    6. If the user provides invalid weather or vibe, ask them to provide valid inputs without suggesting an outfit.
    7. Complete outfit suggested should match appropraitely example, formal shirts cannot go with jeans or shorts, beachwear cannot go with formal shoes, etc.
    only casual shirts can go with shorts, jeans etc. shoes should match the outfit, for example, formal shoes cannot go with casual shirts and shorts, etc.
    8. 4. Format your response as a JSON object with a key "ids" containing a list of strings.
        Example: {{"ids": ["1", "5"]}}

    these are the clothes available: {closet_menu}.
    Suggest an outfit."""
    
    try:
        response = client.chat.completions.create(
            model="google/gemma-4-e4b",
            messages=[{"role": "user", "content": prompt}],
        )

        # 1. Clean the AI content (removes ```json and ```)
        content = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)

        if json_match:
            clean_json = json_match.group()
            data = json.loads(clean_json)
            
            # 2. Get the IDs exactly as they are (Strings for UUIDs)
            suggested_ids = data.get("ids", [])
            
            # 3. Filter the closet
            # We use 'str(item["id"])' to ensure we compare string-to-string
            final_outfit = [
                item for item in closet_items 
                if str(item["id"]) in [str(sid) for sid in suggested_ids]
            ]
            
            return {"outfit": final_outfit}
        else:
            raise ValueError("AI output did not contain valid JSON")

    except Exception as e:
        print(f"AI Error: {e}")
        return {"outfit": [], "error": "AI failed to generate a suggestion."}

@app.post("/upload")
async def upload_clothing_item(file: UploadFile = File(...)):
    # 1. Create unique filename to prevent overwrites
    item_id = str(uuid.uuid4())
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{item_id}.{file_extension}"
    file_location = os.path.join(UPLOAD_FOLDER, unique_filename)
    
    with open(file_location, "wb") as f:
        f.write(await file.read())
    
    # 2. Get AI to identify the clothing
    with open(file_location, "rb") as img_file:
        base64_image = base64.b64encode(img_file.read()).decode('utf-8')

    vision_response = client.chat.completions.create(
        model="google/gemma-4-e4b", 
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Identify this clothing item. Respond with proper indentification like color, style, dress format in words but identify the type like formal, casual, "
                "beach wear based on the image (e.g., 'Black Casual Slim Jeans, White Formal Shirt, Black Casual Trouser')."
                "Strictly needs to have Color, Style like casual, formal, beachwear etc., and dress format like jeans, shirt, t-shirt, trouser, skirt etc. in the response. and no extra text, only the identification."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }]
    )
    ai_tags = vision_response.choices[0].message.content
    
    # 3. Store ID, Path, and AI Tags in DB
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO closet (id, image_path, tags) VALUES (?, ?, ?)", 
                   (item_id, file_location, ai_tags))
    conn.commit()
    conn.close()

    return {"message": f"Successfully added id: {item_id} with tags: {ai_tags} to your closet!"}

@app.get("/items")
async def get_items():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Fetch as a list of dictionaries for easier frontend mapping
    cursor.execute("SELECT image_path, tags FROM closet ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [{"image_path": row[0], "tags": row[1]} for row in rows]