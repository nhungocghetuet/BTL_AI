from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.schemas.constraints import ConstraintStrength, PreferenceMode
from app.schemas.timetable import Weekday
from app.services.optimizer.model import (
    ModelContext,
    WEEKDAY_TO_INT,
    meeting_is_scheduled,
    meeting_matches_target,
)


@dataclass
class ObjectiveComponents:
    soft_days_off: cp_model.LinearExpr | int
    avoid_times: cp_model.LinearExpr | int
    compact_days: cp_model.LinearExpr | int
    avoid_gaps: cp_model.LinearExpr | int
    per_course: cp_model.LinearExpr | int

    @property
    def total_penalty(self) -> cp_model.LinearExpr | int:
        return (
            self.soft_days_off
            + self.avoid_times
            + self.compact_days
            + self.avoid_gaps
            + self.per_course
        )


def _add_or_variable(
    model: cp_model.CpModel,
    inputs: list[cp_model.IntVar],
    name: str,
) -> cp_model.IntVar:
    result = model.new_bool_var(name)
    if not inputs:
        model.add(result == 0)
        return result

    for variable in inputs:
        model.add(result >= variable)
    model.add(result <= sum(inputs))
    return result


def _add_gap_variables(
    model: cp_model.CpModel,
    occupied_slots: dict[int, cp_model.IntVar],
    day_number: int,
) -> list[cp_model.IntVar]:
    if len(occupied_slots) < 3:
        return []

    slots = sorted(occupied_slots)
    gaps: list[cp_model.IntVar] = []
    for index in range(1, len(slots) - 1):
        slot = slots[index]
        before = _add_or_variable(
            model,
            [occupied_slots[previous] for previous in slots[:index]],
            f"before_{day_number}_{slot}",
        )
        after = _add_or_variable(
            model,
            [occupied_slots[later] for later in slots[index + 1:]],
            f"after_{day_number}_{slot}",
        )
        gap = model.new_bool_var(f"gap_{day_number}_{slot}")
        current_occupied = occupied_slots[slot]
        model.add(gap <= before)
        model.add(gap <= after)
        model.add(gap + current_occupied <= 1)
        model.add(gap >= before + after - current_occupied - 1)
        gaps.append(gap)
    return gaps


def add_preference_objective(context: ModelContext) -> ObjectiveComponents:
    """Minimize weighted violations of soft timetable preferences.

    A soft day-off preference is penalized once for an active day. Time avoidance
    is penalized once per affected meeting. Compactness is measured in active
    weekdays, and gaps are empty ca/period slots between occupied slots.
    """

    if context.objective_added:
        raise ValueError("An objective has already been added to this model")

    constraints = context.constraints
    model = context.model
    day_numbers = [weekday.value for weekday in Weekday]
    slot_option_vars: dict[int, dict[int, list[cp_model.IntVar]]] = {
        day: {} for day in day_numbers
    }

    for course_id in context.selected_course_ids:
        for section in context.options_by_course[course_id]:
            variable = context.option_vars[(course_id, section.section_id)]
            for meeting in section.meetings:
                if not meeting_is_scheduled(meeting):
                    continue
                for slot in range(meeting.start_unit, meeting.end_unit + 1):
                    slot_option_vars[meeting.weekday.value].setdefault(slot, []).append(
                        variable
                    )

    occupied_by_day: dict[int, dict[int, cp_model.IntVar]] = {}
    active_by_day: dict[int, cp_model.IntVar] = {}
    all_gap_vars: list[cp_model.IntVar] = []

    for day in day_numbers:
        possible_slots = slot_option_vars[day]
        if possible_slots:
            first_slot = min(possible_slots)
            last_slot = max(possible_slots)
            occupied_by_day[day] = {
                slot: _add_or_variable(
                    model,
                    possible_slots.get(slot, []),
                    f"occupied_{day}_{slot}",
                )
                for slot in range(first_slot, last_slot + 1)
            }
        else:
            occupied_by_day[day] = {}

        active_by_day[day] = _add_or_variable(
            model,
            list(occupied_by_day[day].values()),
            f"active_{day}",
        )
        all_gap_vars.extend(
            _add_gap_variables(model, occupied_by_day[day], day)
        )

    soft_day_off_terms = [
        preference.weight * active_by_day[WEEKDAY_TO_INT[preference.day.value]]
        for preference in constraints.soft_days_off
    ]

    avoid_time_terms: list[cp_model.LinearExpr] = []
    for preference in constraints.avoid_times:
        for course_id in context.selected_course_ids:
            for section in context.options_by_course[course_id]:
                variable = context.option_vars[(course_id, section.section_id)]
                for meeting in section.meetings:
                    if meeting_matches_target(meeting, preference.target):
                        avoid_time_terms.append(preference.weight * variable)

    compact_day_terms = [
        constraints.weights.compact_days * active
        for active in active_by_day.values()
    ]
    gap_terms = [
        constraints.weights.avoid_gaps * gap
        for gap in all_gap_vars
    ]

    course_rule_terms: list[cp_model.LinearExpr] = []
    for rule in constraints.per_course:
        if rule.strength is not ConstraintStrength.SOFT:
            continue
        if rule.weight is None:
            raise ValueError("A soft course rule requires a weight")

        course_id = rule.course_id
        for section in context.options_by_course[course_id]:
            variable = context.option_vars[(course_id, section.section_id)]
            meeting = section.meetings[0]
            if not meeting_is_scheduled(meeting):
                continue
            matches = meeting_matches_target(meeting, rule.target)
            violated = (
                (rule.mode is PreferenceMode.PREFER and not matches)
                or (rule.mode is PreferenceMode.AVOID and matches)
            )
            if violated:
                course_rule_terms.append(rule.weight * variable)

    components = ObjectiveComponents(
        soft_days_off=sum(soft_day_off_terms),
        avoid_times=sum(avoid_time_terms),
        compact_days=sum(compact_day_terms),
        avoid_gaps=sum(gap_terms),
        per_course=sum(course_rule_terms),
    )
    model.minimize(components.total_penalty)
    context.objective_added = True
    return components
