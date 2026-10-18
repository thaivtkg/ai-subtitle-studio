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
    def test_auto_glossary_button_extracts_terms_and_merges_with_existing_glossary(self):
        class StubProvider:
            def __init__(self):
                self.last_prompt = None

            def translate(self, prompt: str) -> str:
                self.last_prompt = prompt
                return "1. 非同期処理\n2. イベントループ\n3. FastAPI\n4. python"

        stub = StubProvider()
        panel = TranscriptionContextPanel()
        panel.set_llm_provider_factory(lambda: stub)
        panel.set_language_getter(lambda: "ja")
        panel.context_edit.setPlainText("Video hướng dẫn lập trình bất đồng bộ Python")
        panel.glossary_edit.setPlainText("Python")
        panel.domain_edit.setText("Programming")
        panel.debounce_timer.stop()

        spy = QSignalSpy(panel.context_committed)
        panel.btn_auto_glossary.click()

        for _ in range(40):
            if spy.count() > 0:
                break
            QTest.qWait(25)
        self.assertEqual(spy.count(), 1)
        self.assertTrue(panel.btn_auto_glossary.isEnabled())
        self.assertIn("Japanese", stub.last_prompt)
        self.assertIn("Programming", stub.last_prompt)
        self.assertIn("✓ Extracted 4 glossary term(s) (3 new)", panel.diagnostics_label.text())
        self.assertEqual(
            panel.glossary_edit.toPlainText().splitlines(),
            ["Python", "非同期処理", "イベントループ", "FastAPI"],
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
        panel.set_llm_provider_factory(lambda: SlowProvider())
        panel.context_edit.setPlainText("Summary of Project A")
        panel.debounce_timer.stop()

        spy = QSignalSpy(panel.context_committed)
        panel.btn_auto_glossary.click()
        self.assertTrue(started.wait(timeout=1.0))
        self.assertFalse(panel.btn_auto_glossary.isEnabled())

        panel.set_context(TranscriptionContext("Project B", ["ProjectBTerm"]))
        self.assertTrue(panel.btn_auto_glossary.isEnabled())
        self.assertEqual(panel.btn_auto_glossary.text(), "✨ Auto Glossary")

        release.set()
        QTest.qWait(100)

        self.assertEqual(spy.count(), 0)
        self.assertEqual(
            panel.glossary_edit.toPlainText().splitlines(),
            ["ProjectBTerm"],
        )

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_auto_glossary_with_empty_summary_shows_warning_without_calling_provider(self):
        called = False

        class FailingIfCalledProvider:
            def translate(self, prompt: str) -> str:
                nonlocal called
                called = True
                return "Term"

        panel = TranscriptionContextPanel()
        panel.set_llm_provider_factory(lambda: FailingIfCalledProvider())
        panel.context_edit.setPlainText("   ")
        panel.btn_auto_glossary.click()

        self.assertFalse(called)
        self.assertIn("⚠", panel.diagnostics_label.text())

    @unittest.skipIf(TranscriptionContextPanel is None, "UI dependencies unavailable")
    def test_auto_glossary_handles_provider_failure_gracefully(self):
        class ErrorProvider:
            def translate(self, prompt: str) -> str:
                raise ValueError("API Key is required for Gemini Provider")

        panel = TranscriptionContextPanel()
        panel.set_llm_provider_factory(lambda: ErrorProvider())
        panel.context_edit.setPlainText("Tóm tắt nội dung video tiếng Nhật")
        panel.debounce_timer.stop()

        panel.btn_auto_glossary.click()
        for _ in range(20):
            if panel.btn_auto_glossary.isEnabled() and "API Key" in panel.diagnostics_label.text():
                break
            QTest.qWait(50)

        self.assertTrue(panel.btn_auto_glossary.isEnabled())
        self.assertIn("API Key", panel.diagnostics_label.text())


if __name__ == "__main__":
    unittest.main()
