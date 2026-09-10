"""Reusable background workers so file and account work never blocks Qt."""

from __future__ import annotations

import traceback
from threading import Event
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class TaskWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(
        self,
        function: Callable,
        *args,
        with_progress: bool = False,
        cancel_event: Event | None = None,
        **kwargs,
    ):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.with_progress = with_progress
        self.cancel_event = cancel_event

    @pyqtSlot()
    def run(self) -> None:
        try:
            kwargs = dict(self.kwargs)
            if self.with_progress:
                kwargs["progress"] = self.progress.emit
                kwargs["cancel_event"] = self.cancel_event
            self.finished.emit(self.function(*self.args, **kwargs))
        except Exception as exc:  # keep worker exceptions out of the Qt event loop
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            self.failed.emit(detail)
