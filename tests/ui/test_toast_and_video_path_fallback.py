# -*- coding: utf-8 -*-
import pytest
from PySide6.QtWidgets import QWidget
from ui.toast import Toast
from ui.theme import Theme


def test_toast_warning_and_helpers(qapp):
    parent = QWidget()

    # 1. Test Toast instantiation with warning type
    toast = Toast(parent, "Cảnh báo thử nghiệm", type="warning", duration=2000)
    assert toast.container is not None

    # 2. Test classmethods exist and can be called without error
    Toast.show_warning(parent, "Warning test message", duration_ms=1000)
    Toast.show_toast(parent, "Info toast message", duration_ms=1000)
    Toast.show_success(parent, "Success message", duration_ms=1000)
    Toast.show_error(parent, "Error message", duration_ms=1000)
    Toast.show_info(parent, "Info message", duration_ms=1000)
    parent.close()


def test_gui_get_current_video_path_fallback(qapp, tmp_path):
    from ui.Gui import MainWindow

    win = MainWindow()

    test_video = str(tmp_path / "sample_video.mp4")
    with open(test_video, "w") as f:
        f.write("mock video")

    # Tier 1: self.current_vid
    win.current_vid = test_video
    assert win.get_current_video_path() == test_video

    # Clear Tier 1, test Tier 2: project_service.current_project.video_path
    win.current_vid = None
    if win.project_service and win.project_service.current_project:
        win.project_service.current_project.video_path = test_video
        assert win.get_current_video_path() == test_video
        win.project_service.current_project.video_path = None

    # Clear Tier 2, test Tier 3: queue_mgr
    if hasattr(win, "queue_mgr"):
        win.queue_mgr.get_active_data = lambda: (test_video, None)
        assert win.get_current_video_path() == test_video

    win.close()


def test_subeditor_reanalyze_audio_style_warning_no_crash(qapp):
    from ui.SubEditor import SubtitleEditorWidget

    editor = SubtitleEditorWidget()

    editor.all_segments = [
        {"start": "00:00:01,000", "end": "00:00:03,000", "text": "Hello"}
    ]

    # Without video_path, _on_reanalyze_audio_style_clicked should call Toast.show_warning
    # and return gracefully without raising AttributeError
    editor._on_reanalyze_audio_style_clicked([0])
    editor.close()
