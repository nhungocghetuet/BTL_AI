from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeliveryMode(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    LECTURE = "LT"
    PRACTICE = "TH"
    EXERCISE = "BT"
    MIXED = "MIXED"  # ô ghi nhiều thành phần, ví dụ "LT+TH"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TimeUnit(str, Enum):
    PERIOD = "period"
    CA = "ca"
    CLOCK = "clock"


class Weekday(int, Enum):
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7
    SUNDAY = 8


class Meeting(StrictModel):
    weekday: Weekday | None = None
    # ge=0: giờ bắt đầu có thể là 0 (00:30) và ô lỗi như "tiết 0" vẫn phải
    # dựng được Meeting để validate.py báo TIME_OUT_OF_RANGE thay vì crash.
    start_unit: int | None = Field(default=None, ge=0)
    end_unit: int | None = Field(default=None, ge=0)
    periods: list[int] = Field(default_factory=list)
    start_minute: int | None = Field(default=None, ge=0)
    end_minute: int | None = Field(default=None, ge=0)
    time_unit: TimeUnit
    location: str | None = None
    delivery: DeliveryMode = DeliveryMode.UNKNOWN
    schedule_confirmed: bool = True
    component: ComponentType = ComponentType.UNKNOWN
    components: list[ComponentType] = Field(default_factory=list)
    raw_text: str | None = None
    raw_weekday: str | None = None
    source_row: int | None = None  # số dòng Excel (1-based)
    parse_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time(self) -> "Meeting":
        if (
            self.start_unit is not None
            and self.end_unit is not None
            and self.start_unit > self.end_unit
        ):
            raise ValueError("start_unit must not exceed end_unit")
        if self.weekday is None:
            self.schedule_confirmed = False
        return self


class SectionOption(StrictModel):
    section_id: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    course_name: str = Field(min_length=1)
    meetings: list[Meeting] = Field(min_length=1)
    lecturer: str | None = None
    campus: str | None = None
    priority_label: str | None = None
    parent_section_id: str | None = None  # lớp cha nếu đây là nhóm con TH/BT


class SectionGroup(StrictModel):
    group_id: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    parent_section_id: str = Field(min_length=1)
    child_section_ids: list[str] = Field(default_factory=list)


class Course(StrictModel):
    course_id: str = Field(min_length=1)
    course_name: str = Field(min_length=1)
    sections: list[SectionOption] = Field(min_length=1)
    groups: list[SectionGroup] = Field(default_factory=list)


class TimetableData(StrictModel):
    semester: str | None = None
    time_unit: TimeUnit
    courses: list[Course] = Field(min_length=1)


class ColumnMapping(StrictModel):
    course_id: str | None = None
    course_name: str | None = None
    section_id: str | None = None
    weekday: str | None = None
    time: str | None = None
    location: str | None = None
    lecturer: str | None = None
    component: str | None = None
    delivery: str | None = None


class MappingSuggestion(StrictModel):
    canonical_field: str
    source_column: str | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str | None = None
    requires_confirmation: bool = False


class ImportIssue(StrictModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    sheet: str | None = None
    row: int | None = None
    source_text: str | None = None
    # Mặc định "error": validate_mapping tạo MISSING_MAPPING / UNKNOWN_COLUMN
    # không truyền severity và adapter dựa vào đó để trả FAILED.
    severity: Literal["error", "warning", "info"] = "error"


class ImportStatus(str, Enum):
    READY = "ready"
    NEEDS_MAPPING = "needs_mapping"
    NEEDS_CONFIRMATION = "needs_confirmation"
    FAILED = "failed"


class TimetableImportResult(StrictModel):
    status: ImportStatus
    timetable: TimetableData | None = None
    suggested_mapping: ColumnMapping | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    preview: list[dict[str, object]] = Field(default_factory=list)
    issues: list[ImportIssue] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)