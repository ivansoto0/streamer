import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MEDIA_ROOTS = [
    Path(p.strip())
    for p in os.environ.get("MEDIA_ROOTS", "").split(",")
    if p.strip()
]

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8054"))

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "")
AUTH_PASSWORD_HASH = os.environ.get("AUTH_PASSWORD_HASH", "")
