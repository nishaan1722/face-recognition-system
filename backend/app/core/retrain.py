import cv2
from sqlalchemy.orm import Session

from app.core.face_engine import engine
from app.models.db_models import FaceSample


def retrain_from_db(db: Session) -> None:
    
    samples: list[tuple] = []
    for sample in db.query(FaceSample).all():
        img = cv2.imread(sample.image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        samples.append((img, sample.individual_id))
    engine.train(samples)
