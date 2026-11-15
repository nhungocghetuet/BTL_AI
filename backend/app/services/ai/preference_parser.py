from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schemas.constraints import (
    IssueCode,
    ParseStatus,
    PreferenceIssue,
    PreferenceParseResult,
)
from app.services.ai.llm_client import LLMClient, LLMResponseError
from app.services.ai.prompts import SYSTEM_PROMPT, build_user_prompt


class SelectedCourse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1)
    course_name: str = Field(min_length=1)
    weekly_meeting_count: int | None = Field(default=None, ge=1)

    @field_validator("course_id", "course_name")
    @classmethod
    def strip_course_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("course identifiers and names must not be blank")
        return value


async def parse_preferences(
    text: str,
    selected_courses: list[SelectedCourse],
    *,
    llm_client: LLMClient,
) -> PreferenceParseResult:
    schema = PreferenceParseResult.model_json_schema()
    user_prompt = build_user_prompt(
        text,
        [course.model_dump(mode="json") for course in selected_courses],
        schema,
    )
    raw_result = await llm_client.complete_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    try:
        result = PreferenceParseResult.model_validate(raw_result)
    except ValidationError as exc:
        raise LLMResponseError(
            "LLM output did not match the preference schema"
        ) from exc

    courses_by_id = {course.course_id: course for course in selected_courses}
    valid_rules = []
    issues = list(result.issues)

    for rule in result.constraints.per_course:
        course = courses_by_id.get(rule.course_id)
        issue: PreferenceIssue | None = None
        if course is None:
            issue = PreferenceIssue(
                code=IssueCode.UNKNOWN_COURSE,
                message=f"Không tìm thấy môn học có mã {rule.course_id}.",
                source_text=rule.course_id,
            )
        elif course.weekly_meeting_count is None:
            issue = PreferenceIssue(
                code=IssueCode.AMBIGUOUS,
                message=(
                    f"Chưa xác định được số buổi mỗi tuần của môn "
                    f"{course.course_name}."
                ),
                source_text=course.course_name,
            )
        elif course.weekly_meeting_count != 1:
            issue = PreferenceIssue(
                code=IssueCode.UNSUPPORTED,
                message=(
                    f"Yêu cầu theo môn hiện chỉ hỗ trợ môn có đúng một buổi "
                    f"mỗi tuần; {course.course_name} có "
                    f"{course.weekly_meeting_count} buổi."
                ),
                source_text=course.course_name,
            )

        if issue is None:
            valid_rules.append(rule)
        else:
            issues.append(issue)

    if len(valid_rules) != len(result.constraints.per_course):
        result.constraints.per_course = valid_rules
        result.issues = issues
        result.status = ParseStatus.NEEDS_CLARIFICATION

    return result
