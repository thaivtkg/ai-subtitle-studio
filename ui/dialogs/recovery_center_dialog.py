import os
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme


class RecoveryCenterDialog(QDialog):
    """Small view over MainWindow recovery callbacks."""

    def __init__(
        self,
        *,
        entries_provider,
        live_session_id_provider,
        restore_callback,
        delete_callback,
        confirm_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self._entries_provider = entries_provider
        self._live_session_id_provider = live_session_id_provider
        self._restore_callback = restore_callback
        self._delete_callback = delete_callback
        self._confirm_callback = confirm_callback or self._confirm
        self._entry_ids = []

        self.setWindowTitle("Recovery Center")
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Recovery Center")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {Theme.TEXT_PRIMARY};"
        )
        layout.addWidget(title)
        layout.addWidget(
            QLabel("Các bản khôi phục an toàn được tìm thấy trên máy.")
        )

        self._status_label = QLabel()
        self._status_label.setStyleSheet(f"color: {Theme.WARNING};")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows = QWidget()
        self._rows_layout = QVBoxLayout(self._rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        self._scroll.setWidget(self._rows)
        layout.addWidget(self._scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        footer.addWidget(refresh)
        footer.addWidget(close)
        layout.addLayout(footer)

        self.refresh()

    def refresh(self):
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._entry_ids = []
        self._status_label.clear()

        entries = list(self._entries_provider() or [])
        if not entries:
            empty = QLabel("Không có dữ liệu khôi phục.")
            empty.setObjectName("recovery_empty_state")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self._rows_layout.addWidget(empty)
            return

        for entry in entries:
            self._entry_ids.append(entry.session_id)
            self._rows_layout.addWidget(self._build_entry_row(entry))
        self._rows_layout.addStretch()

    def _build_entry_row(self, entry):
        row = QFrame()
        row.setObjectName("recovery_entry_row")
        row.setStyleSheet(
            f"QFrame#recovery_entry_row {{ background: {Theme.SURFACE_ELEVATED}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; }}"
        )
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        name = QLabel(self._display_name(entry))
        name.setObjectName("recovery_project_name")
        name.setStyleSheet("font-weight: bold;")
        layout.addWidget(name)

        details = QLabel(
            f"{self._format_timestamp(entry.effective_snapshot_timestamp)} · "
            f"Revision {entry.snapshot_revision}"
        )
        layout.addWidget(details)

        source = QLabel(self._source_text(entry.source_status))
        source.setStyleSheet(f"color: {self._source_color(entry.source_status)};")
        layout.addWidget(source)

        actions = QHBoxLayout()
        actions.addStretch()
        restore_text = (
            "Restore" if entry.source_status == "AVAILABLE" else "Restore Unlinked"
        )
        restore = QPushButton(restore_text)
        restore.setObjectName("btn_primary")
        restore.clicked.connect(lambda _checked=False, item=entry: self._restore(item))
        delete = QPushButton("Delete")
        delete.setObjectName("btn_danger")
        delete.clicked.connect(lambda _checked=False, item=entry: self._delete(item))
        actions.addWidget(restore)
        actions.addWidget(delete)
        layout.addLayout(actions)
        return row

    def _restore(self, entry):
        linked = entry.source_status == "AVAILABLE"
        title = "Khôi phục project này?"
        if linked:
            message = (
                "Dữ liệu recovery sẽ thay thế trạng thái đang mở "
                "sau khi project hiện tại được lưu an toàn."
            )
        elif entry.source_status == "SOURCE_MISSING":
            message = (
                "File nguồn không còn tồn tại.\n"
                "Có thể khôi phục nội dung phụ đề ở chế độ unlinked."
            )
        else:
            message = (
                "File nguồn đã thay đổi so với thời điểm recovery.\n"
                "Có thể khôi phục nội dung phụ đề ở chế độ unlinked."
            )
        if not self._confirm_callback(title, message):
            return
        active_session_id = self._live_session_id_provider()
        if self._restore_callback(
            entry.session_id,
            linked=linked,
            active_session_id=active_session_id,
        ):
            self.accept()
        else:
            self._action_failed("Không thể khôi phục dữ liệu recovery.")

    def _delete(self, entry):
        if not self._confirm_callback(
            "Xóa dữ liệu khôi phục?", "Thao tác này không thể hoàn tác."
        ):
            return
        active_session_id = self._live_session_id_provider()
        if self._delete_callback(
            entry.session_id, active_session_id=active_session_id
        ):
            self.refresh()
        else:
            self._action_failed("Không thể xóa dữ liệu recovery.")

    def _action_failed(self, message):
        self._status_label.setText(message)
        self.refresh()
        self._status_label.setText(message)

    def displayed_text(self):
        return "\n".join(label.text() for label in self.findChildren(QLabel))

    def entry_session_ids(self):
        return list(self._entry_ids)

    @staticmethod
    def _display_name(entry):
        root = os.path.basename(os.path.normpath(entry.project_root or ""))
        if root.lower().endswith(".ai-subtitle"):
            root = root[: -len(".ai-subtitle")]
        return root or entry.project_id or "Unknown Project"

    @staticmethod
    def _format_timestamp(value):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            return "Unknown time"
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _source_text(status):
        return {
            "AVAILABLE": "Source available",
            "SOURCE_MISSING": "Source missing",
            "SOURCE_MISMATCH": "Source changed",
        }.get(status, "Source unavailable")

    @staticmethod
    def _source_color(status):
        return {
            "AVAILABLE": Theme.SUCCESS,
            "SOURCE_MISSING": Theme.WARNING,
            "SOURCE_MISMATCH": Theme.WARNING,
        }.get(status, Theme.TEXT_MUTED)

    def _confirm(self, title, message):
        box = QMessageBox(QMessageBox.Icon.Question, title, message, parent=self)
        action = box.addButton(
            "Delete" if title.startswith("Xóa") else "Restore",
            QMessageBox.ButtonRole.AcceptRole,
        )
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is action
