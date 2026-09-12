import uuid
from pathlib import Path

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import (
    ALLOWED_IMAGE_TYPES,
    FACES_DIR,
    MAX_UPLOAD_BYTES,
    MIN_SAMPLES_PER_INDIVIDUAL,
)
from app.core.database import get_db
from app.core.face_engine import NoFaceDetected, decode_image, engine
from app.core.retrain import retrain_from_db
from app.core.security import require_admin
from app.models.db_models import FaceSample, Individual
from app.models.schemas import IndividualOut, RegisterResponse

router = APIRouter(prefix="/api/individuals", tags=["individuals"])


def _to_out(individual: Individual) -> IndividualOut:
    out = IndividualOut.model_validate(individual)
    out.sample_count = len(individual.face_samples)
    return out


async def _read_and_validate(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported image type '{file.content_type}'. Allowed: {sorted(ALLOWED_IMAGE_TYPES)}",
        )
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image too large.")
    return raw


@router.post("", response_model=RegisterResponse, dependencies=[Depends(require_admin)])
async def register_individual(
    full_name: str = Form(...),
    role_or_title: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    notes: str = Form(""),
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    full_name = full_name.strip()
    if not full_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "full_name is required.")
    if len(images) < MIN_SAMPLES_PER_INDIVIDUAL:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"At least {MIN_SAMPLES_PER_INDIVIDUAL} face image is required.",
        )

    crops = []
    for f in images:
        raw = await _read_and_validate(f)
        try:
            img = decode_image(raw)
            crop = engine.extract_face(img)
        except NoFaceDetected:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"No face detected in '{f.filename}'. Please retake that photo with the "
                "face clearly visible and well lit.",
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        crops.append(crop)

    individual = Individual(
        full_name=full_name,
        role_or_title=role_or_title.strip() or None,
        email=email.strip() or None,
        phone=phone.strip() or None,
        notes=notes.strip() or None,
    )
    db.add(individual)
    db.flush()

    person_dir = Path(FACES_DIR) / str(individual.id)
    person_dir.mkdir(parents=True, exist_ok=True)
    for crop in crops:
        image_path = person_dir / f"{uuid.uuid4().hex}.png"
        cv2.imwrite(str(image_path), crop)
        db.add(FaceSample(individual_id=individual.id, image_path=str(image_path)))

    db.commit()
    db.refresh(individual)

    retrain_from_db(db)

    return RegisterResponse(
        individual=_to_out(individual),
        samples_captured=len(crops),
        message=f"Registered '{individual.full_name}' with {len(crops)} face sample(s).",
    )


@router.get("", response_model=list[IndividualOut], dependencies=[Depends(require_admin)])
def list_individuals(db: Session = Depends(get_db)):
    individuals = (
        db.query(Individual)
        .outerjoin(FaceSample)
        .group_by(Individual.id)
        .order_by(Individual.full_name)
        .all()
    )
    return [_to_out(i) for i in individuals]


@router.get("/{individual_id}", response_model=IndividualOut, dependencies=[Depends(require_admin)])
def get_individual(individual_id: int, db: Session = Depends(get_db)):
    individual = db.get(Individual, individual_id)
    if not individual:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Individual not found.")
    return _to_out(individual)


@router.delete("/{individual_id}", dependencies=[Depends(require_admin)])
def delete_individual(individual_id: int, db: Session = Depends(get_db)):
    individual = db.get(Individual, individual_id)
    if not individual:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Individual not found.")

    for sample in individual.face_samples:
        try:
            Path(sample.image_path).unlink(missing_ok=True)
        except OSError:
            pass
    person_dir = Path(FACES_DIR) / str(individual.id)
    try:
        person_dir.rmdir()
    except OSError:
        pass

    db.delete(individual)
    db.commit()

    retrain_from_db(db)

    return {"message": f"Deleted individual {individual_id}."}
