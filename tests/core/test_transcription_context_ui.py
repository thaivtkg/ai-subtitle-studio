import unittest
from unittest.mock import MagicMock

from core.project.transcription_context import TranscriptionContext
from core.transcription.prompt_context_builder import CompiledPromptContext

try:
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtWidgets import QApplication
except (ModuleNotFoundError, ImportError, OSError):
    QApplication = None
    QSignalSpy = None
    QTest = None

if QApplication is not None:
    from ui.components.transcription_context_panel import TranscriptionContextPanel
else:
    TranscriptionContextPanel = None


class TestTranscriptionContextUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = (
            QApplication.instance() or QApplication([])
            if QApplication is not None
            else None
        )

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_context_panel_emits_debounced_commit_with_multiline_glossary(self):
        panel = TranscriptionContextPanel()
        panel.debounce_timer.setInterval(20)
        spy = QSignalSpy(panel.context_committed)
        panel.context_edit.setPlainText("Trận chiến tại Demacia")
        panel.glossary_edit.setPlainText("Demacia\nLux\nGaren")
        self.assertEqual(spy.count(), 0)
        self.assertTrue(spy.wait(1000))
        self.assertEqual(spy.count(), 1)
        committed_ctx = spy.at(0)[0]
        self.assertIsInstance(committed_ctx, TranscriptionContext)
        self.assertEqual(committed_ctx.context, "Trận chiến tại Demacia")
        self.assertEqual(committed_ctx.glossary, ["Demacia", "Lux", "Garen"])

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_programmatic_set_context_does_not_emit_commit(self):
        panel = TranscriptionContextPanel()
        spy = QSignalSpy(panel.context_committed)
        panel.set_context(TranscriptionContext("Load context", ["Term1"]))
        QTest.qWait(50)
        self.assertEqual(spy.count(), 0)

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_set_context_cancels_pending_user_commit(self):
        panel = TranscriptionContextPanel()
        panel.debounce_timer.setInterval(100)
        spy = QSignalSpy(panel.context_committed)
        panel.context_edit.setPlainText("Pending edit")
        panel.set_context(TranscriptionContext("New Project", []))
        QTest.qWait(150)
        self.assertEqual(spy.count(), 0)

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_context_panel_updates_diagnostics_read_only(self):
        panel = TranscriptionContextPanel()
        compiled = CompiledPromptContext(
            text="Terminology: Demacia. Context: Trận chiến",
            token_count=72,
            max_tokens=180,
            glossary_items_used=1,
            glossary_items_dropped=0,
            context_truncated=False,
            truncated=False,
        )
        panel.set_prompt_diagnostics(compiled)
        diagnostics_text = panel.diagnostics_label.text()
        self.assertIn("72/180", diagnostics_text)
        self.assertIn("1", diagnostics_text)
        self.assertNotIn("cắt bớt", diagnostics_text.lower())

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_context_panel_updates_diagnostics_format(self):
        panel = TranscriptionContextPanel()
        compiled = CompiledPromptContext(
            "Terminology: Demacia.", 180, 180, 1, 2, True, True
        )
        panel.set_prompt_diagnostics(compiled)
        text = panel.diagnostics_label.text()
        self.assertIn("1/3 glossary · ~180/180 tokens", text)
        self.assertIn("⚠ 2 glossary term(s) omitted · Context truncated", text)

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_generate_panel_context_status_and_action(self):
        from PySide6.QtWidgets import QPlainTextEdit, QTextEdit
        from ui.subtitle_generation_panel import SubtitleGenerationPanel

        panel = SubtitleGenerationPanel(MagicMock())
        self.assertEqual(panel.findChildren(QPlainTextEdit), [])
        self.assertEqual(panel.findChildren(QTextEdit), [])
        panel.set_context_status(
            CompiledPromptContext("test", 72, 180, 6, 0, False, False),
            configured=True,
        )
        self.assertEqual(
            panel.context_status_label.text(),
            "Context: configured · 6/6 glossary · ~72/180 tokens",
        )
        spy = QSignalSpy(panel.request_context_edit)
        panel.edit_context_btn.click()
        self.assertEqual(spy.count(), 1)

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_generate_panel_context_status_follows_task_mode(self):
        from ui.subtitle_generation_panel import SubtitleGenerationPanel

        panel = SubtitleGenerationPanel(MagicMock())
        panel.set_context_status(
            CompiledPromptContext("test", 72, 180, 2, 0, False, False),
            configured=True,
        )
        self.assertIn("Context: configured", panel.context_status_label.text())
        panel.cmb_mode.setCurrentIndex(1)
        self.assertEqual(
            panel.context_status_label.text(), "Context: not used in Timing Draft"
        )
        panel.cmb_mode.setCurrentIndex(0)
        self.assertIn("Context: configured", panel.context_status_label.text())

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_auto_glossary_toggle_defaults_on_and_extracts_after_typing_delay(self):
        class StubProvider:
            def __init__(self):
                self.last_prompt = None
                self.call_count = 0

            def translate(self, prompt: str) -> str:
                self.last_prompt = prompt
                self.call_count += 1
                return "1. 非同期処理\n2. イベントループ\n3. FastAPI\n4. python"

        stub = StubProvider()
        panel = TranscriptionContextPanel()
        self.assertTrue(panel.btn_auto_glossary.isCheckable())
        self.assertTrue(panel.btn_auto_glossary.isChecked())
        self.assertEqual(panel.auto_glossary_timer.interval(), 2000)

        panel.auto_glossary_timer.setInterval(40)
        panel.debounce_timer.setInterval(20)
        panel.set_llm_provider_factory(lambda: stub)
        panel.set_language_getter(lambda: "ja")
        panel.glossary_edit.setPlainText("Python")
        panel.domain_edit.setText("Programming")
        panel.context_edit.setPlainText("Video hướng dẫn lập trình bất đồng bộ Python")

        # Immediately after typing, debounce delay has not elapsed yet
        self.assertEqual(stub.call_count, 0)

        for _ in range(40):
            if "✓ Extracted" in panel.diagnostics_label.text():
                break
            QTest.qWait(25)

        self.assertEqual(stub.call_count, 1)
        self.assertIn("Japanese", stub.last_prompt)
        self.assertIn("Programming", stub.last_prompt)
        self.assertIn("✓ Extracted 4 glossary term(s) (3 new)", panel.diagnostics_label.text())
        self.assertEqual(
            panel.glossary_edit.toPlainText().splitlines(),
            ["Python", "非同期処理", "イベントループ", "FastAPI"],
        )

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_auto_glossary_when_toggled_off_does_not_extract_until_toggled_on(self):
        calls = 0

        class CountingProvider:
            def translate(self, prompt: str) -> str:
                nonlocal calls
                calls += 1
                return "Rust\nBorrow Checker"

        panel = TranscriptionContextPanel()
        panel.auto_glossary_timer.setInterval(40)
        panel.set_llm_provider_factory(lambda: CountingProvider())

        # Click toggle to turn OFF
        panel.btn_auto_glossary.click()
        self.assertFalse(panel.btn_auto_glossary.isChecked())
        self.assertIn("OFF", panel.btn_auto_glossary.text())

        panel.context_edit.setPlainText("Video giải thích cơ chế quản lý bộ nhớ trong Rust")
        QTest.qWait(100)
        self.assertEqual(calls, 0)

        # Click toggle back to ON -> should schedule auto extraction after delay
        panel.btn_auto_glossary.click()
        self.assertTrue(panel.btn_auto_glossary.isChecked())
        self.assertIn("ON", panel.btn_auto_glossary.text())

        for _ in range(40):
            if calls > 0 and "Rust" in panel.glossary_edit.toPlainText():
                break
            QTest.qWait(25)

        self.assertEqual(calls, 1)
        self.assertEqual(
            panel.glossary_edit.toPlainText().splitlines(),
            ["Rust", "Borrow Checker"],
        )

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_set_context_cancels_in_flight_auto_glossary_worker(self):
        import threading

        started = threading.Event()
        release = threading.Event()

        class SlowProvider:
            def translate(self, prompt: str) -> str:
                started.set()
                release.wait(timeout=2.0)
                return "StaleTermFromProjectA"

        panel = TranscriptionContextPanel()
        panel.auto_glossary_timer.setInterval(20)
        panel.set_llm_provider_factory(lambda: SlowProvider())
        panel.context_edit.setPlainText("Summary of Project A")
        panel.debounce_timer.stop()

        for _ in range(30):
            if started.is_set():
                break
            QTest.qWait(20)
        self.assertTrue(started.is_set())

        spy = QSignalSpy(panel.context_committed)
        panel.set_context(TranscriptionContext("Project B", ["ProjectBTerm"]))
        self.assertFalse(panel.auto_glossary_timer.isActive())
        self.assertEqual(panel.btn_auto_glossary.text(), "✨ Auto Glossary: ON")
        self.assertFalse(panel.diagnostics_label.text().startswith("Extracting glossary"))

        release.set()
        QTest.qWait(100)

        self.assertEqual(spy.count(), 0)
        self.assertEqual(
            panel.glossary_edit.toPlainText().splitlines(),
            ["ProjectBTerm"],
        )

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_auto_glossary_handles_provider_failure_gracefully(self):
        class ErrorProvider:
            def translate(self, prompt: str) -> str:
                raise ValueError("API Key is required for Gemini Provider")

        panel = TranscriptionContextPanel()
        panel.auto_glossary_timer.setInterval(30)
        panel.set_llm_provider_factory(lambda: ErrorProvider())
        panel.context_edit.setPlainText("Tóm tắt nội dung video tiếng Nhật")
        panel.debounce_timer.stop()

        for _ in range(30):
            if "API Key" in panel.diagnostics_label.text():
                break
            QTest.qWait(30)

        self.assertTrue(panel.btn_auto_glossary.isChecked())
        self.assertEqual(panel.btn_auto_glossary.text(), "✨ Auto Glossary: ON")
        self.assertIn("API Key", panel.diagnostics_label.text())

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_auto_glossary_works_offline_by_default_without_api_key(self):
        panel = TranscriptionContextPanel()
        panel.auto_glossary_timer.setInterval(30)
        panel.debounce_timer.setInterval(20)
        panel.context_edit.setPlainText(
            "Trận chiến tại Demacia giữa Garen, Lux và FastAPI trong「呪術廻戦」"
        )

        for _ in range(40):
            if "✓ Extracted" in panel.diagnostics_label.text():
                break
            QTest.qWait(25)

        extracted_lines = panel.glossary_edit.toPlainText().splitlines()
        for expected in ["呪術廻戦", "Demacia", "Garen", "Lux", "FastAPI"]:
            self.assertIn(expected, extracted_lines)
        self.assertIn("✓ Extracted", panel.diagnostics_label.text())

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_auto_glossary_zero_terms_preserves_compiled_diagnostics_without_warning_icon(self):
        panel = TranscriptionContextPanel()
        panel.auto_glossary_timer.setInterval(20)
        panel.set_llm_provider_factory(lambda: type("EmptyProvider", (), {"translate": lambda self, p: ""})())
        panel.set_prompt_diagnostics(
            CompiledPromptContext("Context: hôm nay", 6, 180, 0, 0, False, False)
        )
        panel.context_edit.setPlainText("hôm nay trời đẹp")
        panel.debounce_timer.stop()

        for _ in range(30):
            if panel._last_extracted_key is not None:
                break
            QTest.qWait(25)

        self.assertIsNotNone(panel._last_extracted_key)
        self.assertNotIn("⚠", panel.diagnostics_label.text())
        self.assertIn("0/0 glossary · ~6/180 tokens", panel.diagnostics_label.text())

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_switching_video_language_replaces_stale_auto_terms_and_keeps_manual_terms(self):
        current_lang = "vi"
        panel = TranscriptionContextPanel()
        panel.auto_glossary_timer.setInterval(25)
        panel.debounce_timer.setInterval(20)
        panel.set_language_getter(lambda: current_lang)

        # User manually adds a custom character name first
        panel.glossary_edit.setPlainText("Artorias")
        panel.context_edit.setPlainText(
            "Anh hùng chiến đấu với quái vật giải cứu người dân"
        )

        for _ in range(40):
            if "Ngươi" in panel.glossary_edit.toPlainText():
                break
            QTest.qWait(25)

        vi_lines = panel.glossary_edit.toPlainText().splitlines()
        self.assertIn("Artorias", vi_lines)
        self.assertIn("Ta", vi_lines)
        self.assertIn("Ngươi", vi_lines)

        # Now user changes video language from "vi" to "ja"
        current_lang = "ja"
        panel.on_video_language_changed("ja")

        for _ in range(40):
            if "貴様" in panel.glossary_edit.toPlainText():
                break
            QTest.qWait(25)

        ja_lines = panel.glossary_edit.toPlainText().splitlines()
        self.assertIn("Artorias", ja_lines)
        self.assertIn("貴様", ja_lines)
        self.assertIn("勇者様", ja_lines)
        self.assertNotIn("Ngươi", ja_lines)
        self.assertNotIn("Thảo dân", ja_lines)

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_changing_summary_to_zero_term_or_empty_clears_stale_auto_managed_terms(self):
        panel = TranscriptionContextPanel()
        panel.auto_glossary_timer.setInterval(20)
        panel.debounce_timer.setInterval(20)
        panel.set_language_getter(lambda: "vi")
        panel.glossary_edit.setPlainText("ManualTerm")
        panel.context_edit.setPlainText("Anh hùng chiến đấu với quái vật")

        for _ in range(40):
            if "Ngươi" in panel.glossary_edit.toPlainText():
                break
            QTest.qWait(25)

        self.assertIn("Ngươi", panel.glossary_edit.toPlainText().splitlines())
        self.assertIn("ManualTerm", panel.glossary_edit.toPlainText().splitlines())

        # Replace summary with a plain casual sentence yielding 0 glossary terms
        panel.context_edit.setPlainText("hôm nay trời đẹp quá")
        for _ in range(40):
            if "Ngươi" not in panel.glossary_edit.toPlainText():
                break
            QTest.qWait(25)

        self.assertEqual(panel.glossary_edit.toPlainText().splitlines(), ["ManualTerm"])

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_on_video_language_changed_triggers_immediately_without_waiting_for_2s_timer(self):
        current_lang = "vi"
        panel = TranscriptionContextPanel()
        # Keep the 2000ms timer long so we prove language change does not wait for it
        panel.auto_glossary_timer.setInterval(2000)
        panel.set_language_getter(lambda: current_lang)
        panel.context_edit.setPlainText("Anh hùng chiến đấu với quái vật")

        current_lang = "ja"
        panel.on_video_language_changed("ja")
        self.assertFalse(panel.auto_glossary_timer.isActive())

        for _ in range(25):
            if "貴様" in panel.glossary_edit.toPlainText():
                break
            QTest.qWait(20)

        self.assertIn("貴様", panel.glossary_edit.toPlainText().splitlines())


if __name__ == "__main__":
    unittest.main()

