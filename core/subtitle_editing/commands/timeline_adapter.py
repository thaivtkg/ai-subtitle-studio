from PySide6.QtGui import QUndoCommand


class TimelineCommandAdapter(QUndoCommand):
    """Bridges legacy timeline commands into the application's QUndoStack."""
    def __init__(self, command):
        super().__init__(getattr(command, "description", "Timeline edit"))
        self.command = command
        self._executed = False

    def redo(self):
        if self._executed:
            self.command.redo()
        else:
            self.command.execute(context=None)
            self._executed = True

    def undo(self):
        self.command.undo()
