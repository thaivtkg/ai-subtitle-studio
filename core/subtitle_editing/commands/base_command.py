from PySide6.QtGui import QUndoCommand


class SubtitleCommand(QUndoCommand):
    """Base class for subtitle editing commands managed by QUndoStack."""

    def __init__(self, text: str, data_provider=None, parent: QUndoCommand = None):
        super().__init__(text, parent)
        self.data_provider = data_provider

    def undo(self):
        raise NotImplementedError("Lệnh undo() phải được override ở lớp con.")

    def redo(self):
        raise NotImplementedError("Lệnh redo() phải được override ở lớp con.")
