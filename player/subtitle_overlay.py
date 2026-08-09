from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy


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
        self.position_mode = "Bottom"

        self.current_text = ""
        self.update_style()

    def update_style(self, family=None, size=None, color=None, out_color=None, out_width=None, position=None):
        if family: self.font_family = family
        if size: self.font_size = size
        if color: self.text_color = QColor(color)
        if out_color: self.outline_color = QColor(out_color)
        if out_width is not None: self.outline_width = out_width
        if position: self.position_mode = position

        # [Tối ưu] Sử dụng PixelSize tuyệt đối và lưu thành biến riêng (bỏ qua sự can thiệp của QSS)
        self.custom_font = QFont(self.font_family)
        self.custom_font.setPixelSize(self.font_size)
        self.custom_font.setBold(True)
        self.update()

    def set_subtitle(self, text):
        # Giữ nguyên ký tự \n để hỗ trợ multi-line
        self.current_text = text
        self.update()

    def clear_subtitle(self):
        self.current_text = ""
        self.update()

    def paintEvent(self, event):
        """ Ghi đè paintEvent để render chữ nổi có viền (Stroke/Outline) """
        if not self.current_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # [Tối ưu] Ép QPainter vẽ bằng Font đã được đo đạc bằng Pixel
        if hasattr(self, 'custom_font'):
            painter.setFont(self.custom_font)
        else:
            painter.setFont(self.font())

        # Xóa dấu ngắt dòng cứng để WordWrap tự tính toán
        display_text = self.current_text.replace('\n', ' ')

        rect = self.rect()
        h_margin = int(rect.width() * 0.05)
        rect.setLeft(rect.left() + h_margin)
        rect.setRight(rect.right() - h_margin)

        flags = int(Qt.AlignHCenter | Qt.TextWordWrap)
        
        if self.position_mode == "Top":
            flags |= Qt.AlignTop
            margin = int(self.height() * 0.05)
            rect.setTop(rect.top() + margin)
        elif self.position_mode == "Center":
            flags |= Qt.AlignVCenter
        else: 
            flags |= Qt.AlignBottom
            margin = int(self.height() * 0.08) 
            rect.setBottom(rect.bottom() - margin)

        # 1. Vẽ Outline
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
                painter.drawText(rect.translated(dx, dy), flags, display_text)

        # 2. Vẽ Text chính
        painter.setPen(QPen(self.text_color))
        painter.drawText(rect, flags, display_text)