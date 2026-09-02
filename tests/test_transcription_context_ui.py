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
        QTest.qWait(50)
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


if __name__ == "__main__":
    unittest.main()
