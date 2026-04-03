from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, Enum):
    admin = "admin"
    student = "student"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.student.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    embeddings: Mapped[list["FaceEmbedding"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    attendance_records: Mapped[list["Attendance"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="embeddings")


class AttendanceStatus(str, Enum):
    present = "present"
    absent = "absent"


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("user_id", "attendance_date", "attendance_hour", name="uq_user_attendance_per_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    attendance_hour: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    attendance_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=AttendanceStatus.present.value, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="attendance_records")
