"""Central benchmark task catalog providing discovery, parameterization,
and schema-validated instantiation of all 12 benchmark tasks.
"""

from typing import Any, Callable
from ..schema import TaskCategory, TaskDefinition
from .coordination import get_task_01, get_task_02, get_task_03, get_task_04
from .security import get_task_05, get_task_06, get_task_07
from .reliability import get_task_08, get_task_09, get_task_10
from .integrity import get_task_11, get_task_12

TASK_BUILDERS: dict[str, Callable[..., TaskDefinition]] = {
    "TASK-01": get_task_01,
    "TASK-02": get_task_02,
    "TASK-03": get_task_03,
    "TASK-04": get_task_04,
    "TASK-05": get_task_05,
    "TASK-06": get_task_06,
    "TASK-07": get_task_07,
    "TASK-08": get_task_08,
    "TASK-09": get_task_09,
    "TASK-10": get_task_10,
    "TASK-11": get_task_11,
    "TASK-12": get_task_12,
}


def get_task(task_id: str, seed: int = 42, **kwargs) -> TaskDefinition:
    """Retrieves a specific benchmark task by ID with parameterizable seed."""
    normalized_id = task_id.upper().strip()
    builder = TASK_BUILDERS.get(normalized_id)
    if not builder:
        raise KeyError(f"Unknown benchmark task ID: {task_id}. Available: {list(TASK_BUILDERS.keys())}")
    return builder(seed=seed, **kwargs)


def get_all_tasks(seed: int = 42) -> list[TaskDefinition]:
    """Instantiates and returns all 12 benchmark tasks."""
    return [builder(seed=seed) for builder in TASK_BUILDERS.values()]


def get_tasks_by_category(category: TaskCategory, seed: int = 42) -> list[TaskDefinition]:
    """Retrieves benchmark tasks matching a specific capability category."""
    all_tasks = get_all_tasks(seed=seed)
    return [t for t in all_tasks if t.category == category]


def get_tasks_by_tag(tag: str, seed: int = 42) -> list[TaskDefinition]:
    """Retrieves benchmark tasks containing a specific tag."""
    all_tasks = get_all_tasks(seed=seed)
    needle = tag.lower()
    return [t for t in all_tasks if needle in [item.lower() for item in t.tags]]


def list_task_metadata() -> list[dict[str, Any]]:
    """Returns metadata overview of all 12 benchmark tasks."""
    return [
        {
            "task_id": t.task_id,
            "name": t.name,
            "category": t.category.value,
            "expected_status": t.expected_status,
            "tags": t.tags,
            "description": t.description,
        }
        for t in get_all_tasks()
    ]

