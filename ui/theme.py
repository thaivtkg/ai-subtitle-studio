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
            QMainWindow {{
                background-color: {cls.BG_APP};
            }}
            QWidget {{
                color: {cls.TEXT_PRIMARY};
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                font-size: 13px;
            }}
            /* Định dạng Scrollbar hiện đại */
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.SURFACE_SOFT};
                min-height: 20px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {cls.BORDER};
            }}
            /* Định dạng Input chung */
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {cls.BG_APP};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: {cls.TEXT_PRIMARY};
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 1px solid {cls.PRIMARY_PURPLE};
            }}

            /* =========================================
               [FIX] ĐỊNH DẠNG LIVE LOG & SCROLL AREA (AI SETTINGS)
               ========================================= */
            QTextEdit {{
                background-color: {cls.BG_APP};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                color: {cls.TEXT_SECONDARY};
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 8px;
            }}
            QScrollArea, QScrollArea > QWidget > QWidget {{
                background-color: transparent;
                border: none;
            }}
            
            /* =========================================
               ĐỊNH DẠNG NÚT BẤM (BUTTON SYSTEM)
               ========================================= */
            /* Nút Primary (Gradient) */
            QPushButton#btn_primary {{
                background-color: {cls.PRIMARY_GRADIENT};
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 6px;
                border: none;
                padding: 8px 16px;
            }}
            QPushButton#btn_primary:hover {{
                background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #A78BFA, stop: 1 #F472B6);
            }}
            QPushButton#btn_primary:disabled {{
                background-color: {cls.BORDER};
                color: {cls.TEXT_DISABLED};
            }}

            /* Nút Danger (Hủy, Xóa) */
            QPushButton#btn_danger {{
                background-color: {cls.DANGER};
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 6px;
                border: none;
                padding: 8px 16px;
            }}
            QPushButton#btn_danger:hover {{
                background-color: #FB7185;
            }}
            QPushButton#btn_danger:disabled {{
                background-color: {cls.BORDER};
                color: {cls.TEXT_DISABLED};
            }}

            /* Nút Secondary (Mở thư mục, Duyệt file, Lưu) */
            QPushButton#btn_secondary {{
                background-color: {cls.SURFACE_ELEVATED};
                color: {cls.TEXT_PRIMARY};
                font-weight: bold;
                border-radius: 6px;
                border: 1px solid {cls.BORDER};
                padding: 8px 16px;
            }}
            QPushButton#btn_secondary:hover {{
                background-color: {cls.SURFACE_SOFT};
                border: 1px solid {cls.CYAN};
                color: {cls.CYAN};
            }}
            QPushButton#btn_secondary:disabled {{
                background-color: {cls.SURFACE};
                color: {cls.TEXT_DISABLED};
                border: 1px solid {cls.BORDER};
            }}
        """