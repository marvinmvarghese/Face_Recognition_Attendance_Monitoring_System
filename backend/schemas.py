from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=120)
    role: str = Field(default="student")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FaceRecognitionResult(BaseModel):
    user_id: int
    name: str
    confidence: float


class ScanResponse(BaseModel):
    recognized: list[FaceRecognitionResult]
    unknown_faces: int
    message: str


class AttendanceResponse(BaseModel):
    recognized: bool
    message: str
    user: FaceRecognitionResult | None = None
    attendance_date: date | None = None
    attendance_time: time | None = None


class AttendanceRead(BaseModel):
    id: int
    user_id: int
    user_name: str
    attendance_date: date
    attendance_time: time
    status: str
    confidence: float
    created_at: datetime


class BatchAttendanceItem(BaseModel):
    user_id: int
    confidence: float = Field(default=1.0, ge=0, le=1)
    status: str = Field(default="present")


class BatchAttendanceSubmitRequest(BaseModel):
    attendance_date: date
    entries: list[BatchAttendanceItem]


class BatchAttendanceSubmitResponse(BaseModel):
    message: str
    created_count: int
    updated_count: int
    skipped_count: int


class AttendanceUpdateRequest(BaseModel):
    attendance_date: date | None = None
    status: str | None = None
