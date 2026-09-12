"""
Central application configuration.

All tunables are read from environment variables (with sane defaults) so the
app can be reconfigured per-deployment without touching code, per 12-factor
practice. In a real production deployment, ADMIN_TOKEN and SECRET_KEY should
always be overridden via the environment / a secrets manager rather than
relying on the defaults below.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

# --- Storage -----------------------------------------------------------
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
FACES_DIR = DATA_DIR / "faces"                # cropped, normalized face images
DATABASE_PATH = DATA_DIR / "app.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
MODEL_PATH = DATA_DIR / "lbph_model.yml"      # trained recognizer, cached to disk

# --- Security ------------------------------------------------------------
# Admin token protects registration / deletion / listing of PII. Identify
# endpoint is intentionally left open since that's the "walk up to a camera"
# public-facing flow described in the spec.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-admin-token")

# --- Face detection / recognition tuning ---------------------------------
FACE_SIZE = (200, 200)               # normalized crop size fed to LBPH
HAAR_SCALE_FACTOR = 1.1
HAAR_MIN_NEIGHBORS = 6
HAAR_MIN_SIZE = (80, 80)

# LBPH predict() returns a *distance* (lower = more similar). Empirically,
# genuine matches on a webcam-quality crop tend to score well under 60-70,
# impostors/unknowns score much higher. Tunable via env for the deployment's
# camera/lighting conditions.
LBPH_MAX_DISTANCE = float(os.getenv("LBPH_MAX_DISTANCE", "70"))

MIN_SAMPLES_PER_INDIVIDUAL = 1
RECOMMENDED_SAMPLES_PER_INDIVIDUAL = 3

MAX_UPLOAD_BYTES = 8 * 1024 * 1024   # 8 MB per image
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

for d in (DATA_DIR, FACES_DIR):
    d.mkdir(parents=True, exist_ok=True)
