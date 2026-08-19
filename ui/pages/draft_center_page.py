import json
import os
import time

import PySide6
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.empty_state import EmptyStateWidget
from ui.theme import Theme
from ui.toast import Toast


class DraftCenterPage(QWidget):
    open_draft_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_dir = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        title = QLabel("📦 Draft Artifacts Manager")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {Theme.TEXT_PRIMARY}; border: none;")
        header.addWidget(title)
        header.addStretch()

        btn_refresh = QPushButton("🔄 Làm mới")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self.scan_drafts)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        # Scroll Area for Draft Cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.container = QWidget()
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.cards_layout.setSpacing(8)
        self.scroll.setWidget(self.container)

        self.empty_state = EmptyStateWidget(
            icon="📦",
            title="Chưa có file Draft nào",
            description="Tạo Timing Draft trong Workspace để bảo lưu tiến trình chỉnh sửa.",
        )
        self.cards_layout.addWidget(self.empty_state)

        layout.addWidget(self.scroll)

    def set_directory(self, d):
        # [FIX MEDIUM #9] Quét thư mục 'subtitles' theo chuẩn Output Architecture của Sprint 5
        target_dir = os.path.join(d, "subtitles") if d else ""
        self.active_dir = target_dir if os.path.exists(target_dir) else d
        self.scan_drafts()

    def scan_drafts(self):
        # Clear layout
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        draft_files = []
        if self.active_dir and os.path.exists(self.active_dir):
            try:
                for f in os.listdir(self.active_dir):
                    if f.endswith(".ai-subtitle-draft"):
                        draft_files.append(os.path.join(self.active_dir, f))
            except Exception:
                pass

        if not draft_files:
            self.empty_state = EmptyStateWidget(
                icon="📦",
                title="Chưa có file Draft nào",
                description="Tạo Timing Draft trong Workspace để bảo lưu tiến trình chỉnh sửa.",
            )
            self.cards_layout.addWidget(self.empty_state)
            return

        for path in draft_files:
            card = self._create_draft_card(path)
            self.cards_layout.addWidget(card)

    def _create_draft_card(self, path):
        card = QFrame()
        card.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 10px;")
        l = QHBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)

        # Parse metadata
        seg_count = 0
        filled_count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                segs = data.get("segments", [])
                seg_count = len(segs)
                filled_count = sum(1 for s in segs if s.get("text", "").strip())
        except Exception:
            pass

        pct = int((filled_count / seg_count) * 100) if seg_count > 0 else 0
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))

        info_box = QVBoxLayout()
        lbl_name = QLabel(f"📄 <b>{os.path.basename(path)}</b>")
        lbl_name.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; border: none;")

        lbl_meta = QLabel(f"Tiến độ: <span style='color:{Theme.CYAN}; font-weight:bold;'>{filled_count}/{seg_count} câu ({pct}%)</span> &nbsp;|&nbsp; Cập nhật: {mtime}")
        lbl_meta.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; border: none;")

        info_box.addWidget(lbl_name)
        info_box.addWidget(lbl_meta)
        l.addLayout(info_box, stretch=1)

        btn_open = QPushButton("Mở Editor")
        btn_open.setObjectName("btn_secondary")
        btn_open.clicked.connect(lambda p=path: self.open_draft_requested.emit(p))
        l.addWidget(btn_open)

        btn_del = QPushButton("✕")
        btn_del.setToolTip("Xóa bản nháp này")
        btn_del.setStyleSheet(f"background: transparent; color: {Theme.DANGER}; font-weight: bold; border: none; font-size: 14px;")
        btn_del.clicked.connect(lambda p=path, c=card: self._delete_draft(p, c))
        l.addWidget(btn_del)

        return card

    def _delete_draft(self, path, card_widget):
        # [FIX MEDIUM #10] Thêm hộp thoại xác nhận (Confirmation) và không nuốt lỗi
        reply = QMessageBox.question(
            self, "Xác nhận xóa", 
            f"Bạn có chắc chắn muốn xóa bản nháp:\n{os.path.basename(path)}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if os.path.exists(path):
                    os.remove(path)
                card_widget.deleteLater()
                Toast.show_success(self.window(), "Đã xóa bản nháp thành công.")
            except Exception as e:
                Toast.show_error(self.window(), f"Lỗi xóa file: {str(e)}")