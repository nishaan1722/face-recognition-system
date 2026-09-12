"""
Computer-vision core.

Pipeline:
  1. Detection  - Haar Cascade (haarcascade_frontalface_default), bundled with
                  OpenCV. No external model download required.
  2. Preprocessing - crop to the largest detected face, convert to grayscale,
                  resize to a fixed size, histogram-equalize for lighting
                  invariance.
  3. Recognition - LBPH (Local Binary Patterns Histograms) face recognizer,
                  from opencv-contrib. LBPH is trained directly on the stored
                  face crops of all registered individuals (label = individual
                  id) and produces a distance score at inference time - lower
                  is a better match.

Why this stack (vs. dlib / face_recognition / a deep embedding model):
  - Zero external weight downloads: both the detector and recognizer ship
    inside opencv-contrib-python-headless, so `pip install` + first run works
    offline, with no flaky model-download step to document or debug.
  - No native build toolchain required (dlib needs cmake + a C++ compiler
    and is a common source of setup friction).
  - Accuracy trade-off: LBPH is meaningfully less robust than a modern deep
    embedding model (e.g. ArcFace/SFace) to pose, expression and lighting
    variation, and it must be retrained (not just updated) when the
    registered set changes. For a small-to-medium registered population in
    reasonably controlled lighting -- which fits this assignment's scope --
    it performs adequately. The `FaceEngine` interface below is intentionally
    narrow (detect / preprocess / train / predict) so the LBPH implementation
    could be swapped for a deep-embedding + cosine-similarity approach later
    without changing any calling code.
"""
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
    distance: Optional[float]   # lower = more confident match
    confidence_pct: Optional[float]  # 0-100, derived from distance, for UI display


class FaceEngine:
    """
    Thread-safe wrapper around Haar detection + LBPH recognition.

    A single process-wide instance is used (see main.py). All mutating
    operations (train/reload) are guarded by a lock since the LBPH model
    object is not safe for concurrent read-while-write use, and FastAPI may
    serve requests on multiple worker threads.
    """

    def __init__(self) -> None:
        self._detector = cv2.CascadeClassifier(_CASCADE_PATH)
        if self._detector.empty():
            raise RuntimeError(f"Failed to load Haar cascade from {_CASCADE_PATH}")
        self._recognizer = cv2.face.LBPHFaceRecognizer_create()
        self._trained = False
        self._lock = threading.RLock()
        self._label_count = 0
        self._load_if_exists()

    # ---------------------------------------------------------------- detect
    def detect_largest_face(self, image_bgr: np.ndarray) -> np.ndarray:
        """Return the (x, y, w, h) box of the largest detected face, or raise."""
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
        # Pick the largest box by area - the person presumably closest to camera.
        faces = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
        return faces[0]

    def preprocess(self, image_bgr: np.ndarray, box) -> np.ndarray:
        """Crop to `box`, convert to normalized grayscale suitable for LBPH."""
        x, y, w, h = box
        x, y = max(0, x), max(0, y)
        face = image_bgr[y : y + h, x : x + w]
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, FACE_SIZE, interpolation=cv2.INTER_LINEAR)
        gray = cv2.equalizeHist(gray)
        return gray

    def extract_face(self, image_bgr: np.ndarray) -> np.ndarray:
        """Convenience: detect + preprocess in one call. Raises NoFaceDetected."""
        box = self.detect_largest_face(image_bgr)
        return self.preprocess(image_bgr, box)

    # ----------------------------------------------------------------- train
    def train(self, samples: list[tuple[np.ndarray, int]]) -> None:
        """
        Fully retrain the recognizer from scratch on `samples` =
        [(normalized_gray_face, individual_id), ...].

        LBPH doesn't support removing a label incrementally, so on any change
        to the registered population (add/delete) we retrain from all stored
        crops on disk. This is a deliberate simplicity/scale trade-off: fine
        for the "small but complete" scope here; a larger deployment would
        want an embedding-based approach (add/remove = vector insert/delete,
        no retrain).
        """
        with self._lock:
            if not samples:
                self._trained = False
                self._label_count = 0
                # Recreate a fresh, empty recognizer.
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

    # --------------------------------------------------------------- predict
    def identify(self, image_bgr: np.ndarray) -> RecognitionResult:
        """
        Detect the largest face in `image_bgr` and match it against the
        trained population. Raises NoFaceDetected if no face is found.
        """
        face = self.extract_face(image_bgr)
        with self._lock:
            if not self._trained:
                return RecognitionResult(False, None, None, None)
            label, distance = self._recognizer.predict(face)
        matched = distance <= LBPH_MAX_DISTANCE
        # Map distance -> a rough 0-100 "confidence" for display purposes only.
        confidence_pct = max(0.0, min(100.0, 100.0 * (1 - distance / (LBPH_MAX_DISTANCE * 2))))
        return RecognitionResult(
            matched=matched,
            individual_id=label if matched else None,
            distance=float(distance),
            confidence_pct=round(confidence_pct, 1),
        )


# Process-wide singleton, created at import time and reused across requests.
engine = FaceEngine()


def decode_image(raw_bytes: bytes) -> np.ndarray:
    """Decode uploaded image bytes into a BGR numpy array (as OpenCV expects)."""
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image - unsupported or corrupt file.")
    return img
