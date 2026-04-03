import csv
from datetime import date, datetime
from io import StringIO

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
import numpy as np
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from ..database import get_db
from ..dependencies import get_current_user, require_admin
from ..face_engine import decode_embedding, extract_embeddings_from_image_bgr, find_best_match
from ..models import Attendance, AttendanceStatus, FaceEmbedding, User
from ..schemas import (
    AttendanceRead,
    AttendanceResponse,
    AttendanceUpdateRequest,
    BatchAttendanceSubmitRequest,
    BatchAttendanceSubmitResponse,
    FaceRecognitionResult,
    ScanResponse,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _decode_image(contents: bytes) -> np.ndarray:
    arr = np.frombuffer(contents, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file")
    return image


def _parse_attendance_date(attendance_date: str | None) -> date:
    now = datetime.utcnow()
    return now.date() if attendance_date is None else datetime.fromisoformat(attendance_date).date()


def _build_candidates(db: Session) -> list[tuple[int, str, np.ndarray]]:
    known_rows = db.execute(
        select(FaceEmbedding.user_id, User.name, FaceEmbedding.embedding_json).join(User, User.id == FaceEmbedding.user_id)
    ).all()
    return [(row.user_id, row.name, decode_embedding(row.embedding_json)) for row in known_rows]


def _scan_embeddings(
    embeddings: list[np.ndarray],
    candidates: list[tuple[int, str, np.ndarray]],
    threshold: float = 0.5,
) -> tuple[list[FaceRecognitionResult], int]:
    recognized_by_user: dict[int, FaceRecognitionResult] = {}
    unknown_faces = 0
    for embedding in embeddings:
        match = find_best_match(embedding, candidates=candidates, threshold=threshold)
        if match is None:
            unknown_faces += 1
            continue
        current = recognized_by_user.get(match.user_id)
        if current is None or match.confidence > current.confidence:
            recognized_by_user[match.user_id] = FaceRecognitionResult(
                user_id=match.user_id,
                name=match.name,
                confidence=match.confidence,
            )
    recognized = sorted(recognized_by_user.values(), key=lambda item: item.name)
    return recognized, unknown_faces


@router.post("/scan", response_model=ScanResponse)
async def scan_faces(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScanResponse:
    contents = await file.read()
    image = _decode_image(contents)
    embeddings = extract_embeddings_from_image_bgr(image)
    if not embeddings:
        return ScanResponse(recognized=[], unknown_faces=0, message="No face detected")

    candidates = _build_candidates(db)
    recognized, unknown_faces = _scan_embeddings(embeddings, candidates, threshold=0.5)
    if not recognized and unknown_faces > 0:
        return ScanResponse(recognized=[], unknown_faces=unknown_faces, message="Unknown face(s) detected")
    return ScanResponse(
        recognized=recognized,
        unknown_faces=unknown_faces,
        message=f"Detected {len(recognized)} known face(s), {unknown_faces} unknown face(s)",
    )


@router.post("/submit-batch", response_model=BatchAttendanceSubmitResponse)
def submit_batch_attendance(
    payload: BatchAttendanceSubmitRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BatchAttendanceSubmitResponse:
    if not payload.entries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No attendance entries provided")

    created_count = 0
    updated_count = 0
    skipped_count = 0
    now = datetime.utcnow()

    for entry in payload.entries:
        user = db.get(User, entry.user_id)
        if user is None:
            skipped_count += 1
            continue

        existing = db.scalar(
            select(Attendance).where(
                and_(
                    Attendance.user_id == entry.user_id,
                    Attendance.attendance_date == payload.attendance_date,
                    Attendance.attendance_hour == 0,
                )
            )
        )
        if existing:
            existing.status = entry.status
            existing.confidence = entry.confidence
            existing.attendance_time = now.time().replace(microsecond=0)
            updated_count += 1
            continue

        db.add(
            Attendance(
                user_id=entry.user_id,
                attendance_date=payload.attendance_date,
                attendance_hour=0,
                attendance_time=now.time().replace(microsecond=0),
                status=entry.status,
                confidence=entry.confidence,
            )
        )
        created_count += 1

    db.commit()
    return BatchAttendanceSubmitResponse(
        message="Attendance batch saved",
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


@router.post("/recognize", response_model=AttendanceResponse)
async def recognize_and_mark_attendance(
    file: UploadFile = File(...),
    attendance_date: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttendanceResponse:
    contents = await file.read()
    image = _decode_image(contents)
    embeddings = extract_embeddings_from_image_bgr(image)
    if not embeddings:
        return AttendanceResponse(recognized=False, message="No face detected")

    candidates = _build_candidates(db)
    recognized, unknown_faces = _scan_embeddings([embeddings[0]], candidates, threshold=0.5)
    if not recognized:
        return AttendanceResponse(recognized=False, message="Unknown face detected" if unknown_faces else "Face not recognized")

    match = recognized[0]
    if current_user.role != "admin" and current_user.id != match.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Matched identity does not belong to current user")

    slot_date = _parse_attendance_date(attendance_date)
    existing = db.scalar(
        select(Attendance).where(
            and_(
                Attendance.user_id == match.user_id,
                Attendance.attendance_date == slot_date,
                Attendance.attendance_hour == 0,
            )
        )
    )
    if existing:
        return AttendanceResponse(
            recognized=True,
            message="Attendance already marked for this date",
            user=match,
            attendance_date=existing.attendance_date,
            attendance_time=existing.attendance_time,
        )

    now = datetime.utcnow()
    record = Attendance(
        user_id=match.user_id,
        attendance_date=slot_date,
        attendance_hour=0,
        attendance_time=now.time().replace(microsecond=0),
        status=AttendanceStatus.present.value,
        confidence=match.confidence,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return AttendanceResponse(
        recognized=True,
        message="Attendance marked successfully",
        user=match,
        attendance_date=record.attendance_date,
        attendance_time=record.attendance_time,
    )


@router.get("/records", response_model=list[AttendanceRead])
def list_attendance_records(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AttendanceRead]:
    stmt = select(
        Attendance.id,
        Attendance.user_id,
        User.name.label("user_name"),
        Attendance.attendance_date,
        Attendance.attendance_time,
        Attendance.status,
        Attendance.confidence,
        Attendance.created_at,
    ).join(User, User.id == Attendance.user_id)
    if start_date:
        stmt = stmt.where(Attendance.attendance_date >= datetime.fromisoformat(start_date).date())
    if end_date:
        stmt = stmt.where(Attendance.attendance_date <= datetime.fromisoformat(end_date).date())
    rows = db.execute(stmt.order_by(User.name.asc(), Attendance.attendance_date.desc())).all()
    return [AttendanceRead(**row._mapping) for row in rows]


@router.patch("/records/{attendance_id}", response_model=AttendanceRead)
def update_attendance_record(
    attendance_id: int,
    payload: AttendanceUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AttendanceRead:
    record = db.get(Attendance, attendance_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    if payload.attendance_date is not None:
        record.attendance_date = payload.attendance_date
    if payload.status is not None:
        record.status = payload.status

    db.commit()
    db.refresh(record)
    user = db.get(User, record.user_id)
    return AttendanceRead(
        id=record.id,
        user_id=record.user_id,
        user_name=user.name if user else f"User #{record.user_id}",
        attendance_date=record.attendance_date,
        attendance_time=record.attendance_time,
        status=record.status,
        confidence=record.confidence,
        created_at=record.created_at,
    )


@router.delete("/records/{attendance_id}")
def delete_attendance_record(
    attendance_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    record = db.get(Attendance, attendance_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    db.delete(record)
    db.commit()
    return {"message": "Attendance record deleted", "id": attendance_id}


@router.get("/export-csv")
def export_attendance_csv(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    rows = db.execute(
        select(
            Attendance.id,
            User.name,
            User.email,
            Attendance.attendance_date,
            Attendance.attendance_time,
            Attendance.status,
        ).join(User, User.id == Attendance.user_id).order_by(User.name.asc(), Attendance.attendance_date.desc())
    ).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "name", "email", "date", "time", "status"])
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"},
    )


@router.get("/export-sheet")
def export_attendance_sheet(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    rows = db.execute(
        select(
            Attendance.id,
            User.name,
            User.email,
            Attendance.attendance_date,
            Attendance.attendance_time,
            Attendance.status,
        ).join(User, User.id == Attendance.user_id).order_by(User.name.asc(), Attendance.attendance_date.desc())
    ).all()
    html = [
        "<html><body><table border='1'>",
        "<tr><th>ID</th><th>Name</th><th>Email</th><th>Date</th><th>Time</th><th>Status</th></tr>",
    ]
    for row in rows:
        html.append(
            f"<tr><td>{row.id}</td><td>{row.name}</td><td>{row.email}</td><td>{row.attendance_date}</td><td>{row.attendance_time}</td><td>{row.status}</td></tr>"
        )
    html.append("</table></body></html>")
    return StreamingResponse(
        iter(["".join(html)]),
        media_type="application/vnd.ms-excel",
        headers={"Content-Disposition": "attachment; filename=attendance_sheet.xls"},
    )
