from time import time
from openai import OpenAI
import subprocess
import shlex
import tempfile
import os
import sqlite3
import uuid
import json
import re
import io
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, UploadFile, File, Form, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException, BackgroundTasks
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import base64
from typing import List, Optional
from datetime import datetime, timedelta
from rembg import remove
from PIL import Image
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from jose import JWTError, jwt

# --- Config & Initialization ---
load_dotenv()

DATABASE_NAME = "database.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

# Gemini AI config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("LLM_MODEL", "gemini-2.0-flash")
DATABASE_URL = os.getenv("DATABASE_URL")

# JWT Config
JWT_SECRET = os.getenv("JWT_SECRET", "relai-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30


# --- DB Helpers ---
def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def get_db():
    db = get_db_connection()
    try:
        yield db
    finally:
        db.close()


def get_placeholder():
    return "%s" if DATABASE_URL else "?"


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    create_users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        google_id TEXT UNIQUE,
        email TEXT,
        name TEXT,
        picture TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    create_closet_table = """
    CREATE TABLE IF NOT EXISTS closet (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default_user',
        image_path TEXT,
        tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_worn TIMESTAMP,
        is_available BOOLEAN DEFAULT TRUE
    );
    """

    if DATABASE_URL:
        cursor.execute(create_users_table)
        cursor.execute(create_closet_table)
    else:
        cursor.execute(
            create_users_table
            .replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        )
        cursor.execute(
            create_closet_table
            .replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")
            .replace("last_worn TIMESTAMP", "last_worn DATETIME")
        )

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
# SessionMiddleware is required by authlib for OAuth state management
app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET)

# Static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Gemini client via OpenAI-compatible endpoint (used as fallback / vision)
client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)


def call_gemini_cli(prompt: str, image_path: str = None) -> str:
    """Call Gemini via the CLI using your AI Pro subscription (OAuth).
    Optionally pass an image_path to enable vision analysis via @filepath syntax.
    Falls back to None on failure so callers can handle gracefully.
    """
    try:
        if image_path:
            # @filepath tells the CLI to include the file as multimodal context
            full_prompt = f"@{image_path} {prompt}"
        else:
            full_prompt = prompt

        command = f'gemini -m "gemini-2.5-flash" --yolo -p {shlex.quote(full_prompt)}'
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Gemini CLI error: {e.stderr}")
        return None
    except Exception as e:
        print(f"Gemini CLI general error: {e}")
        return None

# --- Google OAuth Setup ---
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# --- JWT Helpers ---
def create_jwt(google_id: str, email: str, name: str, picture: str) -> str:
    payload = {
        "sub": google_id,
        "email": email,
        "name": name,
        "picture": picture,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(authorization: Optional[str] = Header(None)):
    """FastAPI dependency — validates Bearer JWT.
    AUTH BYPASSED: always returns dev user. Re-enable by removing the bypass block.
    """
    # --- BYPASS: remove this block to enforce auth ---
    return {"sub": "dev_user", "email": "dev@relai.local", "name": "Dev User"}
    # --- END BYPASS ---

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# --- Auth Routes ---
@app.get("/auth/google")
async def auth_google(request: Request):
    """Redirect the user to Google's OAuth consent screen."""
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request):
    """Handle the Google callback, upsert the user, and redirect to frontend with JWT."""
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to retrieve user info from Google")

    google_id = user_info["sub"]
    email = user_info.get("email", "")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    # Upsert user record
    conn = get_db_connection()
    cursor = conn.cursor()
    p = get_placeholder()

    cursor.execute(f"SELECT id FROM users WHERE google_id = {p}", (google_id,))
    existing = cursor.fetchone()

    if existing:
        user_id = existing["id"]
        cursor.execute(
            f"UPDATE users SET email = {p}, name = {p}, picture = {p} WHERE google_id = {p}",
            (email, name, picture, google_id),
        )
    else:
        user_id = str(uuid.uuid4())
        cursor.execute(
            f"INSERT INTO users (id, google_id, email, name, picture) VALUES ({p}, {p}, {p}, {p}, {p})",
            (user_id, google_id, email, name, picture),
        )

    conn.commit()
    cursor.close()
    conn.close()

    jwt_token = create_jwt(google_id, email, name, picture)
    return RedirectResponse(url=f"{FRONTEND_URL}?token={jwt_token}")


@app.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    """Return the current user's info from the JWT."""
    return user


# --- Smart Background Cleanup ---
def remove_background(image_bytes: bytes) -> bytes:
    """Remove background using rembg. Falls back to original on failure."""
    try:
        result = remove(image_bytes)
        print(f"Background removed ({len(image_bytes)} -> {len(result)} bytes)")
        return result
    except Exception as e:
        print(f"Background removal failed: {e}. Using original image.")
        return image_bytes


# --- Heuristic Fallback ---
def get_heuristic_fallback(weather: str, vibe: str):
    return {
        "outfit_id": str(uuid.uuid4()),
        "metadata": {"generated_at": datetime.now().isoformat(), "engine_version": "v1.2-fallback"},
        "recommendation": {
            "outfit_name": f"Heuristic {vibe} {weather} Basics",
            "confidence_score": 0.5,
            "rationale": "API Timeout: Using season-appropriate basics.",
            "items": {
                "base_layer": "fallback-tee",
                "mid_layer": None,
                "outerwear": None,
                "bottom": "fallback-jeans",
                "footwear": "fallback-sneakers",
                "accessories": [],
            },
        },
        "warning": "Using heuristic fallback due to LLM timeout.",
    }


# --- Protected Endpoints ---

@app.get("/suggest")
async def suggest_outfit(
    weather: str,
    vibe: str,
    temp: Optional[float] = 20.0,
    precip: Optional[float] = 0.0,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user["sub"]
    p = get_placeholder()

    temporal_state = datetime.now().isoformat()
    environmental_state = f"Temp: {temp}C, Precip: {precip}%"
    contextual_state = f"Event: {vibe}, Formality: 5"

    cursor = db.cursor()
    cursor.execute(
        f"SELECT id, tags, image_path, last_worn FROM closet WHERE is_available = TRUE AND user_id = {p}",
        (user_id,),
    )
    rows = cursor.fetchall()

    closet_items = []
    forty_eight_hours_ago = datetime.now() - timedelta(hours=48)

    for row in rows:
        last_worn = row["last_worn"]
        if isinstance(last_worn, str):
            last_worn = datetime.fromisoformat(last_worn)
        recency_note = " (Recently worn, avoid if possible)" if last_worn and last_worn > forty_eight_hours_ago else ""
        closet_items.append({"id": row["id"], "description": f"{row['tags']}{recency_note}"})

    cursor.close()

    if not closet_items:
        return {"suggestions": [], "message": "Your closet is empty!"}

    closet_menu = "\n".join([f"ID {item['id']}: {item['description']}" for item in closet_items])

    prompt = f"""You are a master fashion stylist.

--- PROTOCOL DATA ---
Temporal: {temporal_state}
Environmental: {environmental_state}
Contextual: {contextual_state}

Constraint: Return ONLY a valid JSON object matching this schema:
{{
  "outfit_id": "UUID",
  "metadata": {{"generated_at": "Timestamp", "engine_version": "v1.2"}},
  "recommendation": {{
    "outfit_name": "String",
    "confidence_score": "Float",
    "rationale": "String",
    "items": {{
      "base_layer": "ItemID",
      "mid_layer": "ItemID | null",
      "outerwear": "ItemID | null",
      "bottom": "ItemID",
      "footwear": "ItemID",
      "accessories": ["ItemID"]
    }}
  }},
  "warning": "String | null"
}}

Rules:
- Favor items NOT marked as 'Recently worn'.
- If a critical layer is missing for cold weather, return a 'warning' with Gap Analysis in rationale.
- No open-toed shoes if precip > 30%. No shorts for Professional formality.

Available Closet:
{closet_menu}
"""

    try:
        content = call_gemini_cli(prompt)
        if content is None:
            return get_heuristic_fallback(weather, vibe)
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"suggestions": [], "error": "AI returned invalid format."}
    except Exception as e:
        return get_heuristic_fallback(weather, vibe)


async def process_ai_tags(item_id: str, image_bytes: bytes):
    """Identify the clothing item using Gemini vision via CLI.
    Saves image to a temp file, passes it via @filepath to the CLI, then cleans up.
    """
    tmp_path = None
    try:
        # Write image to a temp file so the CLI can read it as a vision input
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        tag_prompt = (
            "This is a clothing item photo. Identify it in 5 words or less covering: "
            "Color, Style, Type. Example outputs: 'White slim fit shirt', "
            "'Black leather jacket', 'Blue denim skinny jeans'. "
            "Respond with ONLY the description, no extra text."
        )
        ai_tags = call_gemini_cli(tag_prompt, image_path=tmp_path)
        if not ai_tags:
            ai_tags = "Unidentified item"

        conn = get_db_connection()
        cursor = conn.cursor()
        p = get_placeholder()
        cursor.execute(f"UPDATE closet SET tags = {p} WHERE id = {p}", (ai_tags, item_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Background AI tagging error: {e}")
    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/upload")
async def upload_clothing_items(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user["sub"]
    p = get_placeholder()
    uploaded_results = []

    for file in files:
        file_content = await file.read()
        clean_bytes = remove_background(file_content)
        base64_image = base64.b64encode(clean_bytes).decode("utf-8")

        upload_result = cloudinary.uploader.upload(
            io.BytesIO(clean_bytes), format="png", resource_type="image"
        )
        image_url = upload_result.get("secure_url")

        item_id = str(uuid.uuid4())
        cursor = db.cursor()
        cursor.execute(
            f"INSERT INTO closet (id, user_id, image_path, tags) VALUES ({p}, {p}, {p}, {p})",
            (item_id, user_id, image_url, "Processing AI tags..."),
        )
        db.commit()
        cursor.close()

        background_tasks.add_task(process_ai_tags, item_id, clean_bytes)
        uploaded_results.append({"id": item_id, "url": image_url})

    return {"message": f"Successfully queued {len(files)} items", "items": uploaded_results}


@app.post("/wear")
async def wear_outfit(item_ids: List[str], db=Depends(get_db), user=Depends(get_current_user)):
    p = get_placeholder()
    cursor = db.cursor()
    now = datetime.now()
    timestamp = now.isoformat() if not DATABASE_URL else now

    for item_id in item_ids:
        cursor.execute(f"UPDATE closet SET last_worn = {p} WHERE id = {p}", (timestamp, item_id))

    db.commit()
    cursor.close()
    return {"message": "Outfit marked as worn!"}


@app.get("/items")
async def get_items(db=Depends(get_db), user=Depends(get_current_user)):
    user_id = user["sub"]
    p = get_placeholder()
    cursor = db.cursor()
    cursor.execute(
        f"SELECT id, image_path, tags FROM closet WHERE user_id = {p} ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cursor.fetchall()
    items = [{"id": row["id"], "image_path": row["image_path"], "tags": row["tags"]} for row in rows]
    cursor.close()
    return items