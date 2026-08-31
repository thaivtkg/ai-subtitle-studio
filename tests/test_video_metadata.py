import sys
import types
import unittest
from unittest.mock import patch

_using_pyside_stub = False
try:
    import PySide6  # noqa: F401
except ModuleNotFoundError:
    _using_pyside_stub = True
    qt_core = types.ModuleType("PySide6.QtCore")
    qt_core.QThread = type("QThread", (), {})
    qt_core.Signal = lambda *args, **kwargs: None
    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qt_core
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qt_core

from core.video_metadata import VideoMetadataExtractor

if _using_pyside_stub:
    sys.modules.pop("PySide6.QtCore", None)
    sys.modules.pop("PySide6", None)


class VideoMetadataExtractorTests(unittest.TestCase):
    @staticmethod
    def _probe_data(format_name):
        return {
            "format": {
                "format_name": format_name,
                "duration": "60.0",
            },
            "streams": [],
        }

    @patch("core.video_metadata.os.path.getsize", return_value=1024)
    def test_mp4_extension_selects_mp4_from_ffprobe_aliases(self, _getsize):
        metadata = VideoMetadataExtractor._parse_ffprobe_data(
            "example.mp4",
            self._probe_data("mov,mp4,m4a,3gp,3g2,mj2"),
        )

        self.assertEqual(metadata["format"], "MP4")

    @patch("core.video_metadata.os.path.getsize", return_value=1024)
    def test_mov_extension_keeps_mov_from_ffprobe_aliases(self, _getsize):
        metadata = VideoMetadataExtractor._parse_ffprobe_data(
            "example.mov",
            self._probe_data("mov,mp4,m4a,3gp,3g2,mj2"),
        )

        self.assertEqual(metadata["format"], "MOV")


if __name__ == "__main__":
    unittest.main()
