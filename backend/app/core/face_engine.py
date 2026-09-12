from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.config import (
    FACE_SIZE,
    HAAR_MIN_NEIGHBORS,
    HAAR_MIN_SIZE,
    HAAR_SCALE_FACTOR,
    LBPH_MAX_DISTANCE,
    MODEL_PATH,
)

logger = logging.getLogger("face_engine")

_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


class NoFaceDetected(Exception):
    pass


class MultipleFacesDetected(Exception):
    pass


@dataclass
class RecognitionResult:
    matched: bool
    individual_id: Optional[int]
    distance: Optional[float]
    confidence_pct: Optional[float]


class FaceEngine:
    def __init__(self) -> None:
        self._detector = cv2.CascadeClassifier(_CASCADE_PATH)
        if self._detector.empty():
            raise RuntimeError(f"Failed to load Haar cascade from {_CASCADE_PATH}")
        self._recognizer = cv2.face.LBPHFaceRecognizer_create()
        self._trained = False
        self._lock = threading.RLock()
        self._label_count = 0
        self._load_if_exists()

    def detect_largest_face(self, image_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self._detector.detectMultiScale(
            gray,
            scaleFactor=HAAR_SCALE_FACTOR,
            minNeighbors=HAAR_MIN_NEIGHBORS,
            minSize=HAAR_MIN_SIZE,
        )
        if len(faces) == 0:
            raise NoFaceDetected("No face detected in the supplied image.")
        faces = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
        return faces[0]

    def preprocess(self, image_bgr: np.ndarray, box) -> np.ndarray:
        x, y, w, h = box
        x, y = max(0, x), max(0, y)
        face = image_bgr[y : y + h, x : x + w]
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, FACE_SIZE, interpolation=cv2.INTER_LINEAR)
        gray = cv2.equalizeHist(gray)
        return gray

    def extract_face(self, image_bgr: np.ndarray) -> np.ndarray:
        box = self.detect_largest_face(image_bgr)
        return self.preprocess(image_bgr, box)

    def train(self, samples: list[tuple[np.ndarray, int]]) -> None:
        with self._lock:
            if not samples:
                self._trained = False
                self._label_count = 0
                self._recognizer = cv2.face.LBPHFaceRecognizer_create()
                return
            images = [s[0] for s in samples]
            labels = np.array([s[1] for s in samples], dtype=np.int32)
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.train(images, labels)
            self._recognizer = recognizer
            self._trained = True
            self._label_count = len(set(labels.tolist()))
            recognizer.write(str(MODEL_PATH))
            logger.info("Retrained LBPH model on %d samples / %d individuals",
                        len(samples), self._label_count)

    def _load_if_exists(self) -> None:
        if Path(MODEL_PATH).exists():
            try:
                self._recognizer.read(str(MODEL_PATH))
                self._trained = True
                logger.info("Loaded cached LBPH model from %s", MODEL_PATH)
            except cv2.error:
                logger.warning("Could not load cached model; will retrain on next change.")

    def identify(self, image_bgr: np.ndarray) -> RecognitionResult:
        face = self.extract_face(image_bgr)
        with self._lock:
            if not self._trained:
                return RecognitionResult(False, None, None, None)
            label, distance = self._recognizer.predict(face)
        matched = distance <= LBPH_MAX_DISTANCE
        confidence_pct = max(0.0, min(100.0, 100.0 * (1 - distance / (LBPH_MAX_DISTANCE * 2))))
        return RecognitionResult(
            matched=matched,
            individual_id=label if matched else None,
            distance=float(distance),
            confidence_pct=round(confidence_pct, 1),
        )


engine = FaceEngine()


def decode_image(raw_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image - unsupported or corrupt file.")
    return img
