class Theme:
    # 1. Colors - Background & Surfaces
    BG_APP = "#0B1020"              # Nền sâu nhất (Deep Navy)
    SURFACE = "#111827"             # Bề mặt Panel (Sidebar, Stack)
    SURFACE_ELEVATED = "#172033"    # Bề mặt nổi (Card)
    SURFACE_SOFT = "#1B263B"        # Nền input, hover nhẹ
    BORDER = "#273247"              # Viền phân cách chung

    # 2. Colors - Accents & States
    PRIMARY_GRADIENT = "qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #8B5CF6, stop: 1 #EC4899)"
    PRIMARY_PURPLE = "#8B5CF6"
    PRIMARY_PINK = "#EC4899"
    CYAN = "#38BDF8"
    SUCCESS = "#34D399"
    WARNING = "#FBBF24"
    DANGER = "#F43F5E"

    # 3. Colors - Typography
    TEXT_PRIMARY = "#F8FAFC"        # Chữ chính sáng rõ
    TEXT_SECONDARY = "#CBD5E1"      # Chữ phụ (Sub-title)
    TEXT_MUTED = "#94A3B8"          # Chữ ghi chú, label
    TEXT_DISABLED = "#64748B"       # Trạng thái vô hiệu hóa

    # 4. Global Stylesheet (Áp dụng cho toàn bộ App)
    @classmethod
    def get_global_stylesheet(cls):
        return f"""
        /* 1. NỀN & TYPOGRAPHY CƠ BẢN */
        QWidget {{
            background-color: {cls.BG_APP};
            color: {cls.TEXT_PRIMARY};
            font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
            font-size: 13px;
        }}

        /* 2. GHOST BUTTONS (Không viền, chỉ hiện nền khi hover) */
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
        
        /* Nút Primary (Được phép có màu nền để call-to-action) */
        QPushButton#btn_primary {{
            background-color: {cls.PRIMARY_PURPLE};
            color: #FFFFFF;
            border: none;
        }}
        QPushButton#btn_primary:hover {{
            background-color: #7b4dff; /* Sáng hơn chút */
        }}

        /* 3. TÀNG HÌNH QSPLITTER (Biến mất, chỉ hiện Cyan khi hover) */
        QSplitter::handle {{
            background-color: transparent;
            margin: 1px 0px;
        }}
        QSplitter::handle:hover {{
            background-color: {cls.CYAN};
        }}
        QSplitter::handle:horizontal {{
            width: 3px;
        }}
        QSplitter::handle:vertical {{
            height: 3px;
        }}

        /* 4. SCROLLBAR SIÊU MỎNG (Phong cách macOS/Web) */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #333333;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #555555;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        /* Scrollbar Ngang */
        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 8px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: #333333;
            min-width: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #555555;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            border: none;
            background: none;
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}

        /* 5. TEXT INPUTS & DROPDOWNS (Đơn giản hóa viền) */
        QLineEdit, QTextEdit, QComboBox, QSpinBox {{
            background-color: {cls.SURFACE};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {cls.PRIMARY_PURPLE};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {cls.CYAN};
            background-color: {cls.SURFACE_ELEVATED};
        }}

        QToolTip {
            background-color: {cls.SURFACE_ELEVATED};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER};
            padding: 4px;
            border-radius: 4px;
        }
        """
