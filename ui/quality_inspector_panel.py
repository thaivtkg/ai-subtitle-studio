import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from core.subtitle_quality import QualitySeverity, SubtitleQualityAnalyzer
from ui.theme import Theme


class QualityInspectorPanel(QWidget):
    jump_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments = []
        self._issues = []
        self.analysis_state = "NO_SOURCE"
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("QUALITY INSPECTOR"))
        self.summary_label = QLabel("0 Errors · 0 Warnings · 0 Info")
        layout.addWidget(self.summary_label)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Errors", "Warnings", "Info"])
        self.filter_combo.currentIndexChanged.connect(self._render_issues)
        layout.addWidget(self.filter_combo)
        self.issue_list = QListWidget()
        self.issue_list.currentItemChanged.connect(
            lambda _current, _previous: self._update_navigation_state()
        )
        self.issue_list.setStyleSheet(
            f"""
            QListWidget, QListWidget::viewport {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
            }}
            QListWidget::item {{
                padding: 6px;
            }}
            QListWidget::item:hover, QListWidget::item:selected {{
                background-color: {Theme.SURFACE_SOFT};
                color: {Theme.TEXT_PRIMARY};
            }}
            """
        )
        layout.addWidget(self.issue_list)
        self.empty_state_label = QLabel()
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; padding: 12px;")
        layout.addWidget(self.empty_state_label)
        self.jump_button = QPushButton("Jump to subtitle")
        self.jump_button.clicked.connect(self._jump_to_selected)
        layout.addWidget(self.jump_button)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)

    def set_segments(self, segments):
        self._replace_snapshot(segments, "STALE")

    def mark_segments_stale(self, segments):
        self._replace_snapshot(segments, "STALE")

    def _replace_snapshot(self, segments, state):
        self._segments = copy.deepcopy(list(segments or []))
        self.analysis_state = "NO_SOURCE" if not self._segments else state
        self._issues = []
        self._update_summary()
        self._render_issues()

    def refresh(self):
        if not self._segments:
            self._replace_snapshot([], "NO_SOURCE")
            return
        self._issues = SubtitleQualityAnalyzer.analyze(self._segments)
        self.analysis_state = "CURRENT"
        self._update_summary()
        self._render_issues()

    def _update_summary(self):
        counts = {
            severity: sum(issue.severity is severity for issue in self._issues)
            for severity in QualitySeverity
        }
        self.summary_label.setText(
            f"{counts[QualitySeverity.ERROR]} Errors · "
            f"{counts[QualitySeverity.WARNING]} Warnings · "
            f"{counts[QualitySeverity.INFO]} Info"
        )

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
            item = self.issue_list.item(self.issue_list.count() - 1)
            item.setData(Qt.UserRole, issue.subtitle_index)
            severity_color = {
                QualitySeverity.ERROR: Theme.DANGER,
                QualitySeverity.WARNING: Theme.WARNING,
                QualitySeverity.INFO: Theme.CYAN,
            }[issue.severity]
            item.setForeground(QColor(severity_color))
        has_issues = self.issue_list.count() > 0
        self.empty_state_label.setVisible(not has_issues)
        if has_issues:
            empty_text = ""
        elif self.analysis_state == "NO_SOURCE":
            empty_text = "No active subtitles to inspect"
        elif self.analysis_state == "STALE":
            empty_text = "Subtitles changed. Refresh to reanalyze."
        else:
            empty_text = "No quality issues found"
        self.empty_state_label.setText(empty_text)
        self._update_navigation_state()

    def _update_navigation_state(self):
        item = self.issue_list.currentItem()
        has_valid_issue = (
            self.analysis_state == "CURRENT"
            and item is not None
            and item.data(Qt.UserRole) is not None
        )
        self.jump_button.setEnabled(has_valid_issue)

    def _jump_to_selected(self):
        item = self.issue_list.currentItem()
        if item is not None:
            self.jump_requested.emit(int(item.data(Qt.UserRole)))
