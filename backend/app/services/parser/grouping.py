"""Gom các dòng thô thành Course -> SectionOption -> Meeting."""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from app.schemas.timetable import (
    ColumnMapping,
    ComponentType,
    Course,
    DeliveryMode,
    ImportIssue,
    Meeting,
    SectionGroup,
    SectionOption,
    TimetableData,
    TimeUnit,
)
from app.services.parser.mapper import normalize_header
from app.services.parser.timeparse import (
    fold_text,
    is_blank,
    normalize_text,
    parse_time_range,
    parse_time_unit,
    parse_weekdays,
)

_FIELDS = (
    "course_id",
    "course_name",
    "section_id",
    "weekday",
    "time",
    "location",
    "lecturer",
    "component",
    "delivery",
)
# Dòng có ít nhất một ô trong các cột này được coi là "dòng buổi học".
_SCHEDULE_FIELDS = ("weekday", "time", "component", "location", "delivery")


# --------------------------------------------------------------------------- #
# Tiện ích header / thành phần / hình thức
# --------------------------------------------------------------------------- #
def original_headers(frame: pd.DataFrame, header_row: int) -> list[str]:
    return [normalize_text(value) for value in frame.iloc[header_row].tolist()]


def build_column_index(headers: Iterable[str]) -> dict[str, int]:
    """Tên cột (đã bỏ dấu) -> vị trí cột đầu tiên. Cột trùng tên lấy cột đầu."""
    index: dict[str, int] = {}
    for position, header in enumerate(headers):
        key = normalize_header(header)
        if key and key not in index:
            index[key] = position
    return index


def find_original_column(
    frame: pd.DataFrame,
    header_row: int,
    mapped_name: str | None,
) -> str | None:
    if mapped_name is None:
        return None
    key = normalize_header(mapped_name)
    for header in original_headers(frame, header_row):
        if normalize_header(header) == key:
            return header
    return None


_COMPONENT_RE = re.compile(
    r"(?<![a-z])(lt|bt|th|ly thuyet|bai tap|thuc hanh)(?![a-z])"
)
_COMPONENT_MAP = {
    "lt": ComponentType.LECTURE,
    "ly thuyet": ComponentType.LECTURE,
    "bt": ComponentType.EXERCISE,
    "bai tap": ComponentType.EXERCISE,
    "th": ComponentType.PRACTICE,
    "thuc hanh": ComponentType.PRACTICE,
}


def parse_components(value: object) -> list[ComponentType]:
    """"LT+TH" -> [LECTURE, PRACTICE]; "LT/BT/TH" -> cả ba; rỗng -> []."""
    text = fold_text(value)
    if not text:
        return []
    found = [_COMPONENT_MAP[m.group(1)] for m in _COMPONENT_RE.finditer(text)]
    unique = list(dict.fromkeys(found))
    return unique or [ComponentType.OTHER]


def primary_component(components: list[ComponentType]) -> ComponentType:
    if not components:
        return ComponentType.UNKNOWN
    if len(components) == 1:
        return components[0]
    return ComponentType.MIXED


def parse_component(value: object) -> ComponentType:
    return primary_component(parse_components(value))


_ONLINE_RE = re.compile(
    r"(?<![a-z])(online|onl|truc tuyen|e-?learning|zoom|ms ?teams|lms)(?![a-z])"
)
_OFFLINE_RE = re.compile(r"(?<![a-z])(offline|truc tiep|tai lop)(?![a-z])")


def parse_delivery(row_values: Iterable[object]) -> DeliveryMode:
    """Chỉ nên truyền các ô liên quan (hình thức, phòng, thời gian...), không phải
    cả dòng, để tránh khớp nhầm với tên giảng viên hoặc tên môn."""
    text = " ".join(fold_text(value) for value in row_values)
    if _ONLINE_RE.search(text):
        return DeliveryMode.ONLINE
    if _OFFLINE_RE.search(text):
        return DeliveryMode.OFFLINE
    return DeliveryMode.UNKNOWN


# --------------------------------------------------------------------------- #
# Ghép lớp lý thuyết với thực hành
# --------------------------------------------------------------------------- #
_SUBGROUP_PATTERNS = (
    re.compile(r"^(?P<base>.*\d)\.\d+$"),  # INT1234_01.1
    re.compile(
        r"^(?P<base>.+?)(?:[\s._\-/]+(?:LT|BT|TH)\d*|(?<=\d)(?:LT|BT|TH)\d*)$",
        re.IGNORECASE,
    ),  # INT1234_01-TH2, INT1234_01TH1
)


def split_section_id(section_id: str) -> str | None:
    """Trả về mã lớp cha nếu ``section_id`` trông như nhóm con (TH/BT), ngược lại None."""
    for pattern in _SUBGROUP_PATTERNS:
        match = pattern.match(section_id)
        if match and match.group("base") != section_id:
            return match.group("base")
    return None


def _link_sections(section_ids: list[str]) -> dict[str, str]:
    """{mã nhóm con: mã lớp cha}. Chỉ nối khi lớp cha thật sự có trong file."""
    known = set(section_ids)
    candidates = {}
    for section_id in section_ids:
        parent = split_section_id(section_id)
        if parent and parent in known:
            candidates[section_id] = parent
    # Chỉ nối một cấp: lớp cha không được là nhóm con của lớp khác.
    return {child: parent for child, parent in candidates.items() if parent not in candidates}


# --------------------------------------------------------------------------- #
# Chuyển DataFrame thô -> TimetableData
# --------------------------------------------------------------------------- #
@dataclass
class _SectionAcc:
    course_id: str
    section_id: str
    course_name: str = ""
    lecturer: str = ""
    meetings: list[Meeting] = field(default_factory=list)
    keys: set[tuple] = field(default_factory=set)


def _issue(
    code: str,
    message: str,
    sheet: str | None,
    severity: str,
    row: int | None = None,
    source_text: str | None = None,
) -> ImportIssue:
    return ImportIssue(
        code=code,
        message=message,
        sheet=sheet,
        row=row,
        source_text=source_text,
        severity=severity,  # type: ignore[arg-type]
    )


def frame_to_timetable(
    frame: pd.DataFrame,
    header_row: int,
    mapping: ColumnMapping,
    semester: str | None = None,
    sheet: str | None = None,
) -> tuple[TimetableData, list[ImportIssue]]:
    """Trả về (timetable, issues). Raise ValueError khi không dựng được dữ liệu."""

    index = build_column_index(original_headers(frame, header_row))
    columns: dict[str, int | None] = {}
    for name in _FIELDS:
        source = getattr(mapping, name, None)
        if source is None or not str(source).strip():
            columns[name] = None
            continue
        position = index.get(normalize_header(source))
        if position is None:
            raise ValueError(f"Cột '{source}' (trường {name}) không tồn tại trong sheet")
        columns[name] = position
    for required in ("course_id", "section_id"):
        if columns[required] is None:
            raise ValueError(f"Thiếu ánh xạ cho cột bắt buộc: {required}")

    def cell(values: tuple, name: str) -> object:
        position = columns[name]
        if position is None or position >= len(values):
            return None
        return values[position]

    time_hint = mapping.time
    header_key = normalize_header(mapping.course_id)
    issues: list[ImportIssue] = []
    sections: dict[tuple[str, str], _SectionAcc] = {}
    time_units: Counter[TimeUnit] = Counter()
    last_course = last_section = ""
    filled_rows = duplicates = 0

    first_data = header_row + 1
    for offset, values in enumerate(
        frame.iloc[first_data:].itertuples(index=False, name=None)
    ):
        excel_row = first_data + offset + 1  # 1-based như trong Excel
        if all(is_blank(value) for value in values):
            last_course = last_section = ""  # ô gộp không vắt qua dòng trống
            continue

        course_id = normalize_text(cell(values, "course_id"))
        section_id = normalize_text(cell(values, "section_id"))
        if course_id and normalize_header(course_id) == header_key:
            last_course = last_section = ""  # dòng tiêu đề lặp lại ở đầu mỗi trang
            continue

        has_schedule = any(not is_blank(cell(values, n)) for n in _SCHEDULE_FIELDS)

        # Ô gộp: mã chỉ ghi ở dòng đầu, các dòng LT/BT/TH sau để trống.
        if not course_id:
            if has_schedule and last_course:
                course_id = last_course
                section_id = section_id or last_section
                filled_rows += 1
        elif not section_id and course_id == last_course and has_schedule:
            section_id = last_section
            filled_rows += 1

        if not course_id or not section_id:
            if has_schedule:
                issues.append(
                    _issue(
                        "SKIPPED_ROW",
                        f"Dòng {excel_row} bị bỏ qua: thiếu mã học phần hoặc mã lớp học phần",
                        sheet,
                        "warning",
                        row=excel_row,
                    )
                )
            continue
        last_course, last_section = course_id, section_id

        acc = sections.setdefault((course_id, section_id), _SectionAcc(course_id, section_id))
        acc.course_name = acc.course_name or normalize_text(cell(values, "course_name"))
        acc.lecturer = acc.lecturer or normalize_text(cell(values, "lecturer"))

        time_raw = cell(values, "time")
        weekday_raw = cell(values, "weekday")
        parsed = parse_time_range(time_raw, time_hint)
        weekdays = parse_weekdays(weekday_raw) or [None]
        location = normalize_text(cell(values, "location")) or None
        components = parse_components(cell(values, "component"))
        component = primary_component(components)
        delivery = parse_delivery(
            cell(values, n) for n in ("delivery", "location", "time", "weekday", "component")
        )
        if not is_blank(time_raw) and not parsed.is_empty:
            time_units[parsed.unit] += 1

        for weekday in weekdays:
            key = (
                weekday,
                tuple(parsed.periods),
                parsed.start,
                parsed.end,
                parsed.start_minute,
                parsed.end_minute,
                location,
                component,
            )
            if key in acc.keys:
                duplicates += 1
                continue
            acc.keys.add(key)
            acc.meetings.append(
                Meeting(
                    weekday=weekday,
                    start_unit=parsed.start,
                    end_unit=parsed.end,
                    periods=parsed.periods,
                    start_minute=parsed.start_minute,
                    end_minute=parsed.end_minute,
                    time_unit=parsed.unit,
                    location=location,
                    delivery=delivery,
                    schedule_confirmed=(
                        weekday is not None
                        and parsed.start is not None
                        and parsed.end is not None
                        and not parsed.errors
                    ),
                    component=component,
                    components=components,
                    raw_text=normalize_text(time_raw) or None,
                    raw_weekday=normalize_text(weekday_raw) or None,
                    source_row=excel_row,
                    parse_codes=parsed.warnings + parsed.errors,
                )
            )

    if filled_rows:
        issues.append(
            _issue(
                "FILLED_MERGED_CELLS",
                f"Đã tự điền mã học phần/lớp từ dòng trên cho {filled_rows} dòng (ô gộp)",
                sheet,
                "info",
            )
        )
    if duplicates:
        issues.append(
            _issue(
                "DUPLICATE_MEETING_DROPPED",
                f"Đã loại {duplicates} buổi học trùng lặp hoàn toàn",
                sheet,
                "info",
            )
        )

    if time_units:
        detected_unit = time_units.most_common(1)[0][0]
        if len(time_units) > 1:
            names = ", ".join(f"{unit.value}: {count}" for unit, count in time_units.items())
            issues.append(
                _issue(
                    "MIXED_TIME_UNITS",
                    f"File dùng nhiều đơn vị thời gian ({names}); lấy '{detected_unit.value}' làm chính",
                    sheet,
                    "warning",
                )
            )
    else:
        detected_unit = parse_time_unit("", time_hint)

    accs_by_course: dict[str, list[_SectionAcc]] = {}
    for acc in sections.values():
        if acc.meetings:
            accs_by_course.setdefault(acc.course_id, []).append(acc)

    courses: list[Course] = []
    for course_id, accs in accs_by_course.items():
        course_name = next((a.course_name for a in accs if a.course_name), course_id)
        links = _link_sections([a.section_id for a in accs])
        options = [
            SectionOption(
                section_id=a.section_id,
                course_id=course_id,
                course_name=course_name,
                meetings=a.meetings,
                lecturer=a.lecturer or None,
                parent_section_id=links.get(a.section_id),
            )
            for a in accs
        ]
        children: dict[str, list[str]] = {}
        for child, parent in links.items():
            children.setdefault(parent, []).append(child)
        groups = [
            SectionGroup(
                group_id=option.section_id,
                course_id=course_id,
                parent_section_id=option.section_id,
                child_section_ids=children.get(option.section_id, []),
            )
            for option in options
            if option.parent_section_id is None
        ]
        courses.append(
            Course(course_id=course_id, course_name=course_name, sections=options, groups=groups)
        )

    if not courses:
        raise ValueError("No valid courses/classes found after applying column mapping")

    return (
        TimetableData(semester=semester, time_unit=detected_unit, courses=courses),
        issues,
    )