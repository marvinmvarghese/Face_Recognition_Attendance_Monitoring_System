import json
from dataclasses import dataclass

import numpy as np

try:
    import face_recognition
except ImportError as exc:
    raise RuntimeError(
        "face_recognition is not installed. Install dependencies from requirements.txt first."
    ) from exc


@dataclass
class MatchResult:
    user_id: int
    name: str
    confidence: float


def encode_embedding(embedding: np.ndarray) -> str:
    return json.dumps(embedding.tolist())


def decode_embedding(embedding_json: str) -> np.ndarray:
    return np.array(json.loads(embedding_json), dtype=np.float64)


def extract_embeddings_from_image_bgr(image_bgr: np.ndarray) -> list[np.ndarray]:
    # dlib/face_recognition expects a contiguous uint8 RGB array.
    rgb = np.ascontiguousarray(image_bgr[:, :, ::-1], dtype=np.uint8)
    locations = face_recognition.face_locations(rgb, model="hog")
    return face_recognition.face_encodings(rgb, locations)


def extract_single_embedding(image_bgr: np.ndarray) -> np.ndarray:
    encodings = extract_embeddings_from_image_bgr(image_bgr)
    if not encodings:
        raise ValueError("No face found in image")
    if len(encodings) > 1:
        raise ValueError("Multiple faces found. Upload an image with one face.")
    return encodings[0]


def find_best_match(
    query_embedding: np.ndarray,
    candidates: list[tuple[int, str, np.ndarray]],
    threshold: float = 0.5,
) -> MatchResult | None:
    if not candidates:
        return None
    known_matrix = np.array([enc for _, _, enc in candidates], dtype=np.float64)
    distances = face_recognition.face_distance(known_matrix, query_embedding)
    best_idx = int(np.argmin(distances))
    best_distance = float(distances[best_idx])
    if best_distance > threshold:
        return None
    user_id, name, _ = candidates[best_idx]
    confidence = float(max(0.0, min(1.0, 1.0 - best_distance)))
    return MatchResult(user_id=user_id, name=name, confidence=confidence)
