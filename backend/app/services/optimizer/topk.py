from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.services.optimizer.model import ModelContext, ModelSolution, solve_cp_model
from app.services.optimizer.objective import add_preference_objective


@dataclass
class TopKResult:
    solutions: list[ModelSolution]
    requested_k: int
    status: str
    complete: bool
    exhausted: bool


def solve_top_k(
    context: ModelContext,
    k: int,
    *,
    max_time_seconds: float = 10.0,
    num_workers: int = 8,
) -> TopKResult:
    """Return up to k schedules in nondecreasing preference-penalty order.

    The context is mutated with the objective (if absent) and a no-good cut for
    each schedule found. Each solve receives its own max_time_seconds budget.
    `complete` means the requested count was reached or the model was exhausted.
    """

    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError("k must be a positive integer")
    if max_time_seconds <= 0:
        raise ValueError("max_time_seconds must be positive")
    if num_workers <= 0:
        raise ValueError("num_workers must be positive")

    if not context.objective_added:
        add_preference_objective(context)

    solutions: list[ModelSolution] = []
    complete = False
    exhausted = False
    status = "UNKNOWN"

    for _ in range(k):
        solution = solve_cp_model(
            context,
            max_time_seconds=max_time_seconds,
            num_workers=num_workers,
        )
        status = solution.status
        if solution.status == "INFEASIBLE":
            exhausted = True
            complete = True
            break
        if solution.status not in {"OPTIMAL", "FEASIBLE"}:
            break

        solutions.append(solution)
        if solution.status != "OPTIMAL":
            break

        selected_vars = [
            context.option_vars[key] for key in solution.selected_sections
        ]
        context.model.add(
            sum(selected_vars) <= len(selected_vars) - 1
        )

    else:
        complete = True

    return TopKResult(
        solutions=solutions,
        requested_k=k,
        status=status,
        complete=complete,
        exhausted=exhausted,
    )
