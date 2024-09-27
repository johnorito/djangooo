from django.utils.connection import BaseConnectionHandler, ConnectionProxy
from django.utils.module_loading import import_string

from . import checks, signal_handlers  # noqa
from .exceptions import InvalidTaskBackendError
from .task import (
    DEFAULT_QUEUE_NAME,
    DEFAULT_TASK_BACKEND_ALIAS,
    ResultStatus,
    TaskResult,
    task,
)

__all__ = [
    "tasks",
    "DEFAULT_TASK_BACKEND_ALIAS",
    "DEFAULT_QUEUE_NAME",
    "task",
    "ResultStatus",
    "TaskResult",
]


class TasksHandler(BaseConnectionHandler):
    settings_name = "TASKS"
    exception_class = InvalidTaskBackendError

    def create_connection(self, alias):
        params = self.settings[alias].copy()

        # Added back to allow a backend to self-identify
        params["ALIAS"] = alias

        backend = params["BACKEND"]

        try:
            backend_cls = import_string(backend)
        except ImportError as e:
            raise InvalidTaskBackendError(
                f"Could not find backend '{backend}': {e}"
            ) from e

        return backend_cls(params)


tasks = TasksHandler()

default_task_backend = ConnectionProxy(tasks, DEFAULT_TASK_BACKEND_ALIAS)
