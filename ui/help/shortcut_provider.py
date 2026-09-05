import weakref

import shiboken6
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QWidget

from core.help.help_models import RuntimeShortcutDescriptor


class RuntimeShortcutProvider:
    def __init__(self, window=None):
        self._window = weakref.ref(window) if window is not None else None

    def register_shortcut(self, shortcut, action_id, label, context="Global"):
        shortcut.setObjectName(action_id)
        shortcut.setProperty("help_label", label)
        shortcut.setProperty("help_context", context)

    def get_shortcuts(self):
        window = self._window() if self._window else None
        if window is None or not shiboken6.isValid(window):
            return ()
        result = []
        for shortcut in window.findChildren(QShortcut):
            if not shiboken6.isValid(shortcut):
                continue
            sequence = shortcut.key().toString()
            if not sequence:
                continue
            action_id = shortcut.objectName() or "unnamed_action"
            label = shortcut.property("help_label") or action_id.replace("_", " ").title()
            context = shortcut.property("help_context") or "Global"
            result.append(RuntimeShortcutDescriptor(action_id, label, sequence, context))
        return tuple(sorted(result, key=lambda item: item.action_id))
