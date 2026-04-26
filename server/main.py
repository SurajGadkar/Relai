from openai import OpenAI
import os
import sqlite3
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# --- Database & Folder Initialization ---
DATABASE_NAME = "database.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    # Ensure the upload folder exists so the app doesn't crash on first upload
    
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Updated schema: matches your upload logic (image_path, tags)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS closet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- OpenAI Client (Local Ollama) ---
client = OpenAI(
    api_key="ollama", # Key is required but ignored by Ollama
    base_url="http://localhost:1234/v1",
)

# --- Endpoints ---

@app.get("/suggest")
async def suggest_outfit(weather: str, vibe: str):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT tags FROM closet")
    items = [row[0] for row in cursor.fetchall()]
    conn.close()


    if not items:
        return {"suggestion": "Your closet is empty! Upload some clothes first."}

    prompt = f"""You are the best fashion advisor, taking the weather: {weather} 
    and the  vibe: {vibe} into consideration.


    Rules : 
    1. Always suggest a complete outfit but within the given clothes.
    2. Consider the weather and vibe when suggesting an outfit.
    3. You have boundaries, you can only suggest outfits, if any prompts like weather, vibe or clothes are not making sense, or seems invalid
        do not take it into consideration and ask user to provide valid inputs only.
    4. Your output should be in a strict format, only outfit suggestion within the given clothes, no explanations or extra text.
    5. You can only suggest outfits using the clothes available in the closet, you cannot suggest any outfit that is not present in the closet.
    6. If the user provides invalid weather or vibe, ask them to provide valid inputs without suggesting an outfit.
    7. Complete outfit suggested should match appropraitely example, formal shirts cannot go with jeans or shorts, beachwear cannot go with formal shoes, etc.
     only casual shirts can go with shorts, jeans etc. shoes should match the outfit, for example, formal shoes cannot go with casual shirts and shorts, etc.

    these are the clothes available: {', '.join(items)}. Suggest an outfit."""
    
    response = client.chat.completions.create(
        model="google/gemma-4-e4b", 
        messages=[{"role": "user", "content": prompt}]
    )
    
    return {"suggestion": response.choices[0].message.content}

@app.post("/upload")
async def upload_clothing_item(file: UploadFile = File(...), tags: str = Form(...)):
    # Create unique filename to prevent overwrites
    file_location = os.path.join(UPLOAD_FOLDER, file.filename)
    
    with open(file_location, "wb") as f:
        f.write(await file.read())
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO closet (image_path, tags) VALUES (?, ?)", (file_location, tags))
    conn.commit()
    conn.close()
    
    return {"message": f"Successfully added {tags} to your closet!"}

@app.get("/items")
async def get_items():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Fetch as a list of dictionaries for easier frontend mapping
    cursor.execute("SELECT image_path, tags FROM closet ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [{"image_path": row[0], "tags": row[1]} for row in rows]