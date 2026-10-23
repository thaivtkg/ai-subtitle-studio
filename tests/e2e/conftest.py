# -*- coding: utf-8 -*-
import io
import os
import sys
import time
import logging
import contextlib
import traceback
from typing import List, Optional
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

E2E_INTERACTIVE = os.environ.get("E2E_INTERACTIVE", "0") == "1"


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
        self.app_logs: List[str] = []
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
                self.app_logs.append(msg_str)
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


class E2EStepRunner:
    """
    Step Watchdog & Interactive Runner for Desktop Qt E2E tests.
    Provides visual slow-mo, window title tracking, timeout guards,
    and 4-tier diagnostic failure dumps when steps get stuck.
    """

    def __init__(self, window, log_watcher, interactive: Optional[bool] = None):
        self.window = window
        self.log_watcher = log_watcher
        self.interactive = interactive if interactive is not None else E2E_INTERACTIVE
        self.current_step = ""
        self.last_failure_report = ""

    @contextlib.contextmanager
    def step(self, step_name: str, timeout_ms: int = 5000):
        self.current_step = step_name
        start_time = time.time()

        if self.interactive and self.window:
            self.window.setWindowTitle(f"AI Subtitle Studio [E2E RUNNING: {step_name}]")
            QTest.qWait(300)

        try:
            yield
            elapsed_ms = int((time.time() - start_time) * 1000)
            if elapsed_ms > timeout_ms:
                err_msg = f"Step '{step_name}' exceeded timeout: {elapsed_ms}ms > {timeout_ms}ms"
                self.dump_failure_report(step_name, elapsed_ms, timeout_ms, reason=err_msg)
                raise TimeoutError(err_msg)

            if self.interactive and self.window:
                self.window.setWindowTitle(f"AI Subtitle Studio [E2E PASSED: {step_name}]")
                QTest.qWait(300)
        except Exception as exc:
            elapsed_ms = int((time.time() - start_time) * 1000)
            self.dump_failure_report(step_name, elapsed_ms, timeout_ms, exc=exc)
            raise

    def wait_until(self, condition_fn, timeout_ms: int = 5000, poll_interval_ms: int = 50):
        """Polls condition_fn while pumping Qt events, raising TimeoutError on expiration."""
        start_time = time.time()
        while not condition_fn():
            elapsed_ms = int((time.time() - start_time) * 1000)
            if elapsed_ms > timeout_ms:
                err_msg = f"Condition not satisfied within {timeout_ms}ms"
                self.dump_failure_report(self.current_step, elapsed_ms, timeout_ms, reason=err_msg)
                raise TimeoutError(err_msg)
            QTest.qWait(poll_interval_ms)
        return True

    def dump_failure_report(
        self,
        step_name: str,
        elapsed_ms: int,
        timeout_ms: int,
        exc: Optional[Exception] = None,
        reason: str = "",
    ) -> str:
        """Gathers and outputs the 4-tier diagnostic failure report."""
        win = self.window

        # ---------------------------------------------------------------------
        # Tier 1: Step Information
        # ---------------------------------------------------------------------
        time_info = (
            f"Đã vượt quá giới hạn {timeout_ms}ms (thực tế: {elapsed_ms}ms)"
            if elapsed_ms > timeout_ms
            else f"{elapsed_ms}ms / Giới hạn: {timeout_ms}ms"
        )
        if reason:
            time_info += f" - Lý do: {reason}"

        # ---------------------------------------------------------------------
        # Tier 2: Current UI Snapshot
        # ---------------------------------------------------------------------
        STACK_NAMES = {
            0: "Dashboard",
            1: "Studio Workspace",
            2: "Queue & Output",
            3: "Draft Center",
            4: "Export Center",
            5: "Settings Center",
            6: "Help Center",
        }
        stack_idx = -1
        if win:
            if hasattr(win, "stack"):
                idx_attr = getattr(win.stack, "current_index", None)
                if idx_attr is None:
                    idx_attr = getattr(win.stack, "currentIndex", None)
                if callable(idx_attr):
                    stack_idx = idx_attr()
                elif isinstance(idx_attr, int):
                    stack_idx = idx_attr
            if stack_idx == -1 and hasattr(win, "_active_nav_index"):
                stack_idx = getattr(win, "_active_nav_index", -1)
        page_name = STACK_NAMES.get(stack_idx, f"Page {stack_idx}")

        scan_btn = getattr(getattr(win, "sub_editor", None), "reanalyze_audio_style_btn", None)
        scan_info = (
            f"isVisible={scan_btn.isVisible()}, isEnabled={scan_btn.isEnabled()}"
            if scan_btn
            else "Không tìm thấy nút"
        )

        active_modal = QApplication.activeModalWidget()
        if active_modal:
            modal_title = (
                active_modal.windowTitle()
                if hasattr(active_modal, "windowTitle") and active_modal.windowTitle()
                else "Không có tiêu đề"
            )
            modal_info = f"Đang bị chặn bởi {active_modal.__class__.__name__} ({modal_title})"
        else:
            modal_info = "Không có"

        playhead_ms = 0
        scroll_val = 0
        if win and hasattr(win, "timeline_widget") and win.timeline_widget:
            track = getattr(getattr(win.timeline_widget, "container", None), "track", None)
            if track and hasattr(track, "playhead_ms"):
                playhead_ms = track.playhead_ms
            if hasattr(win.timeline_widget, "horizontalScrollBar"):
                scroll_val = win.timeline_widget.horizontalScrollBar().value()

        h = playhead_ms // 3600000
        mi = (playhead_ms % 3600000) // 60000
        s = (playhead_ms % 60000) // 1000
        ms = playhead_ms % 1000
        playhead_str = f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"

        # ---------------------------------------------------------------------
        # Tier 3: Internal Application Logs
        # ---------------------------------------------------------------------
        app_logs = getattr(self.log_watcher, "app_logs", [])
        recent_logs = app_logs[-10:] if app_logs else ["[Chưa có log nội bộ]"]
        formatted_app_logs = "\n  ".join(recent_logs)

        # ---------------------------------------------------------------------
        # Tier 4: Command Line & Traceback Logs
        # ---------------------------------------------------------------------
        cli_lines = []
        if exc:
            tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
            cli_lines.append("".join(tb_lines).strip())

        watcher_errors = getattr(self.log_watcher, "errors", [])
        if watcher_errors:
            cli_lines.extend(watcher_errors[-5:])

        if hasattr(self.log_watcher, "_tee_stderr") and self.log_watcher._tee_stderr:
            buf = self.log_watcher._tee_stderr.getvalue().strip()
            if buf and buf not in "\n".join(cli_lines):
                cli_lines.append(buf[-500:])

        formatted_cli = "\n  ".join(cli_lines) if cli_lines else "[Không có lỗi CLI/Stderr]"

        report = f"""
================================================================================
🚨 [E2E FAILURE REPORT] KỊCH BẢN BỊ KẸT TẠI BƯỚC: [{step_name}]
================================================================================
📍 [1. THÔNG TIN BƯỚC]
  - Tên bước: {step_name}
  - Thời gian chờ: {time_info}
🖥️ [2. TRẠNG THÁI GIAO DIỆN HIỆN TẠI (UI SNAPSHOT)]
  - Cửa sổ chính: Visible={win.isVisible() if win else False}, Geometry=({win.x() if win else 0}, {win.y() if win else 0}, {win.width() if win else 0}, {win.height() if win else 0})
  - Trang đang hiển thị (Stack Index): Index {stack_idx} ({page_name})
  - Nút [🔄 Quét Audio]: {scan_info}
  - Modal Dialog đang chặn: {modal_info}
  - Kim đỏ Timeline: {playhead_str} | Thanh cuộn: {scroll_val}px
📋 [3. NHẬT KÝ NỘI BỘ ỨNG DỤNG (APP INTERNAL LOGS)]
  {formatted_app_logs}
💻 [4. NHẬT KÝ COMMAND LINE & TRACEBACK (CLI STDOUT / STDERR)]
  {formatted_cli}
================================================================================
"""
        self.last_failure_report = report.strip()

        # Output directly to sys.__stderr__ to bypass any runner captures
        try:
            sys.__stderr__.write(report + "\n")
            sys.__stderr__.flush()
        except Exception:
            try:
                sys.__stderr__.write(report.encode("ascii", errors="replace").decode("ascii") + "\n")
                sys.__stderr__.flush()
            except Exception:
                print(report.encode("ascii", errors="replace").decode("ascii"))

        # Optional: Save screenshot if window is visible
        try:
            if win and win.isVisible():
                win.grab().save("stuck_screenshot.png")
        except Exception:
            pass

        return report


@pytest.fixture
def live_studio_app(qapp, tmp_path):
    """
    Live MainWindow fixture equipped with ErrorLogWatcher and E2EStepRunner.
    Supports interactive visual mode (E2E_INTERACTIVE=1) with slow-mo and window elevation.
    Yields (MainWindow, ErrorLogWatcher, E2EStepRunner).
    """
    from ui.Gui import MainWindow

    win = MainWindow()
    watcher = ErrorLogWatcher(win)
    watcher.start()

    if E2E_INTERACTIVE:
        win.showNormal()
        win.resize(1366, 768)
        win.raise_()
        win.activateWindow()
    else:
        win.show()
    qapp.processEvents()

    runner = E2EStepRunner(win, watcher, interactive=E2E_INTERACTIVE)
    win.runner = runner
    watcher.runner = runner

    try:
        yield win, watcher, runner
    finally:
        try:
            if hasattr(win, "video_player") and hasattr(win.video_player, "cleanup"):
                win.video_player.cleanup()
        except Exception:
            pass
        try:
            qapp.removeEventFilter(win)
        except Exception:
            pass
        win.close()
        win.deleteLater()
        qapp.processEvents()
        watcher.stop()
