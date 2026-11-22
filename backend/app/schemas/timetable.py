"""Schema chuẩn hóa thời khóa biểu, dùng chung cho parser, optimizer và API."""

from enum import Enum, IntEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TimeUnit(str, Enum):
    PERIOD = "period"  # tiết
    CA = "ca"  # ca học
    CLOCK = "clock"  # giờ:phút


class Weekday(IntEnum):
    """Quy ước của trường: Thứ 2 = 2 ... Thứ 7 = 7, Chủ nhật = 8."""

    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7
    SUNDAY = 8


class ComponentType(str, Enum):
    LECTURE = "LT"
    EXERCISE = "BT"
    PRACTICE = "TH"
    MIXED = "MIXED"  # ví dụ "LT+TH", "LT/BT/TH"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class DeliveryMode(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ImportStatus(str, Enum):
    NEEDS_MAPPING = "needs_mapping"
    NEEDS_CONFIRMATION = "needs_confirmation"
    FAILED = "failed"
    READY = "ready"


class ColumnMapping(BaseModel):
    """Tên cột (đúng như trong file) tương ứng với từng trường chuẩn."""

    course_id: str | None = None
    course_name: str | None = None
    section_id: str | None = None
    weekday: str | None = None
    time: str | None = None
    location: str | None = None
    lecturer: str | None = None
    component: str | None = None
    delivery: str | None = None


class ImportIssue(BaseModel):
    code: str
    message: str
    sheet: str | None = None
    row: int | None = None  # số dòng 1-based như hiển thị trong Excel
    source_text: str | None = None
    severity: Literal["error", "warning", "info"] = "error"


class Meeting(BaseModel):
    """Một buổi học lặp hàng tuần của một lớp học phần."""

    weekday: Weekday | None = None
    # Với PERIOD/CA: số tiết/ca đầu và cuối. Với CLOCK: giờ bắt đầu/kết thúc.
    start_unit: int | None = None
    end_unit: int | None = None
    # Danh sách tiết/ca thực sự học (giữ nguyên khoảng trống, vd 1,2,3,7,8).
    periods: list[int] = Field(default_factory=list)
    # Chỉ dùng cho CLOCK: số phút tính từ 00:00.
    start_minute: int | None = None
    end_minute: int | None = None
    time_unit: TimeUnit = TimeUnit.PERIOD
    location: str | None = None
    delivery: DeliveryMode = DeliveryMode.UNKNOWN
    schedule_confirmed: bool = False
    component: ComponentType = ComponentType.UNKNOWN
    components: list[ComponentType] = Field(default_factory=list)
    raw_text: str | None = None  # nội dung gốc của ô thời gian
    raw_weekday: str | None = None  # nội dung gốc của ô thứ
    source_row: int | None = None  # dòng 1-based trong file
    parse_codes: list[str] = Field(default_factory=list)  # cảnh báo/lỗi khi phân tích


class SectionOption(BaseModel):
    section_id: str
    course_id: str
    course_name: str
    meetings: list[Meeting]
    lecturer: str | None = None
    # Nếu là nhóm thực hành/bài tập con của một lớp học phần khác
    # (vd "INT1234_01.1" thuộc "INT1234_01") thì trỏ tới lớp cha.
    parent_section_id: str | None = None


class SectionGroup(BaseModel):
    """Một phương án đăng ký hoàn chỉnh cho môn học.

    Khi chọn nhóm này, sinh viên học tất cả buổi của ``parent_section_id`` và
    đúng MỘT lớp trong ``child_section_ids`` (nếu danh sách không rỗng).
    """

    group_id: str
    course_id: str
    parent_section_id: str
    child_section_ids: list[str] = Field(default_factory=list)


class Course(BaseModel):
    course_id: str
    course_name: str
    sections: list[SectionOption]
    groups: list[SectionGroup] = Field(default_factory=list)


class TimetableData(BaseModel):
    semester: str | None = None
    time_unit: TimeUnit = TimeUnit.PERIOD
    courses: list[Course]


class TimetableImportResult(BaseModel):
    status: ImportStatus
    timetable: TimetableData | None = None
    suggested_mapping: ColumnMapping | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    preview: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[ImportIssue] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)