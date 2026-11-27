"""Thao tác CSDL: lưu file upload và lưu/đọc thời khóa biểu đã chuẩn hóa."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    UPLOAD_STATUS_CONFIRMED,
    CourseRecord,
    MeetingRecord,
    SectionRecord,
    UploadedFile,
)
from app.schemas.timetable import (
    ColumnMapping,
    ComponentType,
    Course,
    DeliveryMode,
    Meeting,
    SectionGroup,
    SectionOption,
    TimetableData,
    TimeUnit,
    Weekday,
)


# --------------------------------------------------------------------------- #
# File upload
# --------------------------------------------------------------------------- #
def create_uploaded_file(
    db: Session,
    *,
    file_id: str,
    original_name: str,
    stored_path: str,
    size_bytes: int,
    sheet_name: str | None = None,
    header_row: int | None = None,
) -> UploadedFile:
    record = UploadedFile(
        id=file_id,
        original_name=original_name,
        stored_path=stored_path,
        size_bytes=size_bytes,
        sheet_name=sheet_name,
        header_row=header_row,
    )
    db.add(record)
    db.commit()
    return record


def get_uploaded_file(db: Session, file_id: str) -> UploadedFile | None:
    return db.get(UploadedFile, file_id)


def delete_uploaded_file(db: Session, file_id: str) -> str | None:
    """Xóa bản ghi (kèm toàn bộ môn/lớp/buổi học). Trả về đường dẫn file gốc để
    nơi gọi tự xóa trên đĩa, hoặc None nếu không có file_id này."""
    record = db.get(UploadedFile, file_id)
    if record is None:
        return None
    stored_path = record.stored_path
    db.delete(record)
    db.commit()
    return stored_path


# --------------------------------------------------------------------------- #
# Thời khóa biểu
# --------------------------------------------------------------------------- #
def _meeting_record(meeting: Meeting) -> MeetingRecord:
    return MeetingRecord(
        weekday=meeting.weekday.value if meeting.weekday is not None else None,
        time_unit=meeting.time_unit.value,
        start_unit=meeting.start_unit,
        end_unit=meeting.end_unit,
        periods=list(meeting.periods),
        start_minute=meeting.start_minute,
        end_minute=meeting.end_minute,
        location=meeting.location,
        delivery=meeting.delivery.value,
        schedule_confirmed=meeting.schedule_confirmed,
        component=meeting.component.value,
        components=[c.value for c in meeting.components],
        raw_text=meeting.raw_text,
        raw_weekday=meeting.raw_weekday,
        source_row=meeting.source_row,
        parse_codes=list(meeting.parse_codes),
    )


def save_timetable(
    db: Session,
    file_id: str,
    timetable: TimetableData,
    mapping: ColumnMapping,
    *,
    sheet_name: str | None = None,
    header_row: int | None = None,
) -> UploadedFile:
    """Ghi (hoặc ghi đè) thời khóa biểu của ``file_id`` trong một giao dịch.

    Xác nhận lại mapping sẽ thay toàn bộ dữ liệu cũ của file đó.
    Raise LookupError nếu file_id không tồn tại.
    """
    upload = db.get(UploadedFile, file_id)
    if upload is None:
        raise LookupError(file_id)

    try:
        upload.courses.clear()
        db.flush()

        for course in timetable.courses:
            course_record = CourseRecord(
                course_id=course.course_id, course_name=course.course_name
            )
            for section in course.sections:
                course_record.sections.append(
                    SectionRecord(
                        section_id=section.section_id,
                        lecturer=section.lecturer,
                        campus=section.campus,
                        priority_label=section.priority_label,
                        parent_section_id=section.parent_section_id,
                        meetings=[_meeting_record(m) for m in section.meetings],
                    )
                )
            upload.courses.append(course_record)

        upload.status = UPLOAD_STATUS_CONFIRMED
        upload.mapping = mapping.model_dump()
        upload.semester = timetable.semester
        upload.time_unit = timetable.time_unit.value
        upload.sheet_name = sheet_name if sheet_name is not None else upload.sheet_name
        upload.header_row = header_row if header_row is not None else upload.header_row
        upload.confirmed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return upload


def _to_meeting(record: MeetingRecord) -> Meeting:
    return Meeting(
        weekday=Weekday(record.weekday) if record.weekday is not None else None,
        start_unit=record.start_unit,
        end_unit=record.end_unit,
        periods=list(record.periods or []),
        start_minute=record.start_minute,
        end_minute=record.end_minute,
        time_unit=TimeUnit(record.time_unit),
        location=record.location,
        delivery=DeliveryMode(record.delivery),
        schedule_confirmed=record.schedule_confirmed,
        component=ComponentType(record.component),
        components=[ComponentType(c) for c in (record.components or [])],
        raw_text=record.raw_text,
        raw_weekday=record.raw_weekday,
        source_row=record.source_row,
        parse_codes=list(record.parse_codes or []),
    )


def _to_course(record: CourseRecord) -> Course:
    options = [
        SectionOption(
            section_id=s.section_id,
            course_id=record.course_id,
            course_name=record.course_name,
            meetings=[_to_meeting(m) for m in s.meetings],
            lecturer=s.lecturer,
            campus=s.campus,
            priority_label=s.priority_label,
            parent_section_id=s.parent_section_id,
        )
        for s in record.sections
    ]
    children: dict[str, list[str]] = {}
    for option in options:
        if option.parent_section_id:
            children.setdefault(option.parent_section_id, []).append(option.section_id)
    # Giống grouping.py: mỗi lớp cha (không có parent) là một nhóm.
    groups = [
        SectionGroup(
            group_id=option.section_id,
            course_id=record.course_id,
            parent_section_id=option.section_id,
            child_section_ids=children.get(option.section_id, []),
        )
        for option in options
        if option.parent_section_id is None
    ]
    return Course(
        course_id=record.course_id,
        course_name=record.course_name,
        sections=options,
        groups=groups,
    )


def get_timetable(db: Session, file_id: str) -> TimetableData | None:
    """Dựng lại TimetableData đã lưu. None nếu file chưa tồn tại hoặc chưa xác nhận."""
    stmt = (
        select(UploadedFile)
        .where(UploadedFile.id == file_id)
        .options(
            selectinload(UploadedFile.courses)
            .selectinload(CourseRecord.sections)
            .selectinload(SectionRecord.meetings)
        )
    )
    upload = db.execute(stmt).scalar_one_or_none()
    if upload is None or upload.status != UPLOAD_STATUS_CONFIRMED or not upload.courses:
        return None
    return TimetableData(
        semester=upload.semester,
        time_unit=TimeUnit(upload.time_unit),
        courses=[_to_course(c) for c in upload.courses],
    )