"""Single source of truth for the UI: legacy palette identity + P0 visual grammar.

Colors are the original AI Subtitle Studio palette (indigo primary, sky-blue focus,
navy surfaces) re-expressed as semantic tokens. Geometry follows the locked P0 grammar:
Control 8 / Surface 16 / Glass 24 / Pill. `ui.theme.Theme` aliases these values.
"""


class ColorToken:
    # Surfaces (solid content layers)
    BG_APP = "#0D111A"
    SURFACE = "#151A27"
    SURFACE_ELEVATED = "#1E2536"
    SURFACE_SOFT = "#262E40"
    BORDER = "#1E293B"

    # Brand / accents
    PRIMARY = "#6366F1"
    PRIMARY_HOVER = "#4F46E5"
    PRIMARY_PINK = "#EC4899"
    PRIMARY_GREEN = "#10B981"
    PRIMARY_GRADIENT = "qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #6366F1, stop: 1 #EC4899)"
    ACCENT = "#38BDF8"  # focus ring / small highlights

    # Status
    SUCCESS = "#10B981"
    DANGER = "#EF4444"
    WARNING = "#F59E0B"
    INFO = "#3B82F6"

    # Text
    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"
    TEXT_DISABLED = "#475569"

    # Functional glass (navigation layer only) + interaction overlays
    GLASS_SURFACE = "rgba(21, 26, 39, 0.78)"
    GLASS_EDGE = "rgba(255, 255, 255, 0.06)"
    GLASS_EDGE_TOP = "rgba(255, 255, 255, 0.14)"
    HOVER_OVERLAY = "rgba(255, 255, 255, 0.06)"
    SELECTED_SURFACE = "rgba(99, 102, 241, 0.18)"


class RadiusToken:
    INNER = 4      # checkbox, scrollbar handle, tiny tags
    CONTROL = 8    # input, combo, buttons, tabs, list items
    SURFACE = 16   # content surfaces, overlays, dialogs
    FLOATING = 24  # glass outer (sidebar, dock)
    PILL = 999     # primary floating action only


class SpacingToken:
    XS = 4
    SM = 8    # control-to-control, icon-to-text
    MD = 16
    LG = 24   # section-to-section, surface padding
    XL = 32


class SizeToken:
    CONTROL_HEIGHT = 32
    ICON_BUTTON = 36        # icon-only toolbar/sidebar button, one geometry everywhere
    SIDEBAR_WIDTH = 64
    TOPBAR_HEIGHT = 42


class TypographyToken:
    FONT_FAMILY = '"Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif'
    CAPTION = 11
    BODY = 13
    SECTION_TITLE = 13   # semi-bold
    PAGE_TITLE = 20
