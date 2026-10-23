# -*- coding: utf-8 -*-
import io
import sys
import logging
from typing import List, Optional
import pytest
from PySide6.QtWidgets import QApplication


class StderrTee:
    """Tees sys.stderr to original stream and in-memory buffer to audit errors."""

    def __init__(self, original, watcher):
        self.original = original
        self.watcher = watcher
        self.buffer = io.StringIO()

    def write(self, s: str):
        if self.original:
            try:
                self.original.write(s)
            except Exception:
                pass
        self.buffer.write(s)
        for pattern in self.watcher.FORBIDDEN_PATTERNS:
            if pattern in s:
                self.watcher.errors.append(f"[STDERR] {s.strip()}")
                break

    def flush(self):
        if self.original:
            try:
                self.original.flush()
            except Exception:
                pass
        self.buffer.flush()

    def getvalue(self) -> str:
        return self.buffer.getvalue()

    def __getattr__(self, name):
        return getattr(self.original, name)


class ErrorLogWatcher(logging.Handler):
    """
    Exception & Traceback Auditor for Desktop Qt E2E tests.
    Intercepts sys.stderr, Python root logging, and MainWindow.append_log
    to catch unhandled exceptions, tracebacks, and runtime UI errors.
    """

    FORBIDDEN_PATTERNS = [
        "Traceback (most recent call last)",
        "AttributeError:",
        "TypeError:",
        "ModuleNotFoundError:",
        "ImportError:",
        "NameError:",
        "❌ [LỖI]",
        "❌ [ERROR]",
        "[CRITICAL]",
    ]

    def __init__(self, window=None):
        super().__init__(level=logging.ERROR)
        self.errors: List[str] = []
        self._orig_stderr = None
        self._tee_stderr: Optional[StderrTee] = None
        self._window = window
        self._orig_append_log = None
        self._installed = False

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.errors.append(f"[LOGGING {record.levelname}] {msg}")

    def start(self, window=None):
        if self._installed:
            return
        if window:
            self._window = window

        # 1. Attach to root logger for ERROR and CRITICAL
        logging.getLogger().addHandler(self)

        # 2. Tee sys.stderr
        self._orig_stderr = sys.stderr
        self._tee_stderr = StderrTee(self._orig_stderr, self)
        sys.stderr = self._tee_stderr

        # 3. Hook MainWindow.append_log if present
        if self._window and hasattr(self._window, "append_log"):
            self._orig_append_log = self._window.append_log

            def hooked_append_log(msg, *args, **kwargs):
                msg_str = str(msg)
                for pattern in self.FORBIDDEN_PATTERNS:
                    if pattern in msg_str:
                        self.errors.append(f"[APP_LOG] {msg_str.strip()}")
                        break
                return self._orig_append_log(msg, *args, **kwargs)

            self._window.append_log = hooked_append_log

        self._installed = True

    def stop(self):
        if not self._installed:
            return
        # Detach root logging handler
        try:
            logging.getLogger().removeHandler(self)
        except Exception:
            pass
        # Restore sys.stderr
        if self._tee_stderr:
            sys.stderr = self._orig_stderr
            self._tee_stderr = None
        # Restore MainWindow.append_log
        if self._window and self._orig_append_log:
            self._window.append_log = self._orig_append_log
            self._orig_append_log = None
        self._installed = False

    def assert_no_errors(self):
        """Asserter that verifies zero forbidden patterns or tracebacks occurred."""
        if self._tee_stderr:
            stderr_all = self._tee_stderr.getvalue()
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern in stderr_all:
                    for line in stderr_all.splitlines():
                        if pattern in line:
                            entry = f"[STDERR] {line.strip()}"
                            if entry not in self.errors:
                                self.errors.append(entry)

        if self.errors:
            summary = "\n".join(f"  - {err}" for err in self.errors)
            pytest.fail(f"ErrorLogWatcher detected {len(self.errors)} error(s) during execution:\n{summary}")


@pytest.fixture
def live_studio_app(qapp, tmp_path):
    """
    Live MainWindow fixture equipped with ErrorLogWatcher.
    Yields (MainWindow, ErrorLogWatcher) and guarantees clean teardown.
    """
    from ui.Gui import MainWindow

    win = MainWindow()
    watcher = ErrorLogWatcher(win)
    watcher.start()
    win.show()
    qapp.processEvents()

    try:
        yield win, watcher
    finally:
        watcher.stop()
        try:
            qapp.removeEventFilter(win)
        except Exception:
            pass
        win.close()
        qapp.processEvents()
