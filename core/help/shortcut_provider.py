class RuntimeShortcutProvider:
    """Read-only view of the shortcuts currently registered by the UI."""

    def __init__(self, shortcut_source):
        self._shortcut_source = shortcut_source

    def entries(self):
        result = []
        for shortcut in self._shortcut_source():
            name = shortcut.objectName()
            sequence = (
                shortcut.key_sequence()
                if hasattr(shortcut, "key_sequence")
                else shortcut.key().toString()
            )
            if name and sequence:
                result.append((name, sequence))
        return tuple(result)
