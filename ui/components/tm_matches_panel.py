from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, 
    QAbstractItemView, QHBoxLayout, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from ui.theme import Theme
from core.database.tm_manager import TMMatch, TMMatchType

class TMMatchesPanel(QWidget):
    # Signal emitted when user wants to apply a TM match
    match_applied = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Header
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("TM Matches (0)")
        self.lbl_title.setStyleSheet(f"font-weight: bold; color: {Theme.TEXT_PRIMARY};")
        header_layout.addWidget(self.lbl_title)
        
        self.btn_apply = QPushButton("Apply (Enter)")
        self.btn_apply.setObjectName("btn_primary")
        self.btn_apply.setToolTip("Áp dụng bản dịch được chọn đè lên phụ đề hiện tại")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        header_layout.addWidget(self.btn_apply)
        
        layout.addLayout(header_layout)
        
        # List of matches
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {Theme.BG_APP};
            }}
            QListWidget::item:selected {{
                background-color: {Theme.SURFACE_SOFT};
                color: {Theme.CYAN};
            }}
        """)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

    def update_matches(self, matches: list[TMMatch]):
        self.list_widget.clear()
        self.lbl_title.setText(f"TM Matches ({len(matches)})")
        
        for m in matches:
            item = QListWidgetItem()
            
            # Formatting the match text
            score_pct = int(m.score * 100) if m.match_type == TMMatchType.FUZZY else 100
            if m.match_type == TMMatchType.CONTEXT_101:
                score_str = "101%"
                color = Theme.SUCCESS
            elif score_pct == 100:
                score_str = "100%"
                color = Theme.PRIMARY_GREEN
            else:
                score_str = f"{score_pct}%"
                color = Theme.WARNING
                
            display_text = f"[{score_str}] {m.target_text}\n(Gốc: {m.source_text})"
            item.setText(display_text)
            
            # Store the actual target text for applying
            item.setData(Qt.UserRole, m.target_text)
            self.list_widget.addItem(item)
            
        if matches:
            self.list_widget.setCurrentRow(0)
            self.btn_apply.setEnabled(True)
        else:
            self.btn_apply.setEnabled(False)

    def _on_selection_changed(self):
        self.btn_apply.setEnabled(bool(self.list_widget.selectedItems()))

    def _on_apply_clicked(self):
        items = self.list_widget.selectedItems()
        if items:
            self.match_applied.emit(items[0].data(Qt.UserRole))
            
    def _on_item_double_clicked(self, item):
        self.match_applied.emit(item.data(Qt.UserRole))
