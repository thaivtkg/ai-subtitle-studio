import unittest
from core.subtitle_quality.auto_qc_service import AutoQCService

class TestAutoQCService(unittest.TestCase):
    def test_glossary_adherence_success(self):
        glossary_map = {"Katarina": "Ác Kiếm", "Garen": "Sức Mạnh Của Demacia"}
        source = "Katarina is here."
        translated = "Ác Kiếm đã ở đây."
        
        flags = AutoQCService.evaluate_segment(source, translated, glossary_map)
        self.assertEqual(len(flags), 0)

    def test_glossary_adherence_failure(self):
        glossary_map = {"Katarina": "Ác Kiếm"}
        source = "Katarina is here."
        translated = "Katarina đã ở đây."
        
        flags = AutoQCService.evaluate_segment(source, translated, glossary_map)
        self.assertIn("glossary_violation", flags)
        self.assertIn("missing_term: Ác Kiếm", flags)

    def test_format_injection_brackets(self):
        glossary_map = {}
        source = "Hello there."
        translated = "Xin chào. [Nhạc nền]"
        
        flags = AutoQCService.evaluate_segment(source, translated, glossary_map)
        self.assertIn("format_injection: [] brackets", flags)

    def test_format_injection_parens(self):
        glossary_map = {}
        source = "Hello there."
        translated = "Xin chào. (Translated literally)"
        
        flags = AutoQCService.evaluate_segment(source, translated, glossary_map)
        self.assertIn("format_injection: () parens", flags)

    def test_format_injection_notes(self):
        glossary_map = {}
        source = "Hello there."
        translated = "Xin chào.\nNote: This is a note."
        
        flags = AutoQCService.evaluate_segment(source, translated, glossary_map)
        self.assertIn("format_injection: Note keyword", flags)

if __name__ == "__main__":
    unittest.main()
