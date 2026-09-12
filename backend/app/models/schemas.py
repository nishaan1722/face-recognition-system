import datetime

from pydantic import BaseModel, ConfigDict


class IndividualOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role_or_title: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    created_at: datetime.datetime
    sample_count: int = 0


class RegisterResponse(BaseModel):
    individual: IndividualOut
    samples_captured: int
    message: str


class IdentifyResponse(BaseModel):
    identified: bool
    individual: IndividualOut | None = None
    distance: float | None = None
    confidence_pct: float | None = None
    message: str
