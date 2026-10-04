"""Single source of truth for the UI: legacy palette identity + P0 visual grammar.

Colors are the original AI Subtitle Studio palette (deep slate/navy surfaces,
indigo primary, sky-blue accent, pink secondary gradient) re-expressed as semantic tokens.
Geometry follows the locked P0 grammar:
Control 8px / Surface 16px / Glass 24px / Pill for primary actions.
`ui.theme.Theme` aliases these values for backward compatibility.
"""


class ColorToken:
    # Surfaces (solid content layers - Deep Slate / Navy Dark)
    BG_APP = "#0D111A"
    SURFACE = "#151A27"
    SURFACE_ELEVATED = "#1E2536"
    SURFACE_SOFT = "#262E40"
    BORDER = "#1E293B"

    # Brand / accents
    PRIMARY = "#6366F1"            # Indigo/Purple 500 (Core Brand Identity)
    PRIMARY_HOVER = "#4F46E5"      # Indigo 600
    PRIMARY_PINK = "#EC4899"       # Pink 500
    PRIMARY_GREEN = "#10B981"      # Emerald 500
    PRIMARY_GRADIENT = (
        "qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, "
        "stop: 0 #6366F1, stop: 1 #EC4899)"
    )
    ACCENT = "#38BDF8"             # Sky/Cyan (Focus ring / Active indicator)
    ACCENT_HOVER = "#0284C7"       # Sky 600

    # Semantic Status
    SUCCESS = "#10B981"
    DANGER = "#EF4444"
    WARNING = "#F59E0B"
    INFO = "#3B82F6"

    # Text hierarchy
    TEXT_PRIMARY = "#F8FAFC"       # Slate 50
    TEXT_SECONDARY = "#94A3B8"     # Slate 400
    TEXT_MUTED = "#64748B"         # Slate 500
    TEXT_DISABLED = "#475569"      # Slate 600

    # Functional glass (navigation layer only) + interaction overlays
    GLASS_SURFACE = "rgba(21, 26, 39, 0.78)"
    GLASS_EDGE = "rgba(255, 255, 255, 0.06)"
    GLASS_EDGE_TOP = "rgba(255, 255, 255, 0.14)"
    HOVER_OVERLAY = "rgba(255, 255, 255, 0.06)"
    SELECTED_SURFACE = "rgba(99, 102, 241, 0.18)"


class RadiusToken:
    INNER = 4      # Checkbox, radio, scrollbar handle, tiny tags
    CONTROL = 8    # Input, combo, buttons, tabs, list items
    SURFACE = 16   # Content surfaces, overlays, dialogs
    FLOATING = 24  # Glass outer (sidebar, dock)
    PILL = 999     # Primary floating action only


class SpacingToken:
    XS = 4
    SM = 8    # Control-to-control, icon-to-text
    MD = 16
    LG = 24   # Section-to-section, surface padding
    XL = 32


class SizeToken:
    CONTROL_HEIGHT = 32
    ICON_BUTTON = 36        # Standard icon-only button
    SIDEBAR_WIDTH = 64
    TOPBAR_HEIGHT = 42


class TypographyToken:
    FONT_FAMILY = '"Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif'
    CAPTION = 11
    BODY = 13
    SECTION_TITLE = 13   # Semi-bold, title case
    PAGE_TITLE = 20
