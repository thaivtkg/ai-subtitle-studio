import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


class _MutationTracker:
    def __init__(self):
        self.dirty_calls = 0
        self.revision_calls = 0

    def mark_dirty(self):
        self.dirty_calls += 1

    def record_external_change(self):
        self.revision_calls += 1


class ActivityStreamModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _module(self):
        try:
            return importlib.import_module("ui.activity_log")
        except ImportError as exc:
            self.fail(f"Activity Stream model is not implemented yet: {exc}")

    def _parse(self, raw):
        return self._module().parse_activity_log(raw)

    def _model(self, *raw_messages):
        model = self._module().ActivityLogModel()
        for raw in raw_messages:
            model.append(raw)
        return model

    def _page_with_mutation_sentinel(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        tracker = _MutationTracker()
        page.project_service = SimpleNamespace(mark_dirty=tracker.mark_dirty)
        page.revision_tracker = SimpleNamespace(
            record_external_change=tracker.record_external_change
        )
        self.assertIsNotNone(
            getattr(page, "activity_log_model", None),
            "DashboardPage must own the Activity Stream model",
        )
        append = getattr(page, "append_activity_log", None)
        clear = getattr(page, "clear_activity_log", None)
        self.assertIsNotNone(append, "DashboardPage must expose append_activity_log")
        self.assertIsNotNone(clear, "DashboardPage must expose clear_activity_log")
        return page, tracker

    def test_a1_debug_defaults_to_system(self):
        entry = self._parse("[DEBUG] Test")
        self.assertEqual((entry.level, entry.source, entry.message), ("DEBUG", "SYSTEM", "Test"))

    def test_a2_debug_waveform(self):
        entry = self._parse("[DEBUG-WAVEFORM] Test")
        self.assertEqual((entry.level, entry.source, entry.message), ("DEBUG", "WAVEFORM", "Test"))

    def test_a3_warning_timing(self):
        entry = self._parse("[WARNING-TIMING] Warning")
        self.assertEqual((entry.level, entry.source, entry.message), ("WARNING", "TIMING", "Warning"))

    def test_a4_error_export(self):
        entry = self._parse("[ERROR-EXPORT] Failed")
        self.assertEqual((entry.level, entry.source, entry.message), ("ERROR", "EXPORT", "Failed"))

    def test_a5_plain_text_is_info_system(self):
        entry = self._parse("Plain text")
        self.assertEqual((entry.level, entry.source, entry.message), ("INFO", "SYSTEM", "Plain text"))

    def test_a6_malformed_prefix_falls_back_without_crashing(self):
        entry = self._parse("[DEBUG-")
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.source, "SYSTEM")
        self.assertEqual(entry.message, "[DEBUG-")

    def test_a7_recognized_prefix_is_removed_from_message(self):
        entry = self._parse("[WARNING-TIMING] Warning")
        self.assertEqual(entry.message, "Warning")
        self.assertNotIn("[WARNING-TIMING]", entry.message)

    def test_a8_unknown_valid_prefix_falls_back_to_system(self):
        entry = self._parse("[UNKNOWN] message")
        self.assertEqual((entry.level, entry.source), ("INFO", "SYSTEM"))
        self.assertEqual(entry.message, "[UNKNOWN] message")

    def test_a9_empty_string_is_a_valid_plain_entry(self):
        entry = self._parse("")
        self.assertEqual((entry.level, entry.source, entry.message), ("INFO", "SYSTEM", ""))

    def test_a10_unsupported_input_type_falls_back_without_crashing(self):
        for raw in (None, 123):
            with self.subTest(raw=raw):
                entry = self._parse(raw)
                self.assertEqual((entry.level, entry.source), ("INFO", "SYSTEM"))
                self.assertEqual(entry.message, str(raw))

    def test_a11_entry_has_timestamp(self):
        entry = self._parse("timestamped")
        self.assertIsInstance(entry.timestamp, datetime)

    def test_model_append_rejects_unsupported_input_types(self):
        model = self._module().ActivityLogModel()
        with self.assertRaises(TypeError):
            model.append(123)
        with self.assertRaises(TypeError):
            model.append(None)

    def test_source_only_legacy_prefixes_are_info(self):
        expected = {
            "[TIMING] message": "TIMING",
            "[QUEUE] message": "QUEUE",
            "[AI] message": "AI",
            "[FFmpeg] message": "FFMPEG",
            "[SYNC] message": "SYNC",
            "[HỆ THỐNG] message": "SYSTEM",
        }
        for raw, source in expected.items():
            with self.subTest(raw=raw):
                entry = self._parse(raw)
                self.assertEqual((entry.level, entry.source, entry.message), ("INFO", source, "message"))

    def test_b1_level_filter(self):
        model = self._model("[DEBUG-WAVEFORM] debug", "[INFO-PROJECT] info", "[ERROR-TIMING] error")
        model.set_level_filter("ERROR")
        self.assertEqual([(e.level, e.source) for e in model.visible_entries], [("ERROR", "TIMING")])
        self.assertEqual(len(model.entries), 3)

    def test_b2_source_filter(self):
        model = self._model("[DEBUG-WAVEFORM] debug", "[INFO-PROJECT] info", "[ERROR-WAVEFORM] error")
        model.set_show_technical_reports(True)
        model.set_source_filter("WAVEFORM")
        self.assertEqual([e.source for e in model.visible_entries], ["WAVEFORM", "WAVEFORM"])

    def test_b3_combined_filter(self):
        model = self._model("[DEBUG-WAVEFORM] match", "[DEBUG-PROJECT] no", "[ERROR-WAVEFORM] no")
        model.set_show_technical_reports(True)
        model.set_level_filter("DEBUG")
        model.set_source_filter("WAVEFORM")
        self.assertEqual([e.message for e in model.visible_entries], ["match"])

    def test_b4_all_restores_all_retained_entries(self):
        model = self._model("[DEBUG-WAVEFORM] debug", "[INFO-PROJECT] info")
        model.set_show_technical_reports(True)
        model.set_level_filter("DEBUG")
        model.set_source_filter("WAVEFORM")
        model.set_level_filter("ALL")
        model.set_source_filter("ALL")
        self.assertEqual(len(model.visible_entries), 2)

    def test_b5_filters_do_not_delete_history(self):
        model = self._model("one", "two", "three")
        model.set_level_filter("ERROR")
        model.set_source_filter("WAVEFORM")
        self.assertEqual([e.message for e in model.entries], ["one", "two", "three"])

    def test_technical_reports_are_hidden_by_default_and_revealed_by_option(self):
        model = self._model(
            "[DEBUG] Resolved artifact id",
            "[DEBUG-WAVEFORM] Old waveform trace",
            "[RECOVERY-SNAPSHOT] recovery snapshot cycle armed",
            "[E4-AUTOSAVE-TRACE] stage=save-start",
            "[DEBUG][waveform] waveform accepted",
            "[WARNING-QUEUE] queue warning",
            "[ERROR-WAVEFORM] extraction failed",
            "[TIMING] Timing saved",
        )

        self.assertEqual(
            [entry.raw_text for entry in model.visible_entries],
            [
                "[DEBUG][waveform] waveform accepted",
                "[WARNING-QUEUE] queue warning",
                "[ERROR-WAVEFORM] extraction failed",
                "[TIMING] Timing saved",
            ],
        )
        self.assertEqual(len(model.entries), 8)

        model.set_show_technical_reports(True)
        self.assertEqual(len(model.visible_entries), 8)
        model.set_show_technical_reports(False)
        self.assertEqual(len(model.visible_entries), 4)
        self.assertEqual(len(model.entries), 8)

    def test_activity_stream_option_reveals_retained_technical_reports(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        page.append_activity_log("[RECOVERY-SNAPSHOT] recovery snapshot cycle armed")
        page.append_activity_log("[E4-AUTOSAVE-TRACE] stage=save-start")
        page.append_activity_log("[TIMING] Timing saved")

        option = getattr(page.activity_log, "technical_reports_control", None)
        self.assertIsNotNone(option, "Activity Stream must expose the technical-report option")
        self.assertFalse(option.isChecked())
        self.assertNotIn("RECOVERY-SNAPSHOT", page.activity_log.toPlainText())
        self.assertNotIn("E4-AUTOSAVE-TRACE", page.activity_log.toPlainText())
        self.assertIn("Timing saved", page.activity_log.toPlainText())

        option.setChecked(True)
        self.app.processEvents()
        self.assertIn("RECOVERY-SNAPSHOT", page.activity_log.toPlainText())
        self.assertIn("E4-AUTOSAVE-TRACE", page.activity_log.toPlainText())
        self.assertEqual(len(page.activity_log_model.entries), 3)

        option.setChecked(False)
        self.app.processEvents()
        self.assertNotIn("RECOVERY-SNAPSHOT", page.activity_log.toPlainText())
        self.assertNotIn("E4-AUTOSAVE-TRACE", page.activity_log.toPlainText())
        self.assertIn("Timing saved", page.activity_log.toPlainText())
        self.assertEqual(len(page.activity_log_model.entries), 3)

    def test_c1_clear_removes_buffer_and_visible_rows(self):
        model = self._model("one", "two", "three")
        model.clear()
        self.assertEqual(model.entries, ())
        self.assertEqual(model.visible_entries, ())

    def test_c2_append_after_clear_works(self):
        model = self._model("old")
        model.clear()
        model.append("new")
        self.assertEqual([e.message for e in model.entries], ["new"])

    def test_c3_clear_has_no_project_or_runtime_mutation_hook(self):
        page, tracker = self._page_with_mutation_sentinel()
        page.append_activity_log("old")
        page.clear_activity_log()
        self.assertEqual((tracker.dirty_calls, tracker.revision_calls), (0, 0))

    def test_d1_buffer_is_bounded(self):
        model = self._module().ActivityLogModel(max_entries=2000)
        for index in range(2001):
            model.append(f"entry {index}")
        self.assertEqual(len(model.entries), 2000)

    def test_d2_oldest_entry_is_dropped_first(self):
        model = self._module().ActivityLogModel(max_entries=2)
        model.append("old")
        model.append("middle")
        model.append("new")
        self.assertEqual([e.message for e in model.entries], ["middle", "new"])

    def test_d3_newest_entry_is_retained(self):
        model = self._module().ActivityLogModel(max_entries=2)
        model.append("one")
        model.append("two")
        model.append("latest")
        self.assertEqual(model.entries[-1].message, "latest")

    def test_e1_auto_scroll_defaults_on(self):
        model = self._model("entry")
        self.assertTrue(model.auto_scroll)
        self.assertTrue(model.should_scroll_for(model.entries[-1]))

    def test_e2_auto_scroll_off_prevents_forced_bottom(self):
        model = self._model("entry")
        model.set_auto_scroll(False)
        self.assertFalse(model.should_scroll_for(model.entries[-1]))

    def test_e3_hidden_entry_does_not_force_scroll(self):
        model = self._model("[ERROR-TIMING] visible")
        model.set_level_filter("ERROR")
        hidden = self._module().parse_activity_log("[INFO-TIMING] hidden")
        model.append(hidden)
        self.assertFalse(model.should_scroll_for(hidden))

    def test_f1_clear_does_not_mark_project_dirty(self):
        page, tracker = self._page_with_mutation_sentinel()
        page.append_activity_log("entry")
        page.clear_activity_log()
        self.assertEqual(tracker.dirty_calls, 0)

    def test_f2_clear_does_not_increment_revision(self):
        page, tracker = self._page_with_mutation_sentinel()
        page.append_activity_log("entry")
        page.clear_activity_log()
        self.assertEqual(tracker.revision_calls, 0)

    def test_f3_clear_does_not_touch_error_txt(self):
        from ui.pages.dashboard_page import DashboardPage

        error_path = Path("Error.txt")
        before_exists = error_path.exists()
        before_stat = error_path.stat() if before_exists else None

        page = DashboardPage()
        self.assertIsNotNone(
            getattr(page, "activity_log_model", None),
            "DashboardPage must own the Activity Stream model",
        )
        append = getattr(page, "append_activity_log", None)
        clear = getattr(page, "clear_activity_log", None)
        self.assertIsNotNone(append, "DashboardPage must expose append_activity_log")
        self.assertIsNotNone(clear, "DashboardPage must expose clear_activity_log")
        append("entry")
        clear()

        self.assertEqual(error_path.exists(), before_exists)
        if before_stat is not None:
            after_stat = error_path.stat()
            self.assertEqual(after_stat.st_size, before_stat.st_size)
            self.assertEqual(after_stat.st_mtime_ns, before_stat.st_mtime_ns)

    def test_g2_malformed_log_is_accepted_by_view_model(self):
        model = self._model("[", "[DEBUG-", "")
        self.assertEqual(len(model.entries), 3)


class ActivityStreamUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _module(self):
        try:
            return importlib.import_module("ui.activity_log")
        except ImportError as exc:
            self.fail(f"Activity Stream model is not implemented yet: {exc}")

    def _append(self, page, raw):
        self.assertIsNotNone(
            getattr(page, "activity_log_model", None),
            "DashboardPage must own the Activity Stream model",
        )
        append = getattr(page, "append_activity_log", None)
        self.assertIsNotNone(append, "DashboardPage must expose append_activity_log")
        append(raw)

    def _page_with_mutation_sentinel(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        tracker = _MutationTracker()
        page.project_service = SimpleNamespace(mark_dirty=tracker.mark_dirty)
        page.revision_tracker = SimpleNamespace(
            record_external_change=tracker.record_external_change
        )
        self.assertIsNotNone(
            getattr(page, "activity_log_model", None),
            "DashboardPage must own the Activity Stream model",
        )
        return page, tracker

    def _combo_values(self, combo):
        return [combo.itemText(index) for index in range(combo.count())]

    def _view_class(self):
        view = getattr(self._module(), "ActivityLogView", None)
        self.assertIsNotNone(view, "ActivityLogView must be available")
        return view

    def _source_color(self, source):
        color = getattr(self._view_class(), "_source_color", None)
        self.assertIsNotNone(color, "ActivityLogView must expose _source_color")
        return color(source)

    def _level_color(self, level):
        color = getattr(self._view_class(), "_message_color", None)
        self.assertIsNotNone(color, "ActivityLogView must expose _message_color")
        return color(level)

    def _render_message(self, message, level="INFO"):
        render = getattr(self._view_class(), "_render_message", None)
        self.assertIsNotNone(render, "ActivityLogView must expose _render_message")
        return render(message, level)

    def _theme(self):
        from ui.theme import Theme

        return Theme

    def test_g1_main_window_append_log_keeps_raw_dock_log_and_accepts_legacy_signal(self):
        from ui.Gui import MainWindow
        from ui.pages.dashboard_page import DashboardPage

        module = self._module()
        ActivityLogView = getattr(module, "ActivityLogView", None)
        self.assertIsNotNone(ActivityLogView, "ActivityLogView must be reusable")

        page = DashboardPage()
        self.assertIsNotNone(
            getattr(page, "activity_log_model", None),
            "DashboardPage must own the Activity Stream model",
        )
        drawer_view = ActivityLogView(page.activity_log_model)
        window = MainWindow.__new__(MainWindow)
        window.log_box = drawer_view
        window.page_dashboard = page
        window.lbl_speed_eta = SimpleNamespace(setText=lambda _value: None)

        MainWindow.append_log(window, "[DEBUG-WAVEFORM] legacy signal")

        self.assertEqual(page.activity_log_model.entries[-1].source, "WAVEFORM")
        self.assertEqual(page.activity_log.toPlainText(), drawer_view.toPlainText())
        self.assertNotIn("[DEBUG-WAVEFORM]", drawer_view.toPlainText())
        self.assertFalse(hasattr(window, "activity_log_model"))

    def test_shared_view_tracks_dashboard_model_and_clear(self):
        from ui.pages.dashboard_page import DashboardPage

        module = self._module()
        ActivityLogView = getattr(module, "ActivityLogView", None)
        self.assertIsNotNone(ActivityLogView, "ActivityLogView must be reusable")
        page = DashboardPage()
        drawer_view = ActivityLogView(page.activity_log_model)

        self._append(page, "[TIMING] shared")
        self.assertEqual(page.activity_log.toPlainText(), drawer_view.toPlainText())

        page.clear_activity_log()
        self.assertEqual(drawer_view.toPlainText(), "")

    def test_drawer_exposes_shared_activity_controls(self):
        from ui.pages.dashboard_page import DashboardPage

        module = self._module()
        page = DashboardPage()
        drawer_view = module.ActivityLogView(page.activity_log_model)

        self.assertIsNotNone(getattr(drawer_view, "level_filter", None))
        self.assertIsNotNone(getattr(drawer_view, "source_filter", None))
        self.assertIsNotNone(getattr(drawer_view, "technical_reports_control", None))
        self.assertIsNotNone(getattr(drawer_view, "auto_scroll_control", None))
        self.assertIsNotNone(getattr(drawer_view, "clear_button", None))

        self._append(page, "[DEBUG-WAVEFORM] shared")
        drawer_view.technical_reports_control.setChecked(True)
        drawer_view.level_filter.setCurrentText("Debug")
        drawer_view.source_filter.setCurrentText("WAVEFORM")
        drawer_view.auto_scroll_control.setChecked(False)

        self.assertEqual(page.activity_level_filter.currentText(), "Debug")
        self.assertEqual(page.activity_source_filter.currentText(), "WAVEFORM")
        self.assertTrue(page.activity_technical_reports.isChecked())
        self.assertFalse(page.activity_auto_scroll.isChecked())

        drawer_view.clear_button.click()
        self.assertEqual(page.activity_log.toPlainText(), "")
        self.assertEqual([drawer_view.source_filter.itemText(i) for i in range(drawer_view.source_filter.count())], ["All"])

    def test_queue_start_does_not_clear_shared_activity_view(self):
        from ui.Gui import MainWindow
        from ui.pages.dashboard_page import DashboardPage

        module = self._module()
        ActivityLogView = getattr(module, "ActivityLogView", None)
        self.assertIsNotNone(ActivityLogView, "ActivityLogView must be reusable")

        page = DashboardPage()
        drawer_view = ActivityLogView(page.activity_log_model)
        self._append(page, "before queue")

        class FakeLineEdit:
            def text(self):
                return "D:/output"

        class FakeButton:
            def setEnabled(self, _enabled):
                pass

        window = MainWindow.__new__(MainWindow)
        window.queue_mgr = SimpleNamespace(
            get_items=lambda: {"D:/video.mp4": {"srt_path": "D:/video.srt"}}
        )
        window.out_input = FakeLineEdit()
        window.page_export = SimpleNamespace(out_edit=FakeLineEdit())
        window.page_dashboard = page
        window.start_btn = FakeButton()
        window.cancel_btn = FakeButton()
        window.log_box = drawer_view
        window.process_next_batch_item = lambda: None

        MainWindow.start_processing(window)

        self.assertIn("before queue", page.activity_log.toPlainText())
        self.assertIn("before queue", drawer_view.toPlainText())

    def test_g3_rendered_row_does_not_repeat_recognized_prefix(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self._append(page, "[DEBUG-WAVEFORM] message")
        page.activity_technical_reports.setChecked(True)
        rendered = page.activity_log.toPlainText()
        self.assertNotIn("[DEBUG-WAVEFORM]", rendered)

    def test_g4_rendered_row_shows_level_and_source_separately(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self._append(page, "[DEBUG-WAVEFORM] message")
        page.activity_technical_reports.setChecked(True)
        rendered = page.activity_log.toPlainText()
        self.assertIn("DEBUG", rendered)
        self.assertIn("WAVEFORM", rendered)

    def test_clear_button_only_clears_activity_stream(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self._append(page, "activity")
        clear = getattr(page, "clear_activity_log", None)
        self.assertIsNotNone(clear, "DashboardPage must expose clear_activity_log")
        clear()
        self.assertEqual(page.activity_log.toPlainText(), "")

    def test_source_filter_updates_from_retained_entries(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self._append(page, "[TIMING] one")
        self._append(page, "[DEBUG-WAVEFORM] two")
        self._append(page, "[TIMING] three")
        self.assertEqual(
            self._combo_values(page.activity_source_filter),
            ["All", "TIMING", "WAVEFORM"],
        )

        clear = getattr(page, "clear_activity_log", None)
        self.assertIsNotNone(clear, "DashboardPage must expose clear_activity_log")
        clear()
        self.assertEqual(self._combo_values(page.activity_source_filter), ["All"])

    def test_filter_controls_do_not_mutate_project_state(self):
        page, tracker = self._page_with_mutation_sentinel()
        self._append(page, "[DEBUG-WAVEFORM] waveform")
        self._append(page, "[INFO-TIMING] timing")

        page.activity_level_filter.setCurrentText("Debug")
        page.activity_source_filter.setCurrentText("WAVEFORM")
        page.activity_auto_scroll.setChecked(False)

        self.assertEqual(tracker.dirty_calls, 0)
        self.assertEqual(tracker.revision_calls, 0)

    def test_clear_resets_source_but_preserves_level_and_auto_scroll(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self._append(page, "[DEBUG-WAVEFORM] entry")
        page.activity_level_filter.setCurrentText("Debug")
        page.activity_source_filter.setCurrentText("WAVEFORM")
        page.activity_auto_scroll.setChecked(False)

        clear = getattr(page, "clear_activity_log", None)
        self.assertIsNotNone(clear, "DashboardPage must expose clear_activity_log")
        clear()

        self.assertEqual(page.activity_source_filter.currentText(), "All")
        self.assertEqual(page.activity_level_filter.currentText(), "Debug")
        self.assertFalse(page.activity_auto_scroll.isChecked())

    def test_activity_header_exposes_required_controls(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self.assertIsNotNone(getattr(page, "activity_level_filter", None))
        self.assertIsNotNone(getattr(page, "activity_source_filter", None))
        self.assertIsNotNone(getattr(page, "activity_auto_scroll", None))
        self.assertIsNotNone(getattr(page, "activity_clear_button", None))

    def test_colorful_c1_known_sources_are_differentiated(self):
        Theme = self._theme()
        expected = {
            "SYSTEM": Theme.TEXT_MUTED,
            "TIMING": Theme.WARNING,
            "QUEUE": Theme.PRIMARY_PURPLE,
            "AI": Theme.CYAN,
            "FFMPEG": Theme.SUCCESS,
            "SYNC": Theme.CYAN,
            "WAVEFORM": Theme.CYAN,
            "PROJECT": Theme.PRIMARY_PURPLE,
        }
        colors = {source: self._source_color(source) for source in expected}
        self.assertEqual(colors, expected)
        self.assertGreater(len(set(colors.values())), 3)

    def test_colorful_c2_levels_keep_semantic_colors(self):
        Theme = self._theme()
        self.assertEqual(self._level_color("DEBUG"), Theme.TEXT_MUTED)
        self.assertEqual(self._level_color("INFO"), Theme.TEXT_PRIMARY)
        self.assertEqual(self._level_color("WARNING"), Theme.WARNING)
        self.assertEqual(self._level_color("ERROR"), Theme.DANGER)

    def test_colorful_c3_error_message_gets_error_tint(self):
        self.assertIn(self._theme().DANGER, self._render_message("export failed", "ERROR"))

    def test_colorful_c4_warning_message_gets_warning_tint(self):
        self.assertIn(self._theme().WARNING, self._render_message("overlap detected", "WARNING"))

    def test_colorful_c5_info_message_remains_readable(self):
        Theme = self._theme()
        rendered = self._render_message("normal information", "INFO")
        self.assertIn(Theme.TEXT_PRIMARY, rendered)
        self.assertNotIn(Theme.CYAN, rendered)
        self.assertNotIn(Theme.PRIMARY_PURPLE, rendered)

    def test_colorful_c6_success_keywords_are_highlighted(self):
        self.assertIn(self._theme().SUCCESS, self._render_message("Export SUCCESS"))

    def test_colorful_c7_failure_keywords_are_highlighted(self):
        self.assertIn(self._theme().DANGER, self._render_message("FAILED with ERROR"))

    def test_colorful_c8_hardware_and_performance_tokens_are_highlighted(self):
        Theme = self._theme()
        rendered = self._render_message("CPU GPU CUDA VRAM speed=1.42x ETA")
        self.assertIn(Theme.CYAN, rendered)
        self.assertIn("speed=1.42x", rendered)
        self.assertIn("ETA", rendered)

    def test_colorful_c9_percentage_is_highlighted(self):
        self.assertIn(self._theme().CYAN, self._render_message("Progress 73%"))

    def test_colorful_c10_subtitle_time_range_is_highlighted(self):
        rendered = self._render_message("00:01:02,300 --> 00:01:04,100")
        self.assertIn(self._theme().CYAN, rendered)
        single = self._render_message("at 00:01:02,300")
        self.assertIn(self._theme().CYAN, single)

    def test_colorful_c11_file_path_is_highlighted(self):
        rendered = self._render_message(r"D:\Video\output.mp4 /tmp/output.srt")
        self.assertIn(self._theme().CYAN, rendered)
        self.assertIn(r"D:\Video\output.mp4", rendered)
        self.assertIn("/tmp/output.srt", rendered)

    def test_colorful_c12_html_message_remains_literal_text(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self._append(page, "[INFO] <b>x</b>&")
        self.assertIn("<b>x</b>&", page.activity_log.toPlainText())

    def test_colorful_c13_rendering_preserves_plain_text_contract(self):
        from ui.pages.dashboard_page import DashboardPage

        page = DashboardPage()
        self._append(page, "[DEBUG-WAVEFORM] GPU READY")
        page.activity_technical_reports.setChecked(True)
        rendered = page.activity_log.toPlainText()
        self.assertIn("DEBUG", rendered)
        self.assertIn("WAVEFORM", rendered)
        self.assertIn("GPU READY", rendered)

    def test_colorful_c14_unknown_source_uses_safe_fallback_color(self):
        Theme = self._theme()
        self.assertEqual(self._source_color("CUSTOMPLUGIN"), Theme.TEXT_SECONDARY)
        rendered = self._render_message("hello")
        self.assertIn("hello", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
