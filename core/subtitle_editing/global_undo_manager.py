from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoStack

from core.subtitle_editing.commands.base_command import SubtitleCommand


class GlobalUndoManager(QObject):
    """Central undo/redo stack for subtitle editing state."""

    state_changed = Signal()
    clean_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self.clean_changed.emit)

    def push(self, command: SubtitleCommand):
        self.undo_stack.push(command)
        self.state_changed.emit()

    def undo(self):
        if self.undo_stack.canUndo():
            self.undo_stack.undo()
            self.state_changed.emit()
            return True
        return False

    def redo(self):
        if self.undo_stack.canRedo():
            self.undo_stack.redo()
            self.state_changed.emit()
            return True
        return False

    def clear(self):
        self.undo_stack.clear()

    def mark_saved(self):
        self.undo_stack.setClean()

    @property
    def is_dirty(self) -> bool:
        return not self.undo_stack.isClean()
