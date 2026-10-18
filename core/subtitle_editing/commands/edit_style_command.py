from typing import List, Dict, Any
from core.subtitle_editing.commands.base_command import SubtitleCommand


class EditStyleCommand(SubtitleCommand):
    """Lệnh undo/redo thay đổi Style Preset của các dòng phụ đề."""

    def __init__(
        self,
        changes: List[Dict[str, Any]],
        data_provider: List[Dict[str, Any]],
        text: str = "Đổi Style phụ đề",
    ):
        super().__init__(text, data_provider)
        self.changes = changes

    def id(self) -> int:
        return 7

    def undo(self):
        for change in self.changes:
            idx = change["index"]
            if 0 <= idx < len(self.data_provider):
                self.data_provider[idx]["style_preset"] = change["old_preset"]

    def redo(self):
        for change in self.changes:
            idx = change["index"]
            if 0 <= idx < len(self.data_provider):
                self.data_provider[idx]["style_preset"] = change["new_preset"]
