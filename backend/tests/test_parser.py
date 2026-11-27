from datetime import datetime

import pandas as pd
import pytest

from app.schemas.timetable import (
    ComponentType,
    ImportStatus,
    TimeUnit,
    Weekday,
)
from app.services.parser.adapter import import_timetable
from app.services.parser.grouping import parse_component, parse_delivery, split_section_id
from app.services.parser.mapper import suggest_mapping
from app.services.parser.reader import read_spreadsheet
from app.services.parser.timeparse import (
    normalize_text,
    parse_time_range,
    parse_time_unit,
    parse_weekdays,
)

HEADER = [
    "Mã học phần",
    "Tên học phần",
    "Mã lớp học phần",
    "LT/BT/TH",
    "Thứ",
    "Tiết",
    "Phòng",
    "Giảng viên",
]


# ----------------------------- timeparse ----------------------------------- #
def test_normalize_text_handles_nan_and_floats():
    assert normalize_text(float("nan")) == ""
    assert normalize_text(None) == ""
    assert normalize_text(pd.NaT) == ""
    assert normalize_text(7.0) == "7"
    assert normalize_text("  a \u00a0 b ") == "a b"


@pytest.mark.parametrize(
    "value, periods",
    [
        ("1-3", [1, 2, 3]),
        ("Tiết 1,2,3,7,8", [1, 2, 3, 7, 8]),  # giữ khoảng trống 4-6
        ("1-3, 7-9", [1, 2, 3, 7, 8, 9]),
        (7.0, [7]),
        ("10.0", [10]),
        ("Tiết 1-3 (P.301)", [1, 2, 3]),  # số phòng trong ngoặc không bị lẫn vào
    ],
)
def test_period_parsing(value, periods):
    parsed = parse_time_range(value, "Tiết")
    assert parsed.periods == periods
    assert parsed.start == periods[0] and parsed.end == periods[-1]
    assert not parsed.errors


def test_clock_keeps_minutes():
    parsed = parse_time_range("7:30-9:00")
    assert parsed.unit is TimeUnit.CLOCK
    assert (parsed.start_minute, parsed.end_minute) == (450, 540)
    assert parse_time_range("7h30 - 9h").start_minute == 450


def test_excel_date_conversion_is_recovered_with_warning():
    for value in (datetime(2026, 3, 1), datetime(2026, 1, 3), "2026-03-01 00:00:00"):
        parsed = parse_time_range(value, "Tiết")
        assert parsed.periods == [1, 2, 3]
        assert "DATE_CONVERTED" in parsed.warnings


def test_out_of_range_and_invalid():
    assert "TIME_OUT_OF_RANGE" in parse_time_range("Tiết 25", "Tiết").errors
    assert "INVALID_TIME_RANGE" in parse_time_range("5-2", "Tiết").errors
    assert "UNPARSEABLE_TIME" in parse_time_range("abc xyz 12:99".replace("12:99", ""), "Tiết").errors
    assert parse_time_range("Thông báo sau").is_empty


def test_unit_detection_uses_word_boundaries():
    assert parse_time_unit("Cả ngày", None) is TimeUnit.PERIOD  # "ca" trong "cả" không khớp
    assert parse_time_unit("Ca 2", None) is TimeUnit.CA
    assert parse_time_unit("1-3", "Ca học") is TimeUnit.CA
    assert parse_time_unit("Tiết 1-3", "Ca học") is TimeUnit.PERIOD  # nội dung ô ưu tiên


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Thứ 2", [2]),
        ("3", [3]),
        ("Thứ hai", [2]),
        ("Chủ nhật", [8]),
        ("CN", [8]),
        ("Thứ 2, Thứ 4", [2, 4]),
        ("Thứ 2, 4, 6", [2, 4, 6]),
        ("2,4", [2, 4]),
        ("Thứ 2 đến Thứ 4", [2, 3, 4]),
        ("Thứ 2 - 4", [2, 3, 4]),
        ("2-4", [2, 3, 4]),
        ("T2", [2]),
        ("Thứ 2 (tuần 1-8)", [2]),
        ("Thông báo sau", []),
        (float("nan"), []),
    ],
)
def test_weekdays(value, expected):
    assert [int(day) for day in parse_weekdays(value)] == expected


# ------------------------------ grouping ----------------------------------- #
def test_component_and_delivery():
    assert parse_component("LT") is ComponentType.LECTURE
    assert parse_component("TH") is ComponentType.PRACTICE
    assert parse_component("LT+TH") is ComponentType.MIXED
    assert parse_component("LT/BT/TH") is ComponentType.MIXED
    assert parse_component(None) is ComponentType.UNKNOWN
    assert parse_delivery(["Online - Zoom"]).value == "online"
    assert parse_delivery(["Nguyễn Văn Sơn Lê"]).value == "unknown"


def test_split_section_id():
    assert split_section_id("INT1234_01.1") == "INT1234_01"
    assert split_section_id("INT1234_01-TH2") == "INT1234_01"
    assert split_section_id("INT1234_01TH1") == "INT1234_01"
    assert split_section_id("INT1234_01") is None


# ------------------------------ mapper -------------------------------------- #
def test_mapper_handles_d_with_stroke_and_unique_columns():
    frame = pd.DataFrame([HEADER[:6] + ["Địa điểm"] + ["Giảng viên"]], dtype=object)
    mapping, confidence = suggest_mapping(frame, 0)
    assert mapping.location == "Địa điểm"
    assert mapping.course_id == "Mã học phần"
    assert mapping.section_id == "Mã lớp học phần"
    assert mapping.time == "Tiết" and mapping.weekday == "Thứ"
    used = [v for v in mapping.model_dump().values() if v]
    assert len(used) == len(set(used))  # mỗi cột chỉ gán cho một trường


# ------------------------------ end to end --------------------------------- #
@pytest.fixture
def sample_xlsx(tmp_path):
    rows = [
        ["Danh sách lớp học kỳ 1"] + [None] * 7,
        HEADER,
        ["INT1", "Lập trình", "INT1_01", "LT", "Thứ 2", "1-3", "A101", "Nam"],
        [None, None, None, "TH", "Thứ 4", "1,2,3,7,8", None, None],  # ô gộp
        ["INT1", None, "INT1_01.1", "TH", "3", "Tiết 1-3", "B2", "Hoa"],
        ["INT1", None, "INT1_01.2", "TH", "5", datetime(2026, 3, 1), "B2", "Hoa"],  # Excel đổi ngày
        ["INT2", "CSDL", "INT2_01", "LT+TH", "Thứ 2 đến Thứ 4", "Tiết 4-5", "C3", "Minh"],
        ["INT3", "Mạng", "INT3_01", "LT", "Thứ 3", "Tiết 25", "D4", "Lan"],
        ["INT4", "Web", "INT4_01", "LT", "Thông báo sau", "Thông báo sau", None, "Tú"],
        [None] * 8,
        ["Mã học phần", "Tên học phần", "Mã lớp học phần", "LT/BT/TH", "Thứ", "Tiết", "Phòng", "Giảng viên"],
        [None, None, None, None, "Thứ 6", "Tiết 1-2", "E5", None],  # tiêu đề lặp + dòng mồ côi
    ]
    path = tmp_path / "tkb.xlsx"
    pd.DataFrame(rows).to_excel(path, header=False, index=False)
    return path


def test_pipeline_end_to_end(sample_xlsx):
    first = import_timetable(sample_xlsx)
    assert first.status is ImportStatus.NEEDS_CONFIRMATION
    assert first.suggested_mapping.course_id == "Mã học phần"

    result = import_timetable(
        sample_xlsx, mapping=first.suggested_mapping, confirmed_mapping=True, semester="HK1"
    )
    assert result.status is ImportStatus.READY
    courses = {c.course_id: c for c in result.timetable.courses}
    assert set(courses) == {"INT1", "INT2", "INT3", "INT4"}

    # Ô gộp: dòng TH không có mã vẫn thuộc INT1_01, và phòng trống không thành "nan".
    int1 = {s.section_id: s for s in courses["INT1"].sections}
    parent = int1["INT1_01"]
    assert len(parent.meetings) == 2
    th = parent.meetings[1]
    assert th.weekday is Weekday.WEDNESDAY and th.periods == [1, 2, 3, 7, 8]
    assert th.location is None

    # Ghép LT với TH: một nhóm, hai lớp con.
    assert int1["INT1_01.1"].parent_section_id == "INT1_01"
    assert len(courses["INT1"].groups) == 1
    assert courses["INT1"].groups[0].child_section_ids == ["INT1_01.1", "INT1_01.2"]

    # Ô bị Excel đổi ngày được khôi phục và cảnh báo.
    assert int1["INT1_01.2"].meetings[0].periods == [1, 2, 3]
    codes = {i.code for i in result.issues}
    assert "DATE_CONVERTED" in codes

    # "Thứ 2 đến Thứ 4" bung thành 3 buổi, LT+TH là MIXED.
    int2 = courses["INT2"].sections[0]
    assert [int(m.weekday) for m in int2.meetings] == [2, 3, 4]
    assert int2.meetings[0].component is ComponentType.MIXED

    # Dữ liệu xấu không làm sập import mà được báo cáo và bị loại khỏi lịch xếp.
    assert "TIME_OUT_OF_RANGE" in codes
    assert not courses["INT3"].sections[0].meetings[0].schedule_confirmed
    assert "SECTION_NOT_SCHEDULABLE" in codes
    assert "MISSING_WEEKDAY" in codes

    # Dòng tiêu đề lặp bị bỏ qua; dòng mồ côi sau đó KHÔNG bị gán nhầm vào INT4_01.
    assert result.stats["courses"] == 4
    assert result.stats["skipped_rows"] == 1
    skipped = [i for i in result.issues if i.code == "SKIPPED_ROW"]
    assert skipped[0].row == 12
    assert len(courses["INT4"].sections[0].meetings) == 1


def test_unknown_column_fails(sample_xlsx):
    result = import_timetable(
        sample_xlsx,
        mapping={"course_id": "Không có", "section_id": "Mã lớp học phần", "weekday": "Thứ", "time": "Tiết"},
        confirmed_mapping=True,
    )
    assert result.status is ImportStatus.FAILED
    assert result.issues[0].code == "UNKNOWN_COLUMN"


def test_csv_with_semicolon_and_utf8_bom(tmp_path):
    text = "Mã học phần;Mã lớp học phần;Thứ;Tiết\nINT1;INT1_01;Thứ 2;1-3\n"
    path = tmp_path / "tkb.csv"
    path.write_bytes(text.encode("utf-8-sig"))
    frames = read_spreadsheet(path)
    frame = frames["Sheet1"]
    assert frame.shape == (2, 4)
    assert frame.iloc[0, 0] == "Mã học phần"
    result = import_timetable(path, mapping=suggest_mapping(frame, 0)[0], confirmed_mapping=True)
    assert result.status is ImportStatus.READY
    assert result.timetable.courses[0].sections[0].meetings[0].periods == [1, 2, 3]


def test_sheet_selection_by_index_and_name(sample_xlsx):
    assert list(read_spreadsheet(sample_xlsx, sheet_name=0)) == ["Sheet1"]
    assert list(read_spreadsheet(sample_xlsx, sheet_name="Sheet1")) == ["Sheet1"]
    with pytest.raises(ValueError):
        read_spreadsheet(sample_xlsx, sheet_name="Nope")