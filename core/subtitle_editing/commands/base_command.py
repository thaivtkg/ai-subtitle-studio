from PySide6.QtGui import QUndoCommand


class SubtitleCommand(QUndoCommand):
    """Base class for subtitle editing commands managed by QUndoStack."""

    def __init__(self, text: str, data_provider=None, parent: QUndoCommand = None):
        super().__init__(text, parent)
        self.data_provider = data_provider
        self._stt_schema = bool(data_provider and any("stt" in segment for segment in data_provider))

    def _renumber_stt(self):
        if not self.data_provider:
            return
        # Empty-list Add creates the first production segment with id/stt.
        if not self._stt_schema and not all("id" in segment for segment in self.data_provider):
            return
        for index, segment in enumerate(self.data_provider):
            segment["stt"] = str(index + 1)

    def undo(self):
        raise NotImplementedError("Lệnh undo() phải được override ở lớp con.")

    def redo(self):
        raise NotImplementedError("Lệnh redo() phải được override ở lớp con.")
