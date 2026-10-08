import copy
from core.subtitle_editing.commands.base_command import SubtitleCommand

class RestoreGenerationCommand(SubtitleCommand):
    """
    Command to restore the generation state to a specific checkpoint.
    Allows rolling back generation while maintaining the ability to Undo (Ctrl+Z) the rollback.
    """
    def __init__(self, before_segments, after_segments, data_provider):
        super().__init__("Restore Generation Checkpoint", data_provider)
        # Store deep copies to ensure they are static snapshots
        self.before_state = copy.deepcopy(before_segments)
        self.after_state = copy.deepcopy(after_segments)

    def undo(self):
        if self.data_provider is not None:
            self.data_provider.clear()
            # Deep copy to prevent data provider from mutating our snapshot
            self.data_provider.extend(copy.deepcopy(self.before_state))
            self._renumber_stt()

    def redo(self):
        if self.data_provider is not None:
            self.data_provider.clear()
            self.data_provider.extend(copy.deepcopy(self.after_state))
            self._renumber_stt()
