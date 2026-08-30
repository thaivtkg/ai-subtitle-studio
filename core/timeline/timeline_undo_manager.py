from core.timeline.timeline_commands import TimelineEditCommand

class UndoRedoManager:
    """Quản lý ngăn xếp Undo/Redo (Command Stack) với giới hạn kích thước an toàn"""
    
    def __init__(self, max_history: int = 50):
        self._undo_stack: list[TimelineEditCommand] = []
        self._redo_stack: list[TimelineEditCommand] = []
        self._max_history = max_history

    def execute_command(self, command: TimelineEditCommand, current_state) -> bool:
        if command.can_execute(current_state):
            command.execute(context=None)
            self._undo_stack.append(command)
            self._redo_stack.clear()  # Hủy nhánh Redo khi có thao tác mới
            
            # Tránh tràn RAM nếu lịch sử quá dài
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
            return True
        return False

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
            
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
            
        command = self._redo_stack.pop()
        command.redo()
        self._undo_stack.append(command)
        return True
        
    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()