from dataclasses import dataclass
from typing import TypeAlias

from ortools.sat.python import cp_model

from app.schemas.constraints import (
    ConstraintStrength,
    HardTimeRule,
    OptimizerConstraints,
    PreferenceMode,
    TimeTarget,
)
from app.schemas.timetable import (
    Course,
    Meeting,
    SectionOption,
    TimetableData,
    TimeUnit,
    Weekday,
)


OptionKey: TypeAlias = tuple[str, str]
WEEKDAY_TO_INT = {
    "MONDAY": Weekday.MONDAY.value,
    "TUESDAY": Weekday.TUESDAY.value,
    "WEDNESDAY": Weekday.WEDNESDAY.value,
    "THURSDAY": Weekday.THURSDAY.value,
    "FRIDAY": Weekday.FRIDAY.value,
    "SATURDAY": Weekday.SATURDAY.value,
    "SUNDAY": Weekday.SUNDAY.value,
}


@dataclass
class ModelContext:
    model: cp_model.CpModel
    timetable: TimetableData
    constraints: OptimizerConstraints
    selected_course_ids: list[str]
    option_vars: dict[OptionKey, cp_model.IntVar]
    options_by_course: dict[str, list[SectionOption]]
    option_warnings: dict[OptionKey, list[str]]
    warnings: list[str]
    objective_added: bool = False


@dataclass
class ModelSolution:
    status: str
    selected_sections: list[OptionKey]
    objective_value: int | None
    solve_time_seconds: float
    warnings: list[str]


def meeting_is_scheduled(meeting: Meeting) -> bool:
    return (
        meeting.schedule_confirmed
        and meeting.weekday is not None
        and meeting.start_unit is not None
        and meeting.end_unit is not None
    )


def _time_ranges_overlap(first: Meeting, second: Meeting) -> bool:
    if first.time_unit is not second.time_unit:
        raise ValueError(
            "A timetable cannot mix time units without an explicit conversion table"
        )
    return (
        first.start_unit is not None
        and first.end_unit is not None
        and second.start_unit is not None
        and second.end_unit is not None
        and first.start_unit <= second.end_unit
        and second.start_unit <= first.end_unit
    )


def _target_unit(target: TimeTarget) -> TimeUnit | None:
    if target.time_range is None:
        return None
    if target.time_range.unit.value not in {unit.value for unit in TimeUnit}:
        raise ValueError(f"Unsupported preference time unit: {target.time_range.unit}")
    return TimeUnit(target.time_range.unit.value)


def meeting_matches_target(meeting: Meeting, target: TimeTarget) -> bool:
    if not meeting_is_scheduled(meeting):
        return False

    if target.days:
        allowed_days = {WEEKDAY_TO_INT[day.value] for day in target.days}
        if meeting.weekday.value not in allowed_days:
            return False

    if target.time_range is not None:
        expected_unit = _target_unit(target)
        if meeting.time_unit is not expected_unit:
            raise ValueError(
                "Preference time unit does not match the timetable time unit"
            )
        return (
            meeting.start_unit is not None
            and meeting.end_unit is not None
            and meeting.start_unit <= target.time_range.end
            and target.time_range.start <= meeting.end_unit
        )

    return True


def _meeting_matches_hard_time_rule(
    meeting: Meeting,
    rule: HardTimeRule,
) -> bool:
    return meeting_matches_target(meeting, rule.target)


def _option_meetings_conflict(option: SectionOption) -> bool:
    scheduled = [meeting for meeting in option.meetings if meeting_is_scheduled(meeting)]
    for index, first in enumerate(scheduled):
        for second in scheduled[index + 1:]:
            if (
                first.weekday == second.weekday
                and _time_ranges_overlap(first, second)
            ):
                return True
    return False


def _validate_timetable_units(timetable: TimetableData) -> None:
    for course in timetable.courses:
        for section in course.sections:
            for meeting in section.meetings:
                if meeting.time_unit is not timetable.time_unit:
                    raise ValueError(
                        "A timetable cannot mix time units without an explicit "
                        "conversion table"
                    )


def build_cp_model(
    timetable: TimetableData,
    selected_course_ids: list[str],
    constraints: OptimizerConstraints | None = None,
) -> ModelContext:
    """Build hard CP-SAT constraints for choosing one section per selected course.

    Soft preferences are retained in the context for objective.py to consume.
    """

    if not selected_course_ids:
        raise ValueError("At least one course must be selected")
    if len(selected_course_ids) != len(set(selected_course_ids)):
        raise ValueError("selected_course_ids must not contain duplicates")

    constraints = constraints or OptimizerConstraints()
    _validate_timetable_units(timetable)

    courses_by_id: dict[str, Course] = {}
    for course in timetable.courses:
        if course.course_id in courses_by_id:
            raise ValueError(f"Duplicate course_id in timetable: {course.course_id}")
        courses_by_id[course.course_id] = course

    missing_courses = [
        course_id for course_id in selected_course_ids if course_id not in courses_by_id
    ]
    if missing_courses:
        raise ValueError(
            f"Selected courses are not present in the timetable: "
            f"{', '.join(missing_courses)}"
        )

    selected_courses = [courses_by_id[course_id] for course_id in selected_course_ids]
    options_by_course: dict[str, list[SectionOption]] = {}
    for course in selected_courses:
        section_ids = [section.section_id for section in course.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError(
                f"Duplicate section_id in course {course.course_id}"
            )
        options_by_course[course.course_id] = course.sections

    for rule in constraints.per_course:
        if rule.course_id not in selected_course_ids:
            raise ValueError(
                f"Course rule references an unselected course: {rule.course_id}"
            )
        if any(
            len(section.meetings) != 1
            for section in options_by_course[rule.course_id]
        ):
            raise ValueError(
                f"Course-specific time rules currently require exactly one "
                f"weekly meeting for course {rule.course_id}"
            )

    for rule in constraints.hard_time_rules:
        expected_unit = _target_unit(rule.target)
        if expected_unit is not None and expected_unit is not timetable.time_unit:
            raise ValueError(
                "Time rule unit does not match the timetable time unit"
            )
    for rule in constraints.avoid_times:
        expected_unit = _target_unit(rule.target)
        if expected_unit is not None and expected_unit is not timetable.time_unit:
            raise ValueError(
                "Time rule unit does not match the timetable time unit"
            )
    for rule in constraints.per_course:
        expected_unit = _target_unit(rule.target)
        if expected_unit is not None and expected_unit is not timetable.time_unit:
            raise ValueError(
                "Course rule unit does not match the timetable time unit"
            )

    model = cp_model.CpModel()
    option_vars: dict[OptionKey, cp_model.IntVar] = {}
    option_warnings: dict[OptionKey, list[str]] = {}
    warnings: list[str] = []

    for course in selected_courses:
        course_vars: list[cp_model.IntVar] = []
        for section in course.sections:
            key = (course.course_id, section.section_id)
            variable = model.new_bool_var(f"choose_{len(option_vars)}")
            option_vars[key] = variable
            course_vars.append(variable)

            section_warnings: list[str] = []
            if any(not meeting_is_scheduled(meeting) for meeting in section.meetings):
                section_warnings.append(
                    f"{course.course_name} ({section.section_id}) has a meeting "
                    "without a confirmed day/time; conflicts and hard time rules "
                    "cannot be fully verified."
                )

            if _option_meetings_conflict(section):
                model.add(variable == 0)
                section_warnings.append(
                    f"{course.course_name} ({section.section_id}) contains "
                    "overlapping meetings and cannot be selected."
                )

            option_warnings[key] = section_warnings

        model.add_exactly_one(course_vars)

    all_options: list[tuple[OptionKey, SectionOption]] = [
        ((course.course_id, section.section_id), section)
        for course in selected_courses
        for section in course.sections
    ]

    for index, (first_key, first_option) in enumerate(all_options):
        for second_key, second_option in all_options[index + 1:]:
            if first_key[0] == second_key[0]:
                continue
            has_conflict = any(
                first_meeting.weekday == second_meeting.weekday
                and _time_ranges_overlap(first_meeting, second_meeting)
                for first_meeting in first_option.meetings
                if meeting_is_scheduled(first_meeting)
                for second_meeting in second_option.meetings
                if meeting_is_scheduled(second_meeting)
            )
            if has_conflict:
                model.add(option_vars[first_key] + option_vars[second_key] <= 1)

    hard_days_off = {WEEKDAY_TO_INT[day.value] for day in constraints.hard_days_off}
    for key, section in all_options:
        variable = option_vars[key]
        for meeting in section.meetings:
            if not meeting_is_scheduled(meeting):
                continue

            if meeting.weekday.value in hard_days_off:
                model.add(variable == 0)

            for rule in constraints.hard_time_rules:
                matches = _meeting_matches_hard_time_rule(meeting, rule)
                if rule.mode is PreferenceMode.AVOID and matches:
                    model.add(variable == 0)
                elif rule.mode is PreferenceMode.PREFER and not matches:
                    model.add(variable == 0)

            for rule in constraints.per_course:
                if (
                    rule.strength is not ConstraintStrength.HARD
                    or rule.course_id != key[0]
                ):
                    continue
                matches = meeting_matches_target(meeting, rule.target)
                if rule.mode is PreferenceMode.AVOID and matches:
                    model.add(variable == 0)
                elif rule.mode is PreferenceMode.PREFER and not matches:
                    model.add(variable == 0)

    for section_warnings in option_warnings.values():
        warnings.extend(section_warnings)

    return ModelContext(
        model=model,
        timetable=timetable,
        constraints=constraints,
        selected_course_ids=list(selected_course_ids),
        option_vars=option_vars,
        options_by_course=options_by_course,
        option_warnings=option_warnings,
        warnings=sorted(set(warnings)),
    )


def solve_cp_model(
    context: ModelContext,
    *,
    max_time_seconds: float = 10.0,
    num_workers: int = 8,
) -> ModelSolution:
    if max_time_seconds <= 0:
        raise ValueError("max_time_seconds must be positive")
    if num_workers <= 0:
        raise ValueError("num_workers must be positive")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time_seconds
    solver.parameters.num_search_workers = num_workers
    status = solver.solve(context.model)

    status_name = solver.status_name(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ModelSolution(
            status=status_name,
            selected_sections=[],
            objective_value=None,
            solve_time_seconds=solver.wall_time,
            warnings=context.warnings,
        )

    selected_sections = [
        key
        for key, variable in context.option_vars.items()
        if solver.boolean_value(variable)
    ]
    selected_warnings = [
        warning
        for key in selected_sections
        for warning in context.option_warnings[key]
    ]
    return ModelSolution(
        status=status_name,
        selected_sections=selected_sections,
        objective_value=(
            int(round(solver.objective_value))
            if context.objective_added
            else None
        ),
        solve_time_seconds=solver.wall_time,
        warnings=sorted(set(selected_warnings)),
    )
