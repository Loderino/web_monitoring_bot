import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(override=True)

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
TICK_DURATION = int(os.getenv("TICK_DURATION", "10"))
FAILURE_THRESHOLD = int(os.getenv("FAILURE_THRESHOLD", "3"))

LOGS_DIR = Path(os.getenv("LOGS_DIR", "/data/logs/"))
LANGUAGE_PATH = Path(os.getenv("LANGUAGE_PATH", "/data/language.json"))

MONGO_URI = os.getenv("MONGO_URI", "http://localhost:27017")

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")