from ui.core.design_tokens import ColorToken as C
from ui.core.liquid_theme_engine import LiquidThemeEngine


class Theme:
    """Backward-compatible color aliases. Values live in ui.core.design_tokens (single source)."""

    BG_APP = C.BG_APP
    SURFACE = C.SURFACE
    SURFACE_ELEVATED = C.SURFACE_ELEVATED
    SURFACE_SOFT = C.SURFACE_SOFT

    PRIMARY_PURPLE = C.PRIMARY
    PRIMARY_PINK = C.PRIMARY_PINK
    PRIMARY_GRADIENT = C.PRIMARY_GRADIENT
    PRIMARY_GREEN = C.PRIMARY_GREEN

    CYAN = C.ACCENT
    SUCCESS = C.SUCCESS
    DANGER = C.DANGER
    WARNING = C.WARNING
    INFO = C.INFO

    TEXT_PRIMARY = C.TEXT_PRIMARY
    TEXT_SECONDARY = C.TEXT_SECONDARY
    TEXT_MUTED = C.TEXT_MUTED
    TEXT_DISABLED = C.TEXT_DISABLED
    BORDER = C.BORDER

    @classmethod
    def get_global_stylesheet(cls):
        return LiquidThemeEngine.compile_stylesheet()

    @classmethod
    def get_liquid_stylesheet(cls):
        return LiquidThemeEngine.compile_stylesheet(wallpaper=True)
