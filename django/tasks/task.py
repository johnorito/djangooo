from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from inspect import iscoroutinefunction
from typing import Any, Callable, Dict, Optional

from asgiref.sync import async_to_sync, sync_to_async

from django.db.models.enums import TextChoices
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .exceptions import ResultDoesNotExist
from .utils import exception_from_dict, get_module_path

DEFAULT_TASK_BACKEND_ALIAS = "default"
DEFAULT_QUEUE_NAME = "default"
MIN_PRIORITY = -100
MAX_PRIORITY = 100
DEFAULT_PRIORITY = 0

TASK_REFRESH_ATTRS = {
    "_exception_data",
    "_return_value",
    "finished_at",
    "started_at",
    "status",
    "enqueued_at",
}


class ResultStatus(TextChoices):
    NEW = ("NEW", _("New"))
    RUNNING = ("RUNNING", _("Running"))
    FAILED = ("FAILED", _("Failed"))
    COMPLETE = ("COMPLETE", _("Complete"))


@dataclass(frozen=True)
class Task:
    priority: int
    """The priority of the task"""

    func: Callable
    """The task function"""

    backend: str
    """The name of the backend the task will run on"""

    queue_name: str = DEFAULT_QUEUE_NAME
    """The name of the queue the task will run on"""

    run_after: Optional[datetime] = None
    """The earliest this task will run"""

    enqueue_on_commit: Optional[bool] = None
    """
    Whether the task will be enqueued when the current transaction commits,
    immediately, or whatever the backend decides
    """

    def __post_init__(self):
        self.get_backend().validate_task(self)

    @property
    def name(self):
        """
        An identifier for the task
        """
        return self.func.__name__

    def using(
        self,
        *,
        priority=None,
        queue_name=None,
        run_after=None,
        backend=None,
    ):
        """
        Create a new task with modified defaults
        """

        changes = {}

        if priority is not None:
            changes["priority"] = priority
        if queue_name is not None:
            changes["queue_name"] = queue_name
        if run_after is not None:
            if isinstance(run_after, timedelta):
                changes["run_after"] = timezone.now() + run_after
            else:
                changes["run_after"] = run_after
        if backend is not None:
            changes["backend"] = backend

        return replace(self, **changes)

    def enqueue(self, *args, **kwargs):
        """
        Queue up the task to be executed
        """
        return self.get_backend().enqueue(self, args, kwargs)

    async def aenqueue(self, *args, **kwargs):
        """
        Queue up a task function (or coroutine) to be executed
        """
        return await self.get_backend().aenqueue(self, args, kwargs)

    def get_result(self, result_id):
        """
        Retrieve the result for a task of this type by its id (if one exists).
        If one doesn't, or is the wrong type, raises ResultDoesNotExist.
        """
        result = self.get_backend().get_result(result_id)

        if result.task.func != self.func:
            raise ResultDoesNotExist

        return result

    async def aget_result(self, result_id):
        """
        Retrieve the result for a task of this type by its id (if one exists).
        If one doesn't, or is the wrong type, raises ResultDoesNotExist.
        """
        result = await self.get_backend().aget_result(result_id)

        if result.task.func != self.func:
            raise ResultDoesNotExist

        return result

    def call(self, *args, **kwargs):
        if iscoroutinefunction(self.func):
            return async_to_sync(self.func)(*args, **kwargs)
        return self.func(*args, **kwargs)

    async def acall(self, *args, **kwargs):
        if iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)
        return await sync_to_async(self.func)(*args, **kwargs)

    def get_backend(self):
        from . import tasks

        return tasks[self.backend]

    @property
    def module_path(self):
        return get_module_path(self.func)


# Implementation
def task(
    function=None,
    *,
    priority=DEFAULT_PRIORITY,
    queue_name=DEFAULT_QUEUE_NAME,
    backend=DEFAULT_TASK_BACKEND_ALIAS,
    enqueue_on_commit=None,
):
    """
    A decorator used to create a task.
    """
    from . import tasks

    def wrapper(f):
        return tasks[backend].task_class(
            priority=priority,
            func=f,
            queue_name=queue_name,
            backend=backend,
            enqueue_on_commit=enqueue_on_commit,
        )

    if function:
        return wrapper(function)

    return wrapper


@dataclass(frozen=True)
class TaskResult:
    task: Task
    """The task for which this is a result"""

    id: str
    """A unique identifier for the task result"""

    status: ResultStatus
    """The status of the running task"""

    enqueued_at: Optional[datetime]
    """The time this task was enqueued"""

    started_at: Optional[datetime]
    """The time this task was started"""

    finished_at: Optional[datetime]
    """The time this task was finished"""

    args: list
    """The arguments to pass to the task function"""

    kwargs: Dict[str, Any]
    """The keyword arguments to pass to the task function"""

    backend: str
    """The name of the backend the task will run on"""

    _return_value: Optional[Any] = field(init=False, default=None)
    _exception_data: Optional[Dict[str, Any]] = field(init=False, default=None)

    @property
    def exception(self):
        return (
            exception_from_dict(self._exception_data)
            if self.status == ResultStatus.FAILED and self._exception_data is not None
            else None
        )

    @property
    def traceback(self):
        """
        Return the string representation of the traceback of the task if it failed
        """
        return (
            self._exception_data["exc_traceback"]
            if self.status == ResultStatus.FAILED and self._exception_data is not None
            else None
        )

    @property
    def return_value(self):
        """
        Get the return value of the task.

        If the task didn't complete successfully, an exception is raised.
        This is to distinguish against the task returning None.
        """
        if self.status == ResultStatus.FAILED:
            raise ValueError("Task failed")

        elif self.status != ResultStatus.COMPLETE:
            raise ValueError("Task has not finished yet")

        return self._return_value

    def refresh(self):
        """
        Reload the cached task data from the task store
        """
        refreshed_task = self.task.get_backend().get_result(self.id)

        for attr in TASK_REFRESH_ATTRS:
            object.__setattr__(self, attr, getattr(refreshed_task, attr))

    async def arefresh(self):
        """
        Reload the cached task data from the task store
        """
        refreshed_task = await self.task.get_backend().aget_result(self.id)

        for attr in TASK_REFRESH_ATTRS:
            object.__setattr__(self, attr, getattr(refreshed_task, attr))
