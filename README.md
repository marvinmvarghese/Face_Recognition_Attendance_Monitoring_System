# Face Recognition Attendance System

Production-oriented web attendance system with daily attendance, face recognition mode, and manual tick mode.

## Structure

- `backend/`: FastAPI API with auth, face registration, recognition, and attendance routes
- `web/`: browser frontend (login, capture/upload, mark attendance, admin records)
- `dataset/`: optional image dataset storage
- `attendance_logs/`: exported logs

## Quick Start

1. Create a virtualenv and install dependencies:
   - `python3 -m venv .venv`
   - `.venv/bin/python -m pip install -r requirements.txt`
2. Run backend:
   - `.venv/bin/python -m uvicorn backend.main:app --reload`
3. Open web app:
   - `http://127.0.0.1:8000/web/`
4. Open API docs:
   - `http://127.0.0.1:8000/docs`

## Admin Web Flow

1. Login as admin in `/web`.
2. Choose session date.
3. Start camera and capture each present student (or upload image).
4. App scans faces and adds known students to a pending list.
5. Unknown faces are not added to attendance list.
6. Admin can edit saved records in the records table.
7. Click `Submit Attendance` to mark all entries for that date.

## Default API Flow

1. `POST /auth/register` to create users.
2. `POST /auth/login` to get JWT.
3. Admin: `POST /faces/register/{user_id}` with a face image.
4. Admin: `POST /attendance/scan` to detect known and unknown faces.
5. Admin: `POST /attendance/submit-batch` to mark attendance for selected date.
6. Admin: `PATCH /attendance/records/{id}` and `DELETE /attendance/records/{id}` for corrections.
7. Admin: `GET /attendance/records`, `GET /attendance/export-csv`, or `GET /attendance/export-sheet`.

## Production Notes

- Set `SECRET_KEY` and `DATABASE_URL` via environment variables.
- Move from SQLite to PostgreSQL by setting:
  - `DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname`
- Add liveness detection before marking attendance for anti-spoofing.
# Face_Recognition_Attendance_Monitoring_System
