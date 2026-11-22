"""Kiểm tra tính hợp lệ của ánh xạ cột, tạo dữ liệu xem trước và phát hiện lỗi/trùng lịch thời khóa biểu."""

from datetime import date, datetime, time

import pandas as pd

from app.schemas.timetable import (
    ColumnMapping,
    DeliveryMode,
    ImportIssue,
    Meeting,
    TimetableData,
    TimeUnit,
)
from app.services.parser.mapper import normalize_header
from app.services.parser.timeparse import (
    MAX_CA,
    MAX_PERIOD,
    fold_text,
    is_blank,
    normalize_text,
)

REQUIRED_MAPPING_FIELDS = ("course_id", "section_id", "weekday", "time")


# --------------------------------------------------------------------------- #
# Kiểm tra ánh xạ cột
# --------------------------------------------------------------------------- #
def validate_mapping(
    mapping: ColumnMapping,
    frame: pd.DataFrame,
    header_row: int,
    sheet: str,
) -> list[ImportIssue]:
    issues: list[ImportIssue] = []
    headers = [normalize_text(value) for value in frame.iloc[header_row].tolist()]
    header_lookup = {normalize_header(h): h for h in headers if h}
    used: dict[str, str] = {}

    for field in ColumnMapping.model_fields:
        source = getattr(mapping, field)
        required = field in REQUIRED_MAPPING_FIELDS
        if not source:
            if required:
                issues.append(
                    ImportIssue(
                        code="MISSING_MAPPING",
                        message=f"Chưa xác định cột bắt buộc: {field}",
                        sheet=sheet,
                    )
                )
            continue

        key = normalize_header(source)
        if key not in header_lookup:
            issues.append(
                ImportIssue(
                    code="UNKNOWN_COLUMN",
                    message=f"Cột {source} không tồn tại trong sheet {sheet}",
                    sheet=sheet,
                    source_text=source,
                )
            )
        elif key in used:
            issues.append(
                ImportIssue(
                    code="DUPLICATE_COLUMN",
                    message=f"Cột {source} được dùng cho cả '{used[key]}' và '{field}'",
                    sheet=sheet,
                    source_text=source,
                    severity="warning",
                )
            )
        else:
            used[key] = field
    return issues


# --------------------------------------------------------------------------- #
# Xem trước
# --------------------------------------------------------------------------- #
def _jsonable(value: object) -> object:
    if is_blank(value):
        return None
    if isinstance(value, (datetime, date, time)):
        return normalize_text(value)
    if hasattr(value, "item"):  # numpy scalar
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def get_preview(
    frame: pd.DataFrame, header_row: int, limit: int = 20
) -> list[dict[str, object]]:
    """Tối đa ``limit`` dòng dữ liệu không trống; ``__row`` là số dòng Excel (1-based)."""
    headers = [normalize_text(value) for value in frame.iloc[header_row].tolist()]
    records: list[dict[str, object]] = []
    for row_index in range(header_row + 1, len(frame)):
        if len(records) >= limit:
            break
        row = frame.iloc[row_index]
        if all(is_blank(value) for value in row.tolist()):
            continue
        record: dict[str, object] = {"__row": row_index + 1}
        for column_index, column in enumerate(headers):
            if not column:
                continue
            name = column if column not in record else f"{column} ({column_index + 1})"
            record[name] = _jsonable(row.iloc[column_index])
        records.append(record)
    return records


# --------------------------------------------------------------------------- #
# Kiểm tra dữ liệu đã chuẩn hóa
# --------------------------------------------------------------------------- #
_TIME_ERROR_CODES = {"INVALID_TIME_RANGE", "TIME_OUT_OF_RANGE", "UNPARSEABLE_TIME"}


def _issue(
    code: str,
    message: str,
    sheet: str | None,
    row: int | None,
    source_text: str | None = None,
    severity: str = "warning",
) -> ImportIssue:
    return ImportIssue(
        code=code,
        message=message,
        sheet=sheet,
        row=row,
        source_text=source_text,
        severity=severity,  # type: ignore[arg-type]
    )


def _limit_text(unit: TimeUnit) -> str:
    if unit is TimeUnit.CA:
        return f"ca 1-{MAX_CA}"
    if unit is TimeUnit.CLOCK:
        return "giờ 0-23, phút 0-59"
    return f"tiết 1-{MAX_PERIOD}"


def _parse_code_issue(
    code: str, meeting: Meeting, label: str, sheet: str | None
) -> ImportIssue | None:
    raw = meeting.raw_text
    row = meeting.source_row
    if code == "DATE_CONVERTED":
        shown = f"{meeting.start_unit}-{meeting.end_unit}"
        return _issue(
            code,
            f"{label}: ô thời gian '{raw}' bị Excel tự đổi thành ngày, đã khôi phục "
            f"thành {shown}. Hãy kiểm tra lại (nên định dạng cột là Text)",
            sheet,
            row,
            raw,
        )
    if code == "INVALID_TIME_RANGE":
        return _issue(
            code,
            f"{label}: thời gian '{raw}' có điểm bắt đầu lớn hơn điểm kết thúc, buổi học này bị bỏ qua khi xếp lịch",
            sheet,
            row,
            raw,
        )
    if code == "TIME_OUT_OF_RANGE":
        return _issue(
            code,
            f"{label}: thời gian '{raw}' nằm ngoài khoảng hợp lệ ({_limit_text(meeting.time_unit)}), buổi học này bị bỏ qua khi xếp lịch",
            sheet,
            row,
            raw,
        )
    if code == "UNPARSEABLE_TIME":
        return _issue(
            code,
            f"{label}: không đọc được thời gian '{raw}', buổi học này bị bỏ qua khi xếp lịch",
            sheet,
            row,
            raw,
        )
    return None


def _overlap(a: Meeting, b: Meeting) -> bool:
    if a.time_unit != b.time_unit or a.weekday != b.weekday:
        return False
    if a.time_unit is TimeUnit.CLOCK:
        if None in (a.start_minute, a.end_minute, b.start_minute, b.end_minute):
            return False
        return a.start_minute < b.end_minute and b.start_minute < a.end_minute  # type: ignore[operator]
    slots_a = set(a.periods) or set(range(a.start_unit or 0, (a.end_unit or -1) + 1))
    slots_b = set(b.periods) or set(range(b.start_unit or 0, (b.end_unit or -1) + 1))
    return bool(slots_a & slots_b)


def validate_timetable(
    timetable: TimetableData, sheet: str | None = None
) -> list[ImportIssue]:
    """Kiểm tra từng buổi học và từng lớp. Lỗi dữ liệu là cảnh báo (không chặn import)
    vì buổi học lỗi đã được đánh dấu ``schedule_confirmed=False``."""
    issues: list[ImportIssue] = []

    for course in timetable.courses:
        for section in course.sections:
            confirmed: list[Meeting] = []
            for meeting in section.meetings:
                label = f"{course.course_id}/{section.section_id}"
                online = meeting.delivery is DeliveryMode.ONLINE

                for code in meeting.parse_codes:
                    issue = _parse_code_issue(code, meeting, label, sheet)
                    if issue:
                        issues.append(issue)

                if meeting.weekday is None and not online:
                    raw = meeting.raw_weekday
                    if raw and "thong bao" not in fold_text(raw):
                        issues.append(
                            _issue(
                                "UNKNOWN_WEEKDAY",
                                f"{label}: không nhận dạng được thứ '{raw}'",
                                sheet,
                                meeting.source_row,
                                raw,
                            )
                        )
                    else:
                        issues.append(
                            _issue(
                                "MISSING_WEEKDAY",
                                f"{label}: thiếu thông tin thứ học",
                                sheet,
                                meeting.source_row,
                                raw,
                            )
                        )

                if (
                    meeting.start_unit is None
                    and not online
                    and not (_TIME_ERROR_CODES & set(meeting.parse_codes))
                ):
                    issues.append(
                        _issue(
                            "MISSING_TIME",
                            f"{label}: thiếu thông tin tiết/ca/giờ học",
                            sheet,
                            meeting.source_row,
                            meeting.raw_text,
                        )
                    )

                if meeting.schedule_confirmed:
                    confirmed.append(meeting)

            for i, first in enumerate(confirmed):
                for second in confirmed[i + 1 :]:
                    if _overlap(first, second):
                        issues.append(
                            _issue(
                                "OVERLAP_IN_SECTION",
                                f"{course.course_id}/{section.section_id}: hai buổi học trùng giờ "
                                f"(dòng {first.source_row} và {second.source_row})",
                                sheet,
                                second.source_row,
                            )
                        )

            all_online = all(m.delivery is DeliveryMode.ONLINE for m in section.meetings)
            if not confirmed and not all_online:
                issues.append(
                    _issue(
                        "SECTION_NOT_SCHEDULABLE",
                        f"{course.course_id}/{section.section_id}: không có buổi học nào đủ "
                        "thứ và tiết để xếp lịch",
                        sheet,
                        section.meetings[0].source_row if section.meetings else None,
                    )
                )
    return issues