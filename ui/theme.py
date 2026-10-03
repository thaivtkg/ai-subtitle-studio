class Theme:
    # ---------------------------------------------------------
    # COLOR PALETTE (Dark Mode chuẩn mực)
    # ---------------------------------------------------------
    BG_APP = "#0D111A"             # Nền tổng thể
    SURFACE = "#151A27"            # Nền của Card/Box
    SURFACE_ELEVATED = "#1E2536"   # Nền sáng khi hover/chọn
    SURFACE_SOFT = "#262E40"       # Nền nhẹ cho phân cách
    
    PRIMARY_PURPLE = "#6366F1"     # Màu chủ đạo chính
    PRIMARY_PINK = "#EC4899"
    PRIMARY_GRADIENT = "qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #6366F1, stop: 1 #EC4899)"
    PRIMARY_GREEN = "#10B981"

    CYAN = "#38BDF8"               # Màu nhấn/Focus
    SUCCESS = "#10B981"            # Xanh lá (Thành công/Lưu)
    DANGER = "#EF4444"             # Đỏ (Lỗi/Xóa)
    WARNING = "#F59E0B"            # Vàng/Cam (Cảnh báo)
    INFO = "#3B82F6"               # Xanh dương (Thông tin)
    
    TEXT_PRIMARY = "#F8FAFC"       # Chữ chính (Trắng)
    TEXT_SECONDARY = "#94A3B8"     # Chữ phụ (Xám nhạt)
    TEXT_MUTED = "#64748B"         # Chữ mờ
    TEXT_DISABLED = "#475569"      # Chữ vô hiệu hóa
    BORDER = "#1E293B"             # Viền phân cách

    @classmethod
    def get_global_stylesheet(cls):
        return f"""
        /* 1. RESET CHUNG CHO MỌI WIDGET */
        QWidget {{
            font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
            font-size: 13px;
            color: {cls.TEXT_PRIMARY};
            background-color: transparent; /* Mặc định trong suốt để kế thừa từ MainWindow */
        }}

        /* Áp nền cho các container lớn để tránh bị trắng */
        QMainWindow, QDialog, QDockWidget, QScrollArea, QStackedWidget {{
            background-color: {cls.BG_APP};
        }}

        /* 2. TAB WIDGETS (Sửa lỗi nền trắng của Tab pane) */
        QTabWidget::pane {{
            border-top: 1px solid {cls.BORDER};
            background-color: {cls.BG_APP};
        }}
        QTabBar::tab {{
            background-color: {cls.BG_APP};
            color: {cls.TEXT_SECONDARY};
            padding: 8px 16px;
            border: none;
            font-weight: bold;
        }}
        QTabBar::tab:selected {{
            background-color: {cls.SURFACE};
            color: {cls.PRIMARY_PURPLE};
            border-bottom: 2px solid {cls.PRIMARY_PURPLE};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {cls.SURFACE_ELEVATED};
        }}

        /* 3. GROUPBOX (Bọc ngoài cấu hình) */
        QGroupBox {{
            background-color: {cls.SURFACE};
            border: 1px solid {cls.BORDER};
            border-radius: 6px;
            margin-top: 20px;
            padding-top: 15px;
            font-weight: bold;
            color: {cls.CYAN};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
            color: {cls.CYAN};
        }}

        /* 4. GHOST BUTTONS */
        QPushButton {{
            background-color: transparent;
            color: {cls.TEXT_PRIMARY};
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {cls.SURFACE_SOFT};
            border: 1px solid {cls.BORDER};
        }}
        QPushButton:pressed {{
            background-color: {cls.SURFACE_ELEVATED};
        }}
        QPushButton#btn_primary {{
            background-color: {cls.PRIMARY_PURPLE};
            color: #FFFFFF;
            border: none;
        }}
        QPushButton#btn_primary:hover {{
            background-color: #4F46E5;
        }}
        QPushButton#btn_secondary {{
            background-color: {cls.SURFACE_ELEVATED};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER};
        }}
        QPushButton#btn_secondary:hover {{
            border-color: {cls.CYAN};
        }}

        /* 5. TEXT INPUTS & DROPDOWNS */
        QLineEdit, QTextEdit, QComboBox, QSpinBox {{
            background-color: {cls.SURFACE_ELEVATED};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {cls.PRIMARY_PURPLE};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {cls.CYAN};
            background-color: {cls.SURFACE_SOFT};
        }}

        /* 6. CHECKBOX & RADIO */
        QCheckBox, QRadioButton {{
            color: {cls.TEXT_PRIMARY};
            spacing: 8px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {cls.BORDER};
            border-radius: 3px;
            background-color: {cls.SURFACE_ELEVATED};
        }}
        QCheckBox::indicator:checked {{
            background-color: {cls.CYAN};
            border: 1px solid {cls.CYAN};
        }}

        /* 7. SCROLLBARS TÀNG HÌNH */
        QScrollBar:vertical, QScrollBar:horizontal {{
            border: none;
            background: transparent;
            margin: 0px;
        }}
        QScrollBar:vertical {{ width: 8px; }}
        QScrollBar:horizontal {{ height: 8px; }}
        QScrollBar::handle {{
            background: #333333;
            border-radius: 4px;
        }}
        QScrollBar::handle:hover {{ background: #555555; }}
        QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
            background: none; border: none;
        }}

        /* 8. QSPLITTER TÀNG HÌNH */
        QSplitter::handle {{
            background-color: transparent;
            margin: 1px 0px;
        }}
        QSplitter::handle:hover {{
            background-color: {cls.CYAN};
        }}
        QSplitter::handle:horizontal {{ width: 3px; }}
        QSplitter::handle:vertical {{ height: 3px; }}
        """
