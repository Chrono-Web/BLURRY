"""Talk to a worker process over pipes (QProcess), one JSON object per line."""

from __future__ import annotations

import itertools
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


def worker_command() -> tuple[str, list[str]]:
    """The same executable with the hidden worker argument."""
    if getattr(sys, "frozen", False):  # packaged app
        worker = Path(sys.executable).with_name(
            "blurry-engine.exe" if sys.platform == "win32" else "blurry-engine"
        )
        if worker.is_file():
            return str(worker), ["__worker"]
        return sys.executable, ["__worker"]
    return sys.executable, ["-m", "blurry_opsec", "__worker"]


@dataclass
class _Request:
    on_result: Callable[[dict], None] | None
    on_progress: Callable[[str, int, int], None] | None
    on_error: Callable[[str], None] | None
    on_cancelled: Callable[[], None] | None
    on_frame: Callable[[int, str], None] | None = None


class WorkerClient(QObject):
    """One worker process. Requests are processed one at a time, in order."""

    crashed = Signal()

    _ids = itertools.count(1)
    MAX_RESTARTS = 3

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._buffer = b""
        self._pending: dict[int, _Request] = {}
        self._quitting = False
        self._proc: QProcess | None = None
        self._restarts = 0
        self.unavailable = False  # the engine could not be started, or kept stopping
        self._start()

    def _start(self) -> None:
        proc = QProcess(self)
        program, args = worker_command()
        proc.setProgram(program)
        proc.setArguments(args)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedErrorChannel)
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        proc.start()
        self._proc = proc
        self._buffer = b""
        # A healthy start resets the count after a while.
        QTimer.singleShot(30_000, self, lambda: self._healthy(proc))

    def _healthy(self, proc: QProcess) -> None:
        if self._proc is proc and proc.state() == QProcess.ProcessState.Running:
            self._restarts = 0

    @property
    def busy(self) -> bool:
        return bool(self._pending)

    def request(
        self,
        cmd: str,
        payload: dict,
        on_result: Callable[[dict], None] | None = None,
        on_progress: Callable[[str, int, int], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
        on_frame: Callable[[int, str], None] | None = None,
    ) -> int:
        rid = next(self._ids)
        if self._proc is None:  # restarting, or given up: answer at once, never hang
            if on_error:
                QTimer.singleShot(0, self, lambda: on_error("worker"))
            return rid
        self._pending[rid] = _Request(on_result, on_progress, on_error, on_cancelled, on_frame)
        self._send({"id": rid, "cmd": cmd, **payload})
        return rid

    def cancel(self) -> None:
        """Cancel the request being processed (the worker removes partial files)."""
        self._send({"cmd": "cancel"})

    def shutdown(self, timeout_ms: int = 3000) -> None:
        self._quitting = True
        if self._proc is None or self._proc.state() == QProcess.ProcessState.NotRunning:
            return
        self._send({"cmd": "cancel"})
        self._send({"cmd": "quit"})
        self._proc.closeWriteChannel()
        if not self._proc.waitForFinished(timeout_ms):
            self._proc.kill()
            self._proc.waitForFinished(1000)

    def _send(self, msg: dict) -> None:
        if self._proc is not None:
            self._proc.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))

    def _on_output(self) -> None:
        if self._proc is None:
            return
        self._buffer += bytes(self._proc.readAllStandardOutput())
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        rid = msg.get("id")
        req = self._pending.get(rid)
        if req is None:
            return
        event = msg.get("event")
        if event == "progress":
            if req.on_progress:
                req.on_progress(msg["stage"], msg["done"], msg["total"])
            return
        if event == "frame":
            if req.on_frame:
                req.on_frame(msg["index"], msg["preview"])
            return
        del self._pending[rid]
        if event == "result" and req.on_result:
            req.on_result(msg)
        elif event == "error" and req.on_error:
            req.on_error(msg.get("message", "error"))
        elif event == "cancelled" and req.on_cancelled:
            req.on_cancelled()

    def _on_error(self, error: QProcess.ProcessError) -> None:
        # A process that never started emits no "finished".
        if error == QProcess.ProcessError.FailedToStart:
            self._on_finished()

    def _on_finished(self, *_args) -> None:
        if self._quitting or self._proc is None:
            return
        self._proc = None
        pending, self._pending = self._pending, {}
        for req in pending.values():
            if req.on_error:
                req.on_error("worker")
        self.crashed.emit()
        # Restart a few times, waiting longer each time; then give up and say so,
        # instead of starting processes forever.
        if self._restarts >= self.MAX_RESTARTS:
            self.unavailable = True
            return
        self._restarts += 1
        QTimer.singleShot(1000 * 2 ** (self._restarts - 1), self, self._start)
