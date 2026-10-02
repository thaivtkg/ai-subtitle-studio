from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt
from ui.theme import Theme
from PySide6.QtWidgets import QCheckBox, QFrame
from core.database.glossary_manager import GlossaryManager
from core.batch.batch_models import BatchJob, BatchSession
import uuid
import os


class BatchSetupDialog(QDialog):
    """Modal dialog for configuring a batch processing session."""

    def __init__(self, file_paths: list, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.result_session = None
        self.setWindowTitle("Batch Processing Setup")
        self.setMinimumSize(520, 400)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG_APP}; color: {Theme.TEXT_PRIMARY}; }}
            QLabel {{ color: {Theme.TEXT_SECONDARY}; font-size: 13px; }}
            QComboBox {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 6px; min-width: 160px; }}
            QListWidget {{ background-color: {Theme.SURFACE}; color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER}; border-radius: 4px; }}
            QPushButton {{ padding: 8px 24px; border-radius: 6px; font-weight: 600; font-size: 13px; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel(f"Batch Processing — {len(self.file_paths)} files")
        header.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(header)

        # File list
        self.file_list = QListWidget()
        for fp in self.file_paths:
            item = QListWidgetItem(os.path.basename(fp))
            item.setToolTip(fp)
            self.file_list.addItem(item)
        layout.addWidget(self.file_list)

        # Config row
        config_layout = QHBoxLayout()
        config_layout.setSpacing(12)

        config_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.model_combo.setCurrentText("large-v3")
        config_layout.addWidget(self.model_combo)

        config_layout.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["auto", "en", "vi", "ja", "ko", "zh", "fr", "de", "es"])
        config_layout.addWidget(self.lang_combo)

        config_layout.addWidget(QLabel("Output:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["srt", "ass", "vtt"])
        config_layout.addWidget(self.format_combo)

        config_layout.addStretch()
        layout.addLayout(config_layout)

        # AI Translation Section
        translation_frame = QFrame()
        translation_frame.setStyleSheet(f"""
            QFrame {{ background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; }}
            QCheckBox {{ color: {Theme.TEXT_PRIMARY}; font-weight: bold; spacing: 8px; }}
        """)
        trans_layout = QVBoxLayout(translation_frame)
        trans_layout.setContentsMargins(16, 16, 16, 16)
        
        self.chk_enable_translation = QCheckBox("Bật Dịch thuật AI (Agentic Translation)")
        trans_layout.addWidget(self.chk_enable_translation)
        
        trans_opts_layout = QHBoxLayout()
        trans_opts_layout.addWidget(QLabel("Target Lang:"))
        self.combo_target_lang = QComboBox()
        self.combo_target_lang.addItems(["Vietnamese", "English", "Japanese", "Korean", "Chinese"])
        trans_opts_layout.addWidget(self.combo_target_lang)
        
        trans_opts_layout.addWidget(QLabel("Domain:"))
        self.combo_domain = QComboBox()
        try:
            gm = GlossaryManager()
            domains = gm.get_domains()
            if not domains:
                domains = ["general"]
            if "general" not in domains:
                domains.insert(0, "general")
            self.combo_domain.addItems(domains)
        except Exception:
            self.combo_domain.addItems(["general", "IT", "Anime", "Movie", "Gaming"])
        trans_opts_layout.addWidget(self.combo_domain)
        trans_opts_layout.addStretch()
        
        trans_layout.addLayout(trans_opts_layout)
        layout.addWidget(translation_frame)
        
        def _toggle_trans(state):
            is_checked = (state == Qt.Checked.value) if hasattr(Qt.Checked, 'value') else (state == 2)
            self.combo_target_lang.setEnabled(is_checked)
            self.combo_domain.setEnabled(is_checked)
            
        self.chk_enable_translation.stateChanged.connect(_toggle_trans)
        _toggle_trans(0)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_SECONDARY};")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        start_btn = QPushButton("Start Batch")
        start_btn.setStyleSheet(f"background-color: {Theme.PRIMARY_PURPLE}; color: white;")
        start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(start_btn)

        layout.addLayout(btn_layout)

    def _on_start(self):
        jobs = [
            BatchJob(id=str(uuid.uuid4())[:8], input_file=fp)
            for fp in self.file_paths
        ]
        self.result_session = BatchSession(
            session_id=str(uuid.uuid4())[:8],
            model_size=self.model_combo.currentText(),
            target_lang=self.lang_combo.currentText(),
            output_format=self.format_combo.currentText(),
            jobs=jobs,
            translation_config={
                "enabled": self.chk_enable_translation.isChecked(),
                "target_lang": self.combo_target_lang.currentText(),
                "domain": self.combo_domain.currentText()
            }
        )
        self.accept()
