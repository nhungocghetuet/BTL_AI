"""Bảng SQLite: file đã upload và thời khóa biểu đã chuẩn hóa.

Quan hệ: UploadedFile 1-n CourseRecord 1-n SectionRecord 1-n MeetingRecord.
Các lớp ORM đặt tên ...Record để không trùng với schema Pydantic cùng tên
(Course, SectionOption, Meeting) trong app/schemas/timetable.py.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

UPLOAD_STATUS_UPLOADED = "uploaded"  # đã lưu file, chờ người dùng xác nhận mapping
UPLOAD_STATUS_CONFIRMED = "confirmed"  # đã chuẩn hóa và lưu thời khóa biểu


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # uuid4().hex
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default=UPLOAD_STATUS_UPLOADED)

    # Cách đọc file được dùng lại khi xác nhận mapping
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    header_row: Mapped[int | None]  # 0-based
    mapping: Mapped[dict | None] = mapped_column(JSON)  # ColumnMapping đã xác nhận

    semester: Mapped[str | None] = mapped_column(String(100))
    time_unit: Mapped[str | None] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    courses: Mapped[list["CourseRecord"]] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
        order_by="CourseRecord.id",
    )


class CourseRecord(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("file_id", "course_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[str] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[str] = mapped_column(String(50))
    course_name: Mapped[str] = mapped_column(String(255))

    upload: Mapped[UploadedFile] = relationship(back_populates="courses")
    sections: Mapped[list["SectionRecord"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="SectionRecord.id",
    )


class SectionRecord(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("course_pk", "section_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_pk: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str] = mapped_column(String(100))
    lecturer: Mapped[str | None] = mapped_column(String(255))
    campus: Mapped[str | None] = mapped_column(String(255))
    priority_label: Mapped[str | None] = mapped_column(String(100))
    parent_section_id: Mapped[str | None] = mapped_column(String(100))

    course: Mapped[CourseRecord] = relationship(back_populates="sections")
    meetings: Mapped[list["MeetingRecord"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="MeetingRecord.id",
    )


class MeetingRecord(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_pk: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int | None]  # 2..8 (8 = Chủ nhật)
    time_unit: Mapped[str] = mapped_column(String(10))
    start_unit: Mapped[int | None]
    end_unit: Mapped[int | None]
    periods: Mapped[list] = mapped_column(JSON, default=list)
    start_minute: Mapped[int | None]
    end_minute: Mapped[int | None]
    location: Mapped[str | None] = mapped_column(String(255))
    delivery: Mapped[str] = mapped_column(String(20), default="unknown")
    schedule_confirmed: Mapped[bool] = mapped_column(default=True)
    component: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    components: Mapped[list] = mapped_column(JSON, default=list)
    raw_text: Mapped[str | None] = mapped_column(String(255))
    raw_weekday: Mapped[str | None] = mapped_column(String(255))
    source_row: Mapped[int | None]
    parse_codes: Mapped[list] = mapped_column(JSON, default=list)

    section: Mapped[SectionRecord] = relationship(back_populates="meetings")