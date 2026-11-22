from app.schemas.constraints import ConstraintStrength, PreferenceMode, TimeTarget
from app.schemas.timetable import Meeting, SectionOption, Weekday
from app.services.optimizer.model import (
    ModelContext,
    ModelSolution,
    WEEKDAY_TO_INT,
    meeting_is_scheduled,
    meeting_matches_target,
)


_DAY_NAMES = {
    Weekday.MONDAY.value: "thứ Hai",
    Weekday.TUESDAY.value: "thứ Ba",
    Weekday.WEDNESDAY.value: "thứ Tư",
    Weekday.THURSDAY.value: "thứ Năm",
    Weekday.FRIDAY.value: "thứ Sáu",
    Weekday.SATURDAY.value: "thứ Bảy",
    Weekday.SUNDAY.value: "Chủ nhật",
}


def _target_label(target: TimeTarget) -> str:
    parts = [_DAY_NAMES[WEEKDAY_TO_INT[day.value]] for day in target.days]
    if target.time_range is not None:
        time_range = target.time_range
        unit = "tiết" if time_range.unit.value == "period" else "ca"
        parts.append(f"{unit} {time_range.start}-{time_range.end}")
    return " và ".join(parts)


def _selected_sections(
    context: ModelContext,
    solution: ModelSolution,
) -> dict[str, SectionOption]:
    sections = {
        course_id: {section.section_id: section for section in options}
        for course_id, options in context.options_by_course.items()
    }
    return {
        course_id: sections[course_id][section_id]
        for course_id, section_id in solution.selected_sections
    }


def build_schedule_explanation(
    context: ModelContext,
    solution: ModelSolution,
) -> list[str]:
    selected_sections = _selected_sections(context, solution)
    selected_meetings: list[Meeting] = [
        meeting
        for section in selected_sections.values()
        for meeting in section.meetings
        if meeting_is_scheduled(meeting)
    ]
    active_days = {
        meeting.weekday.value
        for meeting in selected_meetings
        if meeting.weekday is not None
    }
    explanations = [
        "Lịch thỏa các ràng buộc cứng có thể kiểm tra."
    ]

    for preference in context.constraints.soft_days_off:
        day_number = WEEKDAY_TO_INT[preference.day.value]
        day_name = _DAY_NAMES[day_number]
        if day_number in active_days:
            explanations.append(
                f"Vi phạm mong muốn nghỉ {day_name} "
                f"(+{preference.weight} điểm phạt)."
            )
        else:
            explanations.append(f"Đáp ứng mong muốn nghỉ {day_name}.")

    for preference in context.constraints.avoid_times:
        target = preference.target
        matches = [
            meeting
            for meeting in selected_meetings
            if meeting_matches_target(meeting, target)
        ]
        label = _target_label(target)
        if matches:
            penalty = len(matches) * preference.weight
            explanations.append(
                f"{len(matches)} buổi học nằm trong khung cần tránh {label} "
                f"(+{penalty} điểm phạt)."
            )
        else:
            explanations.append(f"Không có buổi học trong khung cần tránh {label}.")

    compact_weight = context.constraints.weights.compact_days
    if compact_weight:
        penalty = len(active_days) * compact_weight
        explanations.append(
            f"Lịch học trong {len(active_days)} ngày; tiêu chí học dồn ít ngày "
            f"tạo {penalty} điểm phạt."
        )

    gap_weight = context.constraints.weights.avoid_gaps
    if gap_weight:
        gaps_by_day: dict[int, set[int]] = {}
        for day in active_days:
            occupied = {
                slot
                for meeting in selected_meetings
                if (
                    meeting.weekday is not None
                    and meeting.weekday.value == day
                    and meeting.start_unit is not None
                    and meeting.end_unit is not None
                )
                for slot in range(meeting.start_unit, meeting.end_unit + 1)
            }
            if occupied:
                gaps_by_day[day] = (
                    set(range(min(occupied) + 1, max(occupied)))
                    - occupied
                )
        gap_count = sum(len(gaps) for gaps in gaps_by_day.values())
        if gap_count:
            explanations.append(
                f"Có {gap_count} ca/tiết trống giữa các buổi học "
                f"(+{gap_count * gap_weight} điểm phạt)."
            )
        else:
            explanations.append("Không có ca/tiết trống giữa các buổi học.")

    for rule in context.constraints.per_course:
        if rule.strength is not ConstraintStrength.SOFT:
            continue
        course_id = rule.course_id
        section = selected_sections[course_id]
        meeting = section.meetings[0]
        if not meeting_is_scheduled(meeting):
            continue

        matches = meeting_matches_target(meeting, rule.target)
        violated = (
            (rule.mode is PreferenceMode.PREFER and not matches)
            or (rule.mode is PreferenceMode.AVOID and matches)
        )
        label = _target_label(rule.target)
        if violated:
            explanations.append(
                f"Môn {section.course_name} không đáp ứng yêu cầu {rule.mode.value} "
                f"{label} (+{rule.weight} điểm phạt)."
            )
        else:
            explanations.append(
                f"Môn {section.course_name} đáp ứng yêu cầu {rule.mode.value} "
                f"{label}."
            )

    if solution.objective_value == 0:
        explanations.append(
            "Không vi phạm sở thích mềm; điểm phạt 0 là tốt nhất."
        )
    elif solution.objective_value is not None:
        explanations.append(
            f"Tổng điểm phạt là {solution.objective_value}; điểm càng thấp càng tốt."
        )
    explanations.extend(solution.warnings)
    return explanations
