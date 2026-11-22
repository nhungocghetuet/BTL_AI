from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.constraints import OptimizerConstraints
from app.schemas.timetable import SectionOption, TimetableData
from app.services.optimizer.model import build_cp_model
from app.services.optimizer.topk import solve_top_k


MAX_TOP_K = 10
MAX_SOLVE_SECONDS_PER_SCHEDULE = 10.0


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timetable: TimetableData
    course_ids: list[str] = Field(min_length=1)
    constraints: OptimizerConstraints = Field(default_factory=OptimizerConstraints)
    top_k: int = Field(default=5, ge=1, le=MAX_TOP_K)


class OptimizedSchedule(BaseModel):
    status: str
    penalty: int | None
    selected_sections: list[SectionOption]
    warnings: list[str]
    solve_time_seconds: float


class OptimizeResponse(BaseModel):
    schedules: list[OptimizedSchedule]
    requested_k: int
    status: str
    complete: bool
    exhausted: bool
    total_solve_time_seconds: float


router = APIRouter(tags=["Optimization"])


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    summary="Generate the best available timetable schedules",
)
def optimize_timetable(request: OptimizeRequest) -> OptimizeResponse:
    try:
        context = build_cp_model(
            request.timetable,
            request.course_ids,
            request.constraints,
        )
        result = solve_top_k(context, request.top_k)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    sections_by_key = {
        (course.course_id, section.section_id): section
        for course in request.timetable.courses
        for section in course.sections
    }
    schedules = [
        OptimizedSchedule(
            status=solution.status,
            penalty=solution.objective_value,
            selected_sections=[
                sections_by_key[key] for key in solution.selected_sections
            ],
            warnings=solution.warnings,
            solve_time_seconds=solution.solve_time_seconds,
        )
        for solution in result.solutions
    ]

    return OptimizeResponse(
        schedules=schedules,
        requested_k=result.requested_k,
        status=result.status,
        complete=result.complete,
        exhausted=result.exhausted,
        total_solve_time_seconds=sum(
            solution.solve_time_seconds for solution in result.solutions
        ),
    )
