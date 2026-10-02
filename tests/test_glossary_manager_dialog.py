import unittest
import sys
from PySide6.QtWidgets import QApplication
from core.database.glossary_manager import GlossaryManager

if not QApplication.instance():
    app = QApplication(sys.argv)

from ui.glossary.glossary_manager_dialog import GlossaryManagerDialog, parse_glossary_csv_text


class TestGlossaryManagerDialog(unittest.TestCase):
    def setUp(self):
        self.mgr = GlossaryManager(db_path=":memory:")
        self.mgr.add_entry("Bankai", "Giải phóng", domain="Anime", lang_pair="ja-vi")
        self.mgr.add_entry("CPU", "Bộ xử lý", domain="IT", lang_pair="en-vi")
        self.dialog = GlossaryManagerDialog(manager=self.mgr)

    def test_dialog_loads_entries_into_table(self):
        self.assertEqual(self.dialog.table.rowCount(), 2)
        # Check source text of first row
        source_item = self.dialog.table.item(0, 0)
        self.assertIsNotNone(source_item)

    def test_dialog_filter_by_domain(self):
        self.dialog.domain_filter.setCurrentText("Anime")
        self.dialog._apply_filters()
        self.assertEqual(self.dialog.table.rowCount(), 1)
        self.assertEqual(self.dialog.table.item(0, 0).text(), "Bankai")

    def test_dialog_search_filter(self):
        self.dialog.search_edit.setText("Bộ xử lý")
        self.dialog._apply_filters()
        self.assertEqual(self.dialog.table.rowCount(), 1)
        self.assertEqual(self.dialog.table.item(0, 0).text(), "CPU")

    def test_parse_csv_text_comma(self):
        csv_data = "Source,Target,Domain,LangPair\nRasengan,La Toàn Hoàn,Anime,ja-vi\nSharingan,Tả Luân Nhãn"
        entries = parse_glossary_csv_text(csv_data)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["source_text"], "Rasengan")
        self.assertEqual(entries[0]["target_text"], "La Toàn Hoàn")
        self.assertEqual(entries[0]["domain"], "Anime")
        self.assertEqual(entries[0]["lang_pair"], "ja-vi")
        self.assertEqual(entries[1]["source_text"], "Sharingan")
        self.assertEqual(entries[1]["target_text"], "Tả Luân Nhãn")
        self.assertEqual(entries[1]["domain"], "general")

    def test_parse_csv_text_arrow(self):
        text_data = "Chidori -> Thiên Điểu\nAmaterasu = Thiên Chiếu"
        entries = parse_glossary_csv_text(text_data)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["source_text"], "Chidori")
        self.assertEqual(entries[0]["target_text"], "Thiên Điểu")
        self.assertEqual(entries[1]["source_text"], "Amaterasu")
        self.assertEqual(entries[1]["target_text"], "Thiên Chiếu")


if __name__ == "__main__":
    unittest.main()
