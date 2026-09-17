import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from core.subtitle_quality import QualitySeverity, SubtitleQualityAnalyzer


class QualityInspectorPanel(QWidget):
    jump_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments = []
        self._issues = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("QUALITY INSPECTOR"))
        self.summary_label = QLabel("0 Errors · 0 Warnings · 0 Info")
        layout.addWidget(self.summary_label)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Errors", "Warnings", "Info"])
        self.filter_combo.currentIndexChanged.connect(self._render_issues)
        layout.addWidget(self.filter_combo)
        self.issue_list = QListWidget()
        layout.addWidget(self.issue_list)
        self.jump_button = QPushButton("Jump to subtitle")
        self.jump_button.clicked.connect(self._jump_to_selected)
        layout.addWidget(self.jump_button)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)

    def set_segments(self, segments):
        self._segments = copy.deepcopy(list(segments or []))

    def refresh(self):
        self._issues = SubtitleQualityAnalyzer.analyze(self._segments)
        counts = {
            severity: sum(issue.severity is severity for issue in self._issues)
            for severity in QualitySeverity
        }
        self.summary_label.setText(
            f"{counts[QualitySeverity.ERROR]} Errors · "
            f"{counts[QualitySeverity.WARNING]} Warnings · "
            f"{counts[QualitySeverity.INFO]} Info"
        )
        self._render_issues()

    def _render_issues(self):
        severity = {
            "Errors": QualitySeverity.ERROR,
            "Warnings": QualitySeverity.WARNING,
            "Info": QualitySeverity.INFO,
        }.get(self.filter_combo.currentText())
        self.issue_list.clear()
        for issue in self._issues:
            if severity is not None and issue.severity is not severity:
                continue
            self.issue_list.addItem(
                f"{issue.severity.name.title()} · #{issue.subtitle_index + 1} {issue.rule_id}\n{issue.message}"
            )
            self.issue_list.item(self.issue_list.count() - 1).setData(
                Qt.UserRole, issue.subtitle_index
            )

    def _jump_to_selected(self):
        item = self.issue_list.currentItem()
        if item is not None:
            self.jump_requested.emit(int(item.data(Qt.UserRole)))
