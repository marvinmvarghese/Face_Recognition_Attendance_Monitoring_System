from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import cv2
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, require_admin
from ..face_engine import encode_embedding, extract_single_embedding
from ..models import FaceEmbedding, User

router = APIRouter(prefix="/faces", tags=["face-registration"])


def _decode_image(contents: bytes) -> np.ndarray:
    arr = np.frombuffer(contents, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file")
    return image


@router.post("/register/{user_id}")
async def register_face_for_user(
    user_id: int,
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    contents = await file.read()
    image = _decode_image(contents)
    try:
        embedding = extract_single_embedding(image)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    db.execute(delete(FaceEmbedding).where(FaceEmbedding.user_id == user_id))
    db.add(FaceEmbedding(user_id=user_id, embedding_json=encode_embedding(embedding)))
    db.commit()

    return {"message": "Face registered successfully", "user_id": user_id}


@router.get("/me")
def my_face_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    embedding = db.scalar(select(FaceEmbedding).where(FaceEmbedding.user_id == current_user.id))
    return {"user_id": current_user.id, "face_registered": embedding is not None}
