from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import ALLOWED_IMAGE_TYPES, MAX_UPLOAD_BYTES
from app.core.database import get_db
from app.core.face_engine import NoFaceDetected, decode_image, engine
from app.core.rate_limit import rate_limit
from app.models.db_models import Individual
from app.models.schemas import IdentifyResponse, IndividualOut

router = APIRouter(prefix="/api", tags=["identify"])


@router.post("/identify", response_model=IdentifyResponse, dependencies=[Depends(rate_limit)])
async def identify(request: Request, image: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Take a single camera frame, detect the largest face in it, and attempt to
    match it against the registered population.

    Always returns 200 with a structured "identified" flag rather than 404 -
    "unrecognized face" is an expected, normal outcome of this endpoint, not
    an error.
    """
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported image type '{image.content_type}'.",
        )
    raw = await image.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image too large.")

    try:
        img = decode_image(raw)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    try:
        result = engine.identify(img)
    except NoFaceDetected:
        return IdentifyResponse(identified=False, message="No face detected in frame.")

    if not result.matched or result.individual_id is None:
        return IdentifyResponse(
            identified=False,
            distance=result.distance,
            confidence_pct=result.confidence_pct,
            message="Face detected but not recognized as a registered individual.",
        )

    individual = db.get(Individual, result.individual_id)
    if individual is None:
        # Model/DB briefly out of sync (e.g. deletion race) - treat as unknown.
        return IdentifyResponse(identified=False, message="No matching registered individual.")

    out = IndividualOut.model_validate(individual)
    out.sample_count = len(individual.face_samples)
    return IdentifyResponse(
        identified=True,
        individual=out,
        distance=result.distance,
        confidence_pct=result.confidence_pct,
        message=f"Identified as {individual.full_name}.",
    )
