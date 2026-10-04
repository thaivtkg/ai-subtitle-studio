"""Compiles the application stylesheet from design tokens (single stylesheet compiler).

Widgets opt in through objectName / dynamic properties, never inline QSS:
  surfaces : [class="ContentSurface"|"ContentElevated"|"GlassPanel"]
  labels   : [class="PageTitle"|"SectionTitle"|"Caption"|"Muted"|"EmptyState"|"Accent"], [state="danger"|"success"|"muted"]
  buttons  : [variant="primary"|"pill"|"secondary"|"success"|"danger"|"icon"|"window"|"window-close"|"handle"]
"""
from string import Template

from ui.core.design_tokens import ColorToken, RadiusToken, SizeToken, SpacingToken, TypographyToken


def _vars():
    v = {k: val for k, val in vars(ColorToken).items() if k.isupper()}
    v["FONT_FAMILY"] = TypographyToken.FONT_FAMILY
    for prefix, cls in (("RADIUS", RadiusToken), ("SPACE", SpacingToken), ("SIZE", SizeToken), ("FONT", TypographyToken)):
        v.update({f"{prefix}_{k}": f"{val}px" for k, val in vars(cls).items() if k.isupper() and isinstance(val, int)})
    return v


_QSS = Template("""
/* ROOT */
QWidget { font-family: $FONT_FAMILY; font-size: $FONT_BODY; color: $TEXT_PRIMARY; background-color: transparent; }
QMainWindow, QDialog, QDockWidget, QScrollArea, QStackedWidget { background-color: $BG_APP; }
QMainWindow[dropActive="true"] { border: 2px solid $PRIMARY; }
QToolTip { background-color: $SURFACE_ELEVATED; color: $TEXT_PRIMARY; border: 1px solid $BORDER; padding: $SPACE_XS $SPACE_SM; }
QDockWidget { border: none; }
QDockWidget::title { background: transparent; color: $TEXT_SECONDARY; padding: $SPACE_SM $SPACE_MD; font-weight: 600; }

/* SURFACES: content is solid, glass is for the navigation/functional layer only */
*[class="ContentSurface"] { background-color: $SURFACE; border: none; border-radius: $RADIUS_SURFACE; }
*[class="ContentElevated"] { background-color: $SURFACE_ELEVATED; border: none; border-radius: $RADIUS_SURFACE; }
*[class="GlassPanel"] { background-color: $GLASS_SURFACE; border: 1px solid $GLASS_EDGE; border-top-color: $GLASS_EDGE_TOP; border-radius: $RADIUS_FLOATING; }
QScrollArea#SidebarScroll { background: transparent; border: none; }
#TopbarFrame, #RightArea { background-color: $BG_APP; border: none; }
#BottomFrame { background-color: $SURFACE; border: none; border-top: 1px solid $BORDER; }

/* TYPOGRAPHY */
QLabel[class="PageTitle"] { font-size: $FONT_PAGE_TITLE; font-weight: 600; }
QLabel[class="SectionTitle"] { font-size: $FONT_SECTION_TITLE; font-weight: 600; }
QLabel[class="Caption"] { font-size: $FONT_CAPTION; color: $TEXT_SECONDARY; }
QLabel[class="Muted"] { color: $TEXT_MUTED; }
QLabel[class="EmptyState"] { font-size: 15px; color: $TEXT_MUTED; }
QLabel[class="Accent"] { color: $ACCENT; font-weight: 600; }
QLabel[state="danger"] { color: $DANGER; }
QLabel[state="success"] { color: $SUCCESS; }
QLabel[state="muted"] { color: $TEXT_MUTED; }

/* GROUPING: sections are separated by space + title, not boxes */
QGroupBox { background: transparent; border: none; margin-top: $SPACE_LG; padding-top: $SPACE_SM; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 0px; padding: 0px; color: $TEXT_PRIMARY; font-size: $FONT_SECTION_TITLE; font-weight: 600; }
QGroupBox:disabled::title { color: $TEXT_DISABLED; }

/* TABS */
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: transparent; color: $TEXT_SECONDARY; padding: 6px $SPACE_MD; margin: $SPACE_XS 2px; border: none; border-radius: $RADIUS_CONTROL; font-weight: 600; min-height: 20px; }
QTabBar::tab:hover:!selected { background-color: $HOVER_OVERLAY; color: $TEXT_PRIMARY; }
QTabBar::tab:selected { background-color: $SELECTED_SURFACE; color: $TEXT_PRIMARY; }
QTabBar::scroller { width: 28px; }
QTabBar QToolButton { background: transparent; border: none; color: $TEXT_PRIMARY; }
QTabBar QToolButton:hover { background: $HOVER_OVERLAY; }

/* BUTTONS: default = ghost secondary (8px). Variants opt in via [variant] */
QPushButton { background-color: transparent; color: $TEXT_PRIMARY; border: 1px solid transparent; border-radius: $RADIUS_CONTROL; padding: 6px $SPACE_MD; font-weight: 600; }
QPushButton:hover { background-color: $SURFACE_SOFT; border-color: $BORDER; }
QPushButton:pressed { background-color: $SURFACE_ELEVATED; }
QPushButton:disabled { color: $TEXT_DISABLED; background-color: transparent; border-color: transparent; }
QPushButton:focus { border-color: $ACCENT; }
QPushButton#btn_primary, QPushButton[variant="primary"], QPushButton[variant="pill"] { background-color: $PRIMARY; color: #FFFFFF; border: none; }
QPushButton#btn_primary:hover, QPushButton[variant="primary"]:hover, QPushButton[variant="pill"]:hover { background-color: $PRIMARY_HOVER; }
QPushButton#btn_primary:disabled, QPushButton[variant="primary"]:disabled, QPushButton[variant="pill"]:disabled { background-color: $SURFACE_SOFT; color: $TEXT_DISABLED; }
QPushButton[variant="pill"] { border-radius: $RADIUS_PILL; }
QPushButton#btn_secondary, QPushButton[variant="secondary"] { background-color: $SURFACE_ELEVATED; border: 1px solid $BORDER; }
QPushButton#btn_secondary:hover, QPushButton[variant="secondary"]:hover { border-color: $ACCENT; }
QPushButton[variant="success"] { background-color: $SUCCESS; color: $BG_APP; border: none; }
QPushButton[variant="danger"] { color: $DANGER; border: 1px solid $DANGER; }
QPushButton[variant="danger"]:hover { background-color: $DANGER; color: #FFFFFF; }
QPushButton[variant="icon"], QPushButton[variant="window"], QPushButton[variant="window-close"] { padding: 0px; color: $TEXT_SECONDARY; font-size: 16px; }
QPushButton[variant="icon"]:hover, QPushButton[variant="window"]:hover { background-color: $HOVER_OVERLAY; border-color: transparent; color: $TEXT_PRIMARY; }
QPushButton[variant="window-close"] { color: $DANGER; }
QPushButton[variant="window-close"]:hover { background-color: $DANGER; color: #FFFFFF; border-color: transparent; }
QPushButton[variant="handle"] { background-color: $SURFACE_ELEVATED; border: 1px solid $BORDER; border-right: none; border-top-right-radius: 0px; border-bottom-right-radius: 0px; color: $TEXT_SECONDARY; padding: 0px; font-size: 16px; }

/* INPUTS: 32px, 8px, solid */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background-color: $SURFACE_ELEVATED; color: $TEXT_PRIMARY; border: 1px solid $BORDER; border-radius: $RADIUS_CONTROL; padding: 5px $SPACE_SM; min-height: 20px; selection-background-color: $PRIMARY; }
QTextEdit, QPlainTextEdit { background-color: $SURFACE_ELEVATED; color: $TEXT_PRIMARY; border: 1px solid $BORDER; border-radius: $RADIUS_CONTROL; padding: 4px $SPACE_SM; selection-background-color: $PRIMARY; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color: $ACCENT; background-color: $SURFACE_SOFT; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: $TEXT_DISABLED; }
QComboBox QAbstractItemView { background-color: $SURFACE_ELEVATED; border: 1px solid $BORDER; selection-background-color: $PRIMARY; outline: 0px; }

/* CHECK / RADIO / SLIDER */
QCheckBox, QRadioButton { spacing: $SPACE_SM; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; border: 1px solid $BORDER; background-color: $SURFACE_ELEVATED; }
QCheckBox::indicator { border-radius: $RADIUS_INNER; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: $ACCENT; }
QCheckBox::indicator:checked { background-color: $ACCENT; border-color: $ACCENT; image: url(assets/check.svg); }
QRadioButton::indicator:checked { background-color: $ACCENT; border-color: $ACCENT; image: url(assets/radio_checked.svg); }
QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: $SURFACE_SOFT; }
QSlider::sub-page:horizontal { background: $PRIMARY; border-radius: 2px; }
QSlider::handle:horizontal { background: $TEXT_PRIMARY; width: 12px; height: 12px; margin: -4px 0px; border-radius: 6px; }
QSlider::handle:horizontal:hover { background: $ACCENT; }

/* LISTS / TABLES */
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: $SPACE_SM $SPACE_MD; margin-bottom: $SPACE_XS; border-radius: $RADIUS_CONTROL; color: $TEXT_SECONDARY; }
QListWidget::item:hover { background-color: $HOVER_OVERLAY; color: $TEXT_PRIMARY; }
QListWidget::item:selected { background-color: $SELECTED_SURFACE; color: $TEXT_PRIMARY; font-weight: 600; }
QTableWidget, QTableView { background-color: $SURFACE; color: $TEXT_PRIMARY; border: none; gridline-color: $BORDER; selection-background-color: $SELECTED_SURFACE; selection-color: $TEXT_PRIMARY; outline: none; }
QHeaderView::section { background-color: $SURFACE; color: $TEXT_SECONDARY; border: none; border-bottom: 1px solid $BORDER; padding: 6px $SPACE_SM; font-weight: 600; }
QProgressBar { background-color: $SURFACE_SOFT; border: none; border-radius: $RADIUS_INNER; }
QProgressBar::chunk { background: $PRIMARY_GRADIENT; border-radius: $RADIUS_INNER; }

/* SCROLLBARS / SPLITTERS */
QScrollBar:vertical, QScrollBar:horizontal { border: none; background: transparent; margin: 0px; }
QScrollBar:vertical { width: 8px; }
QScrollBar:horizontal { height: 8px; }
QScrollBar::handle { background: $SURFACE_SOFT; border-radius: $RADIUS_INNER; }
QScrollBar::handle:hover { background: $TEXT_DISABLED; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; border: none; }
QSplitter::handle { background-color: transparent; margin: 1px 0px; }
QSplitter::handle:hover { background-color: $ACCENT; }
QSplitter::handle:horizontal { width: 3px; }
QSplitter::handle:vertical { height: 3px; }
""")

# Optional environment: the wallpaper only shows through the navigation (glass) layer.
_WALLPAPER = Template("""
QMainWindow { background-color: #000000; border-image: url(liquid_wallpaper.jpg) 0 0 0 0 stretch stretch; }
QMainWindow > QDockWidget#SidebarDock, QDockWidget#SubtitleGenerationDock { background: transparent; }
""")


class LiquidThemeEngine:
    @staticmethod
    def compile_stylesheet(wallpaper: bool = False) -> str:
        v = _vars()
        return _QSS.substitute(v) + (_WALLPAPER.substitute(v) if wallpaper else "")
