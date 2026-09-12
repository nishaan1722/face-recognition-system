import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Individual(Base):
    """A registered person and the profile information shown on identification."""

    __tablename__ = "individuals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_or_title: Mapped[str] = mapped_column(String(200), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    face_samples: Mapped[list["FaceSample"]] = relationship(
        back_populates="individual", cascade="all, delete-orphan"
    )


class FaceSample(Base):
    """
    One registered face image for an individual, stored as a normalized
    grayscale crop on disk. Multiple samples per individual improve LBPH
    recognition robustness across pose/lighting.
    """

    __tablename__ = "face_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    individual_id: Mapped[int] = mapped_column(
        ForeignKey("individuals.id", ondelete="CASCADE"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    individual: Mapped["Individual"] = relationship(back_populates="face_samples")
