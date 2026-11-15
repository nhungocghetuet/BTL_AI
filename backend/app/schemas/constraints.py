from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Weekday(str, Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class TimeUnit(str, Enum):
    PERIOD = "period"
    CA = "ca"


class PreferenceMode(str, Enum):
    PREFER = "prefer"
    AVOID = "avoid"


class ConstraintStrength(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class IssueCode(str, Enum):
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    HARD_NOT_SUPPORTED = "HARD_NOT_SUPPORTED"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    UNKNOWN_COURSE = "UNKNOWN_COURSE"


class TimeRange(StrictModel):
    """Inclusive range in the unit used by the uploaded timetable."""

    unit: TimeUnit
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> "TimeRange":
        if self.start > self.end:
            raise ValueError("start must be less than or equal to end")
        return self


class TimeTarget(StrictModel):
    days: list[Weekday] = Field(default_factory=list)
    time_range: TimeRange | None = None

    @model_validator(mode="after")
    def require_target(self) -> "TimeTarget":
        if not self.days and self.time_range is None:
            raise ValueError("A time target must specify a day or time range")
        return self


class WeightedDayOff(StrictModel):
    day: Weekday
    weight: int = Field(default=3, ge=1, le=5)


class HardTimeRule(StrictModel):
    """A required or forbidden global day/time target."""

    mode: PreferenceMode
    target: TimeTarget

class WeightedTimeAvoidance(StrictModel):
    target: TimeTarget
    weight: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def require_time_component(self) -> "WeightedTimeAvoidance":
        if self.target.time_range is None:
            raise ValueError("A time avoidance must specify a time range")
        return self


class CourseTimeRule(StrictModel):
    """A course-specific rule; the parser service must confirm one meeting per week."""

    course_id: str = Field(min_length=1)
    mode: PreferenceMode
    strength: ConstraintStrength
    target: TimeTarget
    weight: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def validate_weight(self) -> "CourseTimeRule":
        if self.strength is ConstraintStrength.SOFT and self.weight is None:
            raise ValueError("A soft course rule requires a weight")
        if self.strength is ConstraintStrength.HARD and self.weight is not None:
            raise ValueError("A hard course rule must not have a weight")
        return self


class ObjectiveWeights(StrictModel):
    compact_days: int = Field(default=0, ge=0, le=5)
    avoid_gaps: int = Field(default=0, ge=0, le=5)


class OptimizerConstraints(StrictModel):
    """User preferences that map directly to CP-SAT constraints or objective terms."""

    hard_days_off: list[Weekday] = Field(default_factory=list)
    hard_time_rules: list[HardTimeRule] = Field(default_factory=list)
    soft_days_off: list[WeightedDayOff] = Field(default_factory=list)
    avoid_times: list[WeightedTimeAvoidance] = Field(default_factory=list)
    per_course: list[CourseTimeRule] = Field(default_factory=list)
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)


class PreferenceIssue(StrictModel):
    code: IssueCode
    message: str = Field(min_length=1)
    source_text: str = ""


class ParseStatus(str, Enum):
    OK = "ok"
    NEEDS_CLARIFICATION = "needs_clarification"


class PreferenceParseResult(StrictModel):
    status: ParseStatus
    constraints: OptimizerConstraints = Field(default_factory=OptimizerConstraints)
    issues: list[PreferenceIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "PreferenceParseResult":
        has_issues = bool(self.issues)
        needs_clarification = self.status is ParseStatus.NEEDS_CLARIFICATION
        if has_issues != needs_clarification:
            raise ValueError(
                "status must be needs_clarification exactly when issues are present"
            )
        return self
