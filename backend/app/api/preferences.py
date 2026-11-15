from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import settings
from app.schemas.constraints import PreferenceParseResult
from app.services.ai.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
)
from app.services.ai.preference_parser import SelectedCourse, parse_preferences


class PreferenceParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    selected_courses: list[SelectedCourse] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def strip_request_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @model_validator(mode="after")
    def require_unique_course_ids(self) -> "PreferenceParseRequest":
        ids = [course.course_id for course in self.selected_courses]
        if len(ids) != len(set(ids)):
            raise ValueError("selected_courses must have unique course_id values")
        return self


router = APIRouter(prefix=settings.API_PREFIX, tags=["Preferences"])


def get_llm_client() -> LLMClient:
    return LLMClient()


@router.post(
    "/parse-preferences",
    response_model=PreferenceParseResult,
    summary="Parse natural-language timetable preferences",
)
async def parse_preferences_endpoint(
    request: PreferenceParseRequest,
    llm_client: LLMClient = Depends(get_llm_client),
) -> PreferenceParseResult:
    try:
        return await parse_preferences(
            request.text,
            request.selected_courses,
            llm_client=llm_client,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except LLMResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
