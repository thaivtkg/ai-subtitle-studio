from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt


class SubtitleOverlay(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Quan trọng: Làm trong suốt và click xuyên qua Video
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # --- BẮT BUỘC PHẢI CÓ DÒNG NÀY: Ép Overlay giãn to bằng 100% Video ---
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # --------------------------------------------------------------------

        # Mặc định Style (đúng chuẩn spec của bạn)
        self.font_family = "Arial"
        self.font_size = 20
        self.text_color = QColor("white")
        self.outline_color = QColor("black")
        self.outline_width = 2

        self.current_text = ""
        self.update_style()

    def update_style(self, family=None, size=None, color=None, out_color=None, out_width=None):
        if family: self.font_family = family
        if size: self.font_size = size
        if color: self.text_color = QColor(color)
        if out_color: self.outline_color = QColor(out_color)
        if out_width is not None: self.outline_width = out_width

        font = QFont(self.font_family, self.font_size, QFont.Bold)
        self.setFont(font)
        self.update()  # Bắt buộc vẽ lại khi đổi style

    def set_subtitle(self, text):
        # Giữ nguyên ký tự \n để hỗ trợ multi-line
        self.current_text = text
        print(f"👉 [DEBUG - Nhan_Text] Nhận: {repr(text)} | Kích thước Overlay: {self.width()}x{self.height()}")
        self.update()

    def clear_subtitle(self):
        self.current_text = ""
        self.update()

    def paintEvent(self, event):
        """ Ghi đè paintEvent để render chữ nổi có viền (Stroke/Outline) """

        # --- DÒNG DEBUG 2: Kiểm tra xem hàm Vẽ có được kích hoạt không ---
        if self.current_text:
            print(f"🎨 [DEBUG - Dang_Ve] Đang vẽ chữ: {repr(self.current_text)} | Tọa độ Rect: {self.rect()}")
        # -----------------------------------------------------------------

        if not self.current_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.font())

        rect = self.rect()
        # Tính toán Margin Bottom: Chiếm khoảng 8% chiều cao của video
        bottom_margin = int(rect.height() * 0.08)
        rect.setBottom(rect.bottom() - bottom_margin)

        # Căn giữa theo chiều ngang và bám đáy
        flags = int(Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap)

        # 1. Vẽ Outline (bằng cách vẽ text 8 lần ra xung quanh)
        if self.outline_width > 0:
            pen = QPen(self.outline_color)
            painter.setPen(pen)
            ow = self.outline_width
            offsets = [
                (-ow, -ow), (0, -ow), (ow, -ow),
                (-ow, 0), (ow, 0),
                (-ow, ow), (0, ow), (ow, ow)
            ]
            for dx, dy in offsets:
                painter.drawText(rect.translated(dx, dy), flags, self.current_text)

        # 2. Vẽ Text chính (Trắng) đè lên trên cùng
        painter.setPen(QPen(self.text_color))
        painter.drawText(rect, flags, self.current_text)