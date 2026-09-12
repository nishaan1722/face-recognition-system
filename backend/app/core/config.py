
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  


DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
FACES_DIR = DATA_DIR / "faces"                
DATABASE_PATH = DATA_DIR / "app.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
MODEL_PATH = DATA_DIR / "lbph_model.yml"      


ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-admin-token")


FACE_SIZE = (200, 200)               
HAAR_SCALE_FACTOR = 1.1
HAAR_MIN_NEIGHBORS = 6
HAAR_MIN_SIZE = (80, 80)


LBPH_MAX_DISTANCE = float(os.getenv("LBPH_MAX_DISTANCE", "70"))

MIN_SAMPLES_PER_INDIVIDUAL = 1
RECOMMENDED_SAMPLES_PER_INDIVIDUAL = 3

MAX_UPLOAD_BYTES = 8 * 1024 * 1024   
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

for d in (DATA_DIR, FACES_DIR):
    d.mkdir(parents=True, exist_ok=True)
