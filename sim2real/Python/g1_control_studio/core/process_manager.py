"""
Manages external subprocesses (RViz, SDK scripts) via QProcess.

Each process is tracked by a string key. The manager emits signals for
stdout/stderr lines, state changes, and exit events so the UI can react
without polling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QProcess, Signal, Slot


@dataclass
class ProcessInfo:
    key: str
    command: str
    args: List[str]
    started_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    process: Optional[QProcess] = field(default=None, repr=False)

    @property
    def is_running(self) -> bool:
        return (
            self.process is not None
            and self.process.state() == QProcess.ProcessState.Running
        )

    def display_command(self) -> str:
        parts = [self.command] + self.args
        return " ".join(parts)


class ProcessManager(QObject):
    """
    Thread-safe process lifecycle manager built on QProcess.

    Signals
    -------
    process_started(key)
    process_stopped(key, exit_code)
    stdout_line(key, line)
    stderr_line(key, line)
    error_occurred(key, message)
    """

    process_started = Signal(str)
    process_stopped = Signal(str, int)
    stdout_line = Signal(str, str)
    stderr_line = Signal(str, str)
    error_occurred = Signal(str, str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._processes: Dict[str, ProcessInfo] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        key: str,
        command: str,
        args: List[str] | None = None,
        env: Dict[str, str] | None = None,
    ) -> bool:
        """Launch a process identified by *key*. Returns False if already running."""
        if self.is_running(key):
            self.error_occurred.emit(key, f"Process '{key}' is already running.")
            return False

        qproc = QProcess(self)
        qproc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        if env:
            proc_env = qproc.processEnvironment()
            for k, v in env.items():
                proc_env.insert(k, v)
            qproc.setProcessEnvironment(proc_env)

        info = ProcessInfo(
            key=key,
            command=command,
            args=args or [],
            process=qproc,
        )
        self._processes[key] = info

        qproc.readyReadStandardOutput.connect(lambda: self._on_stdout(key))
        qproc.readyReadStandardError.connect(lambda: self._on_stderr(key))
        qproc.started.connect(lambda: self._on_started(key))
        qproc.finished.connect(lambda code, _status: self._on_finished(key, code))
        qproc.errorOccurred.connect(lambda err: self._on_error(key, err))

        qproc.start(command, args or [])
        return True

    def stop(self, key: str, force: bool = False) -> None:
        """Gracefully terminate a process. Pass force=True to kill immediately."""
        info = self._processes.get(key)
        if info is None or not info.is_running:
            return
        if force:
            info.process.kill()
        else:
            info.process.terminate()

    def stop_all(self) -> None:
        for key in list(self._processes):
            self.stop(key)

    def is_running(self, key: str) -> bool:
        info = self._processes.get(key)
        return info is not None and info.is_running

    def get_info(self, key: str) -> Optional[ProcessInfo]:
        return self._processes.get(key)

    def running_keys(self) -> List[str]:
        return [k for k, v in self._processes.items() if v.is_running]

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_stdout(self, key: str) -> None:
        info = self._processes.get(key)
        if info and info.process:
            raw = info.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            for line in raw.splitlines():
                if line.strip():
                    self.stdout_line.emit(key, line)

    @Slot()
    def _on_stderr(self, key: str) -> None:
        info = self._processes.get(key)
        if info and info.process:
            raw = info.process.readAllStandardError().data().decode("utf-8", errors="replace")
            for line in raw.splitlines():
                if line.strip():
                    self.stderr_line.emit(key, line)

    def _on_started(self, key: str) -> None:
        info = self._processes.get(key)
        if info:
            info.started_at = datetime.now()
        self.process_started.emit(key)

    def _on_finished(self, key: str, exit_code: int) -> None:
        info = self._processes.get(key)
        if info:
            info.exit_code = exit_code
        self.process_stopped.emit(key, exit_code)

    def _on_error(self, key: str, error: QProcess.ProcessError) -> None:
        messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start — check path and permissions.",
            QProcess.ProcessError.Crashed: "Process crashed unexpectedly.",
            QProcess.ProcessError.Timedout: "Process timed out.",
            QProcess.ProcessError.WriteError: "Write error.",
            QProcess.ProcessError.ReadError: "Read error.",
            QProcess.ProcessError.UnknownError: "Unknown error.",
        }
        self.error_occurred.emit(key, messages.get(error, "Unknown error."))
