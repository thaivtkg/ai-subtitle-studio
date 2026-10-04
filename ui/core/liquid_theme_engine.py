"""Single QSS compiler for AI Subtitle Studio.

Compiles stylesheet from ui.core.design_tokens. Supports optional wallpaper
mode for the liquid glass environment, while keeping content surfaces solid
and readable.
"""

from string import Template
from ui.core.design_tokens import (
    ColorToken,
    RadiusToken,
    SizeToken,
    SpacingToken,
    TypographyToken,
)


def _vars() -> dict:
    return {
        "BG_APP": ColorToken.BG_APP,
        "SURFACE": ColorToken.SURFACE,
        "SURFACE_ELEVATED": ColorToken.SURFACE_ELEVATED,
        "SURFACE_SOFT": ColorToken.SURFACE_SOFT,
        "BORDER": ColorToken.BORDER,
        "PRIMARY": ColorToken.PRIMARY,
        "PRIMARY_HOVER": ColorToken.PRIMARY_HOVER,
        "PRIMARY_PINK": ColorToken.PRIMARY_PINK,
        "PRIMARY_GREEN": ColorToken.PRIMARY_GREEN,
        "PRIMARY_GRADIENT": ColorToken.PRIMARY_GRADIENT,
        "ACCENT": ColorToken.ACCENT,
        "ACCENT_HOVER": ColorToken.ACCENT_HOVER,
        "SUCCESS": ColorToken.SUCCESS,
        "DANGER": ColorToken.DANGER,
        "WARNING": ColorToken.WARNING,
        "INFO": ColorToken.INFO,
        "TEXT_PRIMARY": ColorToken.TEXT_PRIMARY,
        "TEXT_SECONDARY": ColorToken.TEXT_SECONDARY,
        "TEXT_MUTED": ColorToken.TEXT_MUTED,
        "TEXT_DISABLED": ColorToken.TEXT_DISABLED,
        "GLASS_SURFACE": ColorToken.GLASS_SURFACE,
        "GLASS_EDGE": ColorToken.GLASS_EDGE,
        "GLASS_EDGE_TOP": ColorToken.GLASS_EDGE_TOP,
        "HOVER_OVERLAY": ColorToken.HOVER_OVERLAY,
        "SELECTED_SURFACE": ColorToken.SELECTED_SURFACE,
        "RADIUS_INNER": f"{RadiusToken.INNER}px",
        "RADIUS_CONTROL": f"{RadiusToken.CONTROL}px",
        "RADIUS_SURFACE": f"{RadiusToken.SURFACE}px",
        "RADIUS_FLOATING": f"{RadiusToken.FLOATING}px",
        "RADIUS_PILL": f"{RadiusToken.PILL}px",
        "SPACE_XS": f"{SpacingToken.XS}px",
        "SPACE_SM": f"{SpacingToken.SM}px",
        "SPACE_MD": f"{SpacingToken.MD}px",
        "SPACE_LG": f"{SpacingToken.LG}px",
        "SPACE_XL": f"{SpacingToken.XL}px",
        "CONTROL_HEIGHT": f"{SizeToken.CONTROL_HEIGHT}px",
        "ICON_BUTTON": f"{SizeToken.ICON_BUTTON}px",
        "SIDEBAR_WIDTH": f"{SizeToken.SIDEBAR_WIDTH}px",
        "TOPBAR_HEIGHT": f"{SizeToken.TOPBAR_HEIGHT}px",
        "FONT_FAMILY": TypographyToken.FONT_FAMILY,
        "FONT_CAPTION": f"{TypographyToken.CAPTION}px",
        "FONT_BODY": f"{TypographyToken.BODY}px",
        "FONT_SECTION_TITLE": f"{TypographyToken.SECTION_TITLE}px",
        "FONT_PAGE_TITLE": f"{TypographyToken.PAGE_TITLE}px",
    }


_QSS = Template("""
/* ==========================================================
   1. ROOT & GLOBAL RESET
   ========================================================== */
QWidget {
    font-family: $FONT_FAMILY;
    font-size: $FONT_BODY;
    color: $TEXT_PRIMARY;
    background-color: transparent;
}

QMainWindow, QDialog, QStackedWidget {
    background-color: $BG_APP;
}

QToolTip {
    background-color: $SURFACE_ELEVATED;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER;
    border-radius: $RADIUS_CONTROL;
    padding: $SPACE_XS $SPACE_SM;
    font-size: $FONT_CAPTION;
}

/* ==========================================================
   2. CONTENT SURFACES (SOLID, 16px, READABLE)
   ========================================================== */
.ContentSurface {
    background-color: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: $RADIUS_SURFACE;
}

.ContentElevated {
    background-color: $SURFACE_ELEVATED;
    border: 1px solid $BORDER;
    border-radius: $RADIUS_SURFACE;
}

/* ==========================================================
   3. GLASS SURFACES (FUNCTIONAL LAYER ONLY, 24px)
   ========================================================== */
.GlassPanel,
QDockWidget > QWidget,
QDockWidget#SubtitleGenerationDock {
    background-color: $GLASS_SURFACE;
    border: 1px solid $GLASS_EDGE;
    border-top: 1px solid $GLASS_EDGE_TOP;
    border-radius: $RADIUS_FLOATING;
}

QDockWidget#SidebarDock {
    background: transparent;
    border: none;
    border-radius: 0px;
}

QDockWidget {
    background: transparent;
    color: $TEXT_PRIMARY;
}

QDockWidget::title {
    background: transparent;
    padding: $SPACE_SM $SPACE_MD;
    color: $TEXT_PRIMARY;
    font-weight: 600;
}

/* Window frame panels */
#SidebarFrame {
    background-color: $GLASS_SURFACE;
    border-right: 1px solid $GLASS_EDGE;
    border-top: none;
    border-bottom: none;
    border-left: none;
    border-radius: 0px;
}

#TopbarFrame, #RightArea {
    background-color: $BG_APP;
    border: none;
}

#BottomFrame {
    background-color: $SURFACE;
    border: none;
    border-top: 1px solid $BORDER;
}

/* ==========================================================
   4. TYPOGRAPHY & LABELS
   ========================================================== */
QLabel[class="PageTitle"] {
    font-size: $FONT_PAGE_TITLE;
    font-weight: 600;
    color: #FFFFFF;
}

QLabel[class="SectionTitle"] {
    font-size: $FONT_SECTION_TITLE;
    font-weight: 600;
    color: $TEXT_PRIMARY;
}

QLabel[class="Caption"] {
    font-size: $FONT_CAPTION;
    color: $TEXT_SECONDARY;
}

QLabel[class="Muted"] {
    color: $TEXT_MUTED;
}

QLabel[class="EmptyState"] {
    font-size: 15px;
    color: $TEXT_MUTED;
}

QLabel[class="Accent"] {
    color: $ACCENT;
    font-weight: 600;
}

QLabel[state="danger"] { color: $DANGER; }
QLabel[state="success"] { color: $SUCCESS; }
QLabel[state="warning"] { color: $WARNING; }
QLabel[state="muted"] { color: $TEXT_MUTED; }

/* ==========================================================
   5. GROUPING (SECTION SPACING INSTEAD OF BOXED BORDERS)
   ========================================================== */
QGroupBox {
    background: transparent;
    border: none;
    margin-top: $SPACE_LG;
    padding-top: $SPACE_SM;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0px;
    padding: 0px;
    color: $TEXT_PRIMARY;
    font-size: $FONT_SECTION_TITLE;
    font-weight: 600;
}

QGroupBox:disabled::title {
    color: $TEXT_DISABLED;
}

/* ==========================================================
   6. TABS (8px STANDARD CONTROL GEOMETRY)
   ========================================================== */
QTabWidget::pane {
    border: none;
    background: transparent;
}

QTabBar::tab {
    background: transparent;
    color: $TEXT_SECONDARY;
    padding: 6px $SPACE_MD;
    margin: $SPACE_XS 2px;
    border: none;
    border-radius: $RADIUS_CONTROL;
    font-weight: 600;
    min-height: 20px;
}

QTabBar::tab:hover:!selected {
    background-color: $HOVER_OVERLAY;
    color: $TEXT_PRIMARY;
}

QTabBar::tab:selected {
    background-color: $SELECTED_SURFACE;
    color: $TEXT_PRIMARY;
    font-weight: 600;
}

QTabBar::scroller {
    width: 28px;
}

QTabBar QToolButton {
    background: transparent;
    border: none;
    color: $TEXT_PRIMARY;
}

QTabBar QToolButton:hover {
    background: $HOVER_OVERLAY;
}

/* ==========================================================
   7. BUTTONS (STANDARD 8px, PILL ONLY FOR PRIMARY ACTIONS)
   ========================================================== */
QPushButton {
    background-color: transparent;
    color: $TEXT_PRIMARY;
    border: 1px solid transparent;
    border-radius: $RADIUS_CONTROL;
    padding: 6px $SPACE_MD;
    font-weight: 600;
    min-height: 20px;
}

QPushButton:hover {
    background-color: $SURFACE_SOFT;
    border-color: $BORDER;
}

QPushButton:pressed {
    background-color: $SURFACE_ELEVATED;
}

QPushButton:disabled {
    color: $TEXT_DISABLED;
    background-color: transparent;
    border-color: transparent;
}

QPushButton:focus {
    border-color: $ACCENT;
}

/* Primary actions */
QPushButton#btn_primary,
QPushButton[variant="primary"],
QPushButton[variant="pill"] {
    background-color: $PRIMARY;
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}

QPushButton#btn_primary:hover,
QPushButton[variant="primary"]:hover,
QPushButton[variant="pill"]:hover {
    background-color: $PRIMARY_HOVER;
}

QPushButton#btn_primary:disabled,
QPushButton[variant="primary"]:disabled,
QPushButton[variant="pill"]:disabled {
    background-color: $SURFACE_SOFT;
    color: $TEXT_DISABLED;
}

QPushButton[variant="pill"] {
    border-radius: $RADIUS_PILL;
}

/* Secondary controls */
QPushButton#btn_secondary,
QPushButton[variant="secondary"] {
    background-color: $SURFACE_ELEVATED;
    border: 1px solid $BORDER;
}

QPushButton#btn_secondary:hover,
QPushButton[variant="secondary"]:hover {
    border-color: $ACCENT;
    background-color: $SURFACE_SOFT;
}

/* Semantic variants */
QPushButton[variant="success"] {
    background-color: $SUCCESS;
    color: $BG_APP;
    border: none;
}

QPushButton[variant="warning"],
QPushButton#btn_warning {
    background-color: $WARNING;
    color: #0D111A;
    font-weight: 700;
    border: none;
}

QPushButton[variant="warning"]:hover,
QPushButton#btn_warning:hover {
    background-color: #D97706;
}

QPushButton[variant="danger"],
QPushButton#btn_danger {
    color: $DANGER;
    border: 1px solid $DANGER;
    background-color: transparent;
}

QPushButton[variant="danger"]:hover,
QPushButton#btn_danger:hover {
    background-color: $DANGER;
    color: #FFFFFF;
}

/* Compact icon / window buttons */
QPushButton[variant="icon"],
QPushButton[variant="window"],
QPushButton[variant="window-close"] {
    padding: 0px;
    color: $TEXT_SECONDARY;
    font-size: 16px;
    border-radius: $RADIUS_CONTROL;
    border: none;
}

QPushButton[variant="icon"]:hover,
QPushButton[variant="window"]:hover {
    background-color: $SURFACE_SOFT;
    color: $TEXT_PRIMARY;
}

QPushButton[variant="window-close"]:hover {
    background-color: $DANGER;
    color: #FFFFFF;
}

/* Handle toggle button for drawer */
QPushButton[variant="handle"] {
    background-color: $SURFACE_ELEVATED;
    border: 1px solid $BORDER;
    border-right: none;
    border-top-left-radius: $RADIUS_CONTROL;
    border-bottom-left-radius: $RADIUS_CONTROL;
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
    color: $TEXT_SECONDARY;
    padding: 0px;
    font-size: 16px;
}

QPushButton[variant="handle"]:hover {
    background-color: $SURFACE_SOFT;
    color: $TEXT_PRIMARY;
}

/* Liquid Nav Buttons (Sidebar Activity Bar with Spring Physics Underlay) */
QPushButton[variant="liquid-nav-btn"] {
    background-color: transparent;
    border: none;
    border-radius: $RADIUS_CONTROL;
    color: $TEXT_SECONDARY;
    font-size: 16px;
    font-weight: 500;
    padding: 0px;
}

QPushButton[variant="liquid-nav-btn"]:hover {
    background-color: transparent;
    border: none;
    color: $TEXT_PRIMARY;
}

QPushButton[variant="liquid-nav-btn"]:pressed {
    background-color: transparent;
    border: none;
    color: #FFFFFF;
}

QPushButton[variant="liquid-nav-btn"][active="true"] {
    background-color: transparent;
    border: none;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton[variant="liquid-nav-btn"]:focus {
    border: none;
    outline: none;
}

/* Navigation item buttons (Sidebar Activity Bar - 8px Standard) */
QPushButton[variant="nav-item"] {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: $RADIUS_CONTROL;
    color: $TEXT_SECONDARY;
    font-size: 16px;
    font-weight: 500;
    padding: 0px;
}

QPushButton[variant="nav-item"]:hover {
    background-color: $HOVER_OVERLAY;
    border: 1px solid $GLASS_EDGE;
    color: $TEXT_PRIMARY;
}

QPushButton[variant="nav-item"]:pressed {
    background-color: $SURFACE_ELEVATED;
    color: #FFFFFF;
}

QPushButton[variant="nav-item"][active="true"] {
    background-color: rgba(99, 102, 241, 0.20);
    border: 1px solid rgba(99, 102, 241, 0.45);
    color: $ACCENT;
    font-weight: 600;
}

QPushButton[variant="nav-item"]:focus {
    border-color: $ACCENT;
}

/* Dropdown Menus (Project & Tools Menu in Topbar) */
QMenu {
    background-color: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: $RADIUS_CONTROL;
    padding: $SPACE_XS;
    color: $TEXT_PRIMARY;
}

QMenu::item {
    background: transparent;
    padding: 6px $SPACE_MD;
    border-radius: $RADIUS_INNER;
    color: $TEXT_PRIMARY;
    font-size: $FONT_BODY;
}

QMenu::item:selected {
    background-color: $HOVER_OVERLAY;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background-color: $BORDER;
    margin: $SPACE_XS 0px;
}

/* ==========================================================
   8. INPUTS & CONTROLS (32px HEIGHT, 8px RADIUS, SOLID)
   ========================================================== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: $SURFACE_ELEVATED;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER;
    border-radius: $RADIUS_CONTROL;
    padding: 5px $SPACE_SM;
    min-height: 20px;
    selection-background-color: $PRIMARY;
}

QTextEdit, QPlainTextEdit {
    background-color: $SURFACE_ELEVATED;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER;
    border-radius: $RADIUS_CONTROL;
    padding: 4px $SPACE_SM;
    selection-background-color: $PRIMARY;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {
    border-color: $ACCENT;
    background-color: $SURFACE_SOFT;
}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: $TEXT_DISABLED;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: $SURFACE_ELEVATED;
    border: 1px solid $BORDER;
    selection-background-color: $PRIMARY;
    outline: 0px;
}

/* ==========================================================
   9. CHECKBOX, RADIO, SLIDER (4px INNER RADIUS)
   ========================================================== */
QCheckBox, QRadioButton {
    spacing: $SPACE_SM;
    color: $TEXT_PRIMARY;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $BORDER;
    background-color: $SURFACE_ELEVATED;
}

QCheckBox::indicator {
    border-radius: $RADIUS_INNER;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: $ACCENT;
}

QCheckBox::indicator:checked {
    background-color: $ACCENT;
    border-color: $ACCENT;
    image: url(assets/check.svg);
}

QCheckBox[settingsCheckbox="true"]:disabled {
    color: $TEXT_DISABLED;
}

QCheckBox[settingsCheckbox="true"]::indicator:unchecked {
    background-color: $SURFACE_SOFT;
    border: 1px solid $TEXT_MUTED;
    border-radius: $RADIUS_INNER;
}

QCheckBox[settingsCheckbox="true"]::indicator:unchecked:disabled {
    background-color: $SURFACE;
    border: 1px solid $TEXT_DISABLED;
}

QSlider::groove:horizontal {
    height: 4px;
    border-radius: 2px;
    background: $SURFACE_SOFT;
}

QSlider::sub-page:horizontal {
    background: $PRIMARY;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: $TEXT_PRIMARY;
    width: 12px;
    height: 12px;
    margin: -4px 0px;
    border-radius: 6px;
}

QSlider::handle:horizontal:hover {
    background: $ACCENT;
}

/* ==========================================================
   10. LISTS, TABLES, PROGRESS BARS
   ========================================================== */
QListWidget {
    background: transparent;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: $SPACE_SM $SPACE_MD;
    margin-bottom: $SPACE_XS;
    border-radius: $RADIUS_CONTROL;
    color: $TEXT_SECONDARY;
}

QListWidget::item:hover {
    background-color: $HOVER_OVERLAY;
    color: $TEXT_PRIMARY;
}

QListWidget::item:selected {
    background-color: $SELECTED_SURFACE;
    color: $TEXT_PRIMARY;
    font-weight: 600;
}

QTableWidget, QTableView {
    background-color: $SURFACE;
    color: $TEXT_PRIMARY;
    border: none;
    gridline-color: $BORDER;
    selection-background-color: $SELECTED_SURFACE;
    selection-color: $TEXT_PRIMARY;
    outline: none;
}

QHeaderView::section {
    background-color: $SURFACE;
    color: $TEXT_SECONDARY;
    border: none;
    border-bottom: 1px solid $BORDER;
    padding: 6px $SPACE_SM;
    font-weight: 600;
}

QProgressBar {
    background-color: $SURFACE_SOFT;
    border: none;
    border-radius: $RADIUS_INNER;
    min-height: 6px;
    max-height: 8px;
}

QProgressBar::chunk {
    background: $PRIMARY_GRADIENT;
    border-radius: $RADIUS_INNER;
}

/* ==========================================================
   11. SCROLLBARS & SPLITTERS
   ========================================================== */
QScrollBar:vertical, QScrollBar:horizontal {
    border: none;
    background: transparent;
    margin: 0px;
}

QScrollBar:vertical { width: 8px; }
QScrollBar:horizontal { height: 8px; }

QScrollBar::handle {
    background: $SURFACE_SOFT;
    border-radius: $RADIUS_INNER;
}

QScrollBar::handle:hover {
    background: $TEXT_DISABLED;
}

QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
    border: none;
}

QSplitter::handle {
    background-color: transparent;
    margin: 1px 0px;
}

QSplitter::handle:hover {
    background-color: $ACCENT;
}

QSplitter::handle:horizontal { width: 3px; }
QSplitter::handle:vertical { height: 3px; }
""")

_WALLPAPER = Template("""
QMainWindow {
    background-color: #000000;
    border-image: url(liquid_wallpaper.jpg) 0 0 0 0 stretch stretch;
}
QMainWindow > QDockWidget#SidebarDock,
QDockWidget#SubtitleGenerationDock {
    background: transparent;
}
""")


class LiquidThemeEngine:
    @staticmethod
    def compile_stylesheet(wallpaper: bool = False) -> str:
        v = _vars()
        return _QSS.substitute(v) + (_WALLPAPER.substitute(v) if wallpaper else "")
