# -*- coding: utf-8 -*-
import sys
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from core.subtitle_quality.audio_energy_analyzer import AudioEnergyAnalyzer


def test_e2e_audio_adaptive_and_timeline_workflow(live_studio_app, tmp_path, monkeypatch, qapp):
    """
    E2E Test simulating full user workflow with Step Watchdog:
    - Step 1: Open Settings and enable Adaptive Audio Style.
    - Step 2: Load video and 3-segment subtitle file.
    - Step 3: Trigger [🔄 Quét Audio] via QTest.mouseClick -> Verify whisper, normal, loud presets.
    - Step 4: Play video via QTest.keyClick(Key_Space) -> Verify playhead moves and timeline auto-scrolls.
    - Step 5: Verify clean logs via log_watcher.assert_no_errors().
    """
    win, log_watcher, runner = live_studio_app

    # =========================================================================
    # Step 1: Open Settings and check chk_auto_audio_style
    # =========================================================================
    with runner.step("Bước 1: Mở Cài đặt và bật Adaptive Audio Style", timeout_ms=5000):
        win.switch_page(6)  # Settings Center
        qapp.processEvents()

        assert hasattr(win.page_settings, "chk_auto_audio_style")
        win.page_settings.chk_auto_audio_style.setChecked(True)
        assert win.page_settings.chk_auto_audio_style.isChecked() is True

        # Switch back to Studio Workspace (page 1)
        win.switch_page(1)
        qapp.processEvents()

    # =========================================================================
    # Step 2: Load video and 3-segment subtitle file
    # =========================================================================
    with runner.step("Bước 2: Nạp video và tệp phụ đề SRT 3 phân đoạn", timeout_ms=5000):
        test_video = str(tmp_path / "e2e_test_video.mp4")
        with open(test_video, "w", encoding="utf-8") as f:
            f.write("mock video stream")

        srt_content = """1
00:00:01,000 --> 00:00:03,000
Whisper quiet speech segment

2
00:00:04,000 --> 00:00:06,000
Normal conversational dialogue segment

3
00:00:07,000 --> 00:00:09,000
LOUD SHOUTING HIGH ENERGY SEGMENT
"""
        test_srt = str(tmp_path / "e2e_test_subtitles.srt")
        with open(test_srt, "w", encoding="utf-8") as f:
            f.write(srt_content)

        win.current_vid = test_video
        win._load_context_subtitles(test_srt)
        qapp.processEvents()

        assert len(win.sub_editor.all_segments) == 3
        assert win.get_current_video_path() == test_video

        # Initialize timeline with 60s duration (60000 ms)
        win.timeline_data_provider.load_runtime_data(
            win.sub_editor.all_segments,
            60000,
        )
        win.timeline_widget.load_project_data(
            duration_ms=60000,
            segments=win.timeline_data_provider.get_all_segments(),
        )
        qapp.processEvents()

    # =========================================================================
    # Step 3: Trigger [🔄 Quét Audio] via QTest.mouseClick
    # =========================================================================
    with runner.step("Bước 3: Nhấp nút [🔄 Quét Audio]", timeout_ms=5000):
        # Synthesize peaks array: 60s @ 100fps = 6000 frames
        # Segment 1 (1000..3000ms -> idx 100..300): quiet ~0.05
        # Segment 2 (4000..6000ms -> idx 400..600): normal ~0.40
        # Segment 3 (7000..9000ms -> idx 700..900): loud ~0.90
        peaks = np.zeros((6000, 2), dtype=np.float32)
        peaks[100:300, 0] = -0.05
        peaks[100:300, 1] = 0.05
        peaks[400:600, 0] = -0.40
        peaks[400:600, 1] = 0.40
        peaks[700:900, 0] = -0.90
        peaks[700:900, 1] = 0.90

        monkeypatch.setattr(AudioEnergyAnalyzer, "get_peaks_data", lambda *args, **kwargs: peaks)

        scan_btn = win.sub_editor.reanalyze_audio_style_btn
        assert scan_btn is not None
        assert scan_btn.isEnabled()

        QTest.mouseClick(scan_btn, Qt.LeftButton)
        qapp.processEvents()

        runner.wait_until(
            lambda: [s.get("style_preset") for s in win.sub_editor.all_segments]
            == ["whisper", "normal", "loud"],
            timeout_ms=3000,
        )

    # =========================================================================
    # Step 4: Play video via QTest.keyClick(..., Qt.Key_Space)
    # =========================================================================
    with runner.step("Bước 4: Phát video và kiểm tra cuộn Timeline", timeout_ms=5000):
        # Reset scrollbar to 0 and ensure auto-scroll is enabled
        win.timeline_widget.auto_scroll_enabled = True
        win.timeline_widget.horizontalScrollBar().setValue(0)
        assert win.timeline_widget.horizontalScrollBar().value() == 0

        # Hook player.play to advance playback to 10000ms
        def on_play_advance():
            win.video_player.player.playingChanged.emit(True)
            win.video_player.position_changed(10000)

        win.video_player.player.play = on_play_advance

        # Dispatch hardware-level Space key press to MainWindow
        QTest.keyClick(win, Qt.Key_Space)
        qapp.processEvents()
        QTest.qWait(50)

        # Verify playhead moved to 10000ms and timeline auto-scrolled
        runner.wait_until(
            lambda: win.timeline_widget.container.track.playhead_ms == 10000
            and win.timeline_widget.horizontalScrollBar().value() > 0,
            timeout_ms=3000,
        )

    # =========================================================================
    # Step 5: Verify clean logs via log_watcher.assert_no_errors()
    # =========================================================================
    with runner.step("Bước 5: Kiểm tra nhật ký không có lỗi", timeout_ms=5000):
        log_watcher.assert_no_errors()


def test_step_runner_diagnostics_on_stuck_step(live_studio_app):
    """
    Simulates an intentionally stuck step to verify that E2EStepRunner
    fails without hanging infinitely and dumps the full 4-tier report.
    """
    win, log_watcher, runner = live_studio_app

    # Simulate an internal app log for Tier 3 verification
    win.append_log("📦 [HỆ THỐNG] Đã tự động tạo/nạp dự án cho video: test_stuck.mp4")

    stuck_caught = False
    try:
        with runner.step("Bước thử nghiệm: Chờ điều kiện không bao giờ xảy ra", timeout_ms=300):
            runner.wait_until(lambda: False, timeout_ms=250, poll_interval_ms=50)
    except TimeoutError:
        stuck_caught = True

    assert stuck_caught is True
    report = runner.last_failure_report
    assert "🚨 [E2E FAILURE REPORT] KỊCH BẢN BỊ KẸT TẠI BƯỚC:" in report
    assert "📍 [1. THÔNG TIN BƯỚC]" in report
    assert "🖥️ [2. TRẠNG THÁI GIAO DIỆN HIỆN TẠI (UI SNAPSHOT)]" in report
    assert "📋 [3. NHẬT KÝ NỘI BỘ ỨNG DỤNG (APP INTERNAL LOGS)]" in report
    assert "💻 [4. NHẬT KÝ COMMAND LINE & TRACEBACK (CLI STDOUT / STDERR)]" in report
    assert "test_stuck.mp4" in report


def test_error_log_watcher_detects_forbidden_errors():
    """Verifies ErrorLogWatcher faithfully flags exceptions and tracebacks."""
    from tests.e2e.conftest import ErrorLogWatcher
    import logging

    watcher = ErrorLogWatcher()
    watcher.start()

    # Case 1: Logging error record
    rec = logging.LogRecord(
        "test", logging.ERROR, "test.py", 10, "Simulated critical failure", (), None
    )
    watcher.emit(rec)
    assert any("[LOGGING ERROR]" in err for err in watcher.errors)

    # Case 2: Stderr buffer receives traceback
    watcher._tee_stderr.buffer.write(
        "Traceback (most recent call last):\n  File 'test.py', line 1\nAttributeError: 'None' object has no attribute 'val'\n"
    )

    # Case 3: assert_no_errors raises pytest failure
    with pytest.raises(pytest.fail.Exception):
        watcher.assert_no_errors()

    watcher.stop()
