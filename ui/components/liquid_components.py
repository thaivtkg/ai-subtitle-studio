"""Shared visual primitives. All styling lives in ui.core.liquid_theme_engine (QSS by property)."""
from PySide6.QtWidgets import QFrame, QWidget


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_state(widget: QWidget, state: str) -> None:
    """Semantic label state: 'danger' | 'success' | 'muted' | '' (default)."""
    widget.setProperty("state", state)
    repolish(widget)


class ContentSurface(QFrame):
    """Solid, readable content layer (Workspace, Settings, pages). Never glass."""

    def __init__(self, parent=None, elevated=False):
        super().__init__(parent)
        self.setProperty("class", "ContentElevated" if elevated else "ContentSurface")


class GlassPanel(QFrame):
    """Functional glass layer (sidebar, AI dock). Navigation/tool surfaces only."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "GlassPanel")
