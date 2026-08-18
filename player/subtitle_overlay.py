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
        # [P2-T5] Phân biệt: Text rỗng của đoạn Active (Draft) khác với việc không có đoạn nào Active
        if not text.strip():
            self.current_text = "[...]"
            self.is_placeholder = True
        else:
            self.current_text = text
            self.is_placeholder = False
        self.update()

    def clear_subtitle(self):
        # Trạng thái rỗng hoàn toàn: Kim thời gian đã chạy ra khỏi mọi khung Timing
        self.current_text = ""
        self.is_placeholder = False
        self.update()

    def paintEvent(self, event):
        """ Ghi đè paintEvent để render chữ nổi có viền (Stroke/Outline) """
        if not self.current_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # [P2-T5] Áp dụng Opacity 60% làm mờ tinh tế nếu chỉ là Timing Preview
        if getattr(self, 'is_placeholder', False):
            painter.setOpacity(0.6)
        
        if hasattr(self, 'custom_font'):
            painter.setFont(self.custom_font)
        else:
            painter.setFont(self.font())

        display_text = self.current_text

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

        painter.setPen(QPen(self.text_color))
        painter.drawText(rect, flags, display_text)