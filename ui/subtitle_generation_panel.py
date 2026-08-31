import uuid

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.subtitle_generation.subtitle_generation_request import (
    SubtitleGenerationRequest,
)
from ui.theme import Theme


class SubtitleGenerationPanel(QWidget):
    """Qt view for robust subtitle generation; project data comes from the core."""

    # Timing Draft dùng pipeline VAD riêng, không khởi tạo Whisper ASR.
    timing_start_requested = Signal(int, dict)
    timing_cancel_requested = Signal()

    def __init__(self, generation_service, parent=None):
        super().__init__(parent)
        self.generation_service = generation_service
        self.video_duration_ms = 0
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # The global theme styles normal inputs with a bright foreground but
        # has no disabled-state rules. Keep the mode lock visible even when
        # the panel is hosted inside a globally styled MainWindow.
        self.setStyleSheet(
            f"""
            QGroupBox:disabled {{
                color: {Theme.TEXT_DISABLED};
                border-color: {Theme.BORDER};
            }}
            QGroupBox:disabled QLabel {{
                color: {Theme.TEXT_DISABLED};
            }}
            QComboBox:disabled, QSpinBox:disabled {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                color: {Theme.TEXT_DISABLED};
            }}
            QCheckBox:disabled {{
                color: {Theme.TEXT_DISABLED};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("✨ Generate Subtitle")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {Theme.TEXT_PRIMARY};"
        )
        layout.addWidget(title)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Task Mode:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Full Subtitle (Whisper ASR)", "asr")
        self.cmb_mode.addItem("Timing Draft (VAD Only)", "timing")
        self.cmb_mode.setStyleSheet("font-weight: bold;")
        mode_layout.addWidget(self.cmb_mode, stretch=1)
        layout.addLayout(mode_layout)
        # Adapt Qt's int payload to the no-argument policy slot.
        self.cmb_mode.currentIndexChanged.connect(
            lambda _index: self._on_mode_changed()
        )

        self.model_group = QGroupBox("Model Configuration")
        model_layout = QVBoxLayout(self.model_group)
        self.cmb_model = QComboBox()
        self.cmb_model.addItems(
            ["tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo"]
        )
        self.cmb_model.setCurrentText("large-v3-turbo")
        model_layout.addWidget(QLabel("Model Size:"))
        model_layout.addWidget(self.cmb_model)

        self.cmb_compute = QComboBox()
        self.cmb_compute.addItems(["float16", "int8_float16", "int8"])
        self.cmb_compute.setCurrentText("float16")
        model_layout.addWidget(QLabel("Compute Type:"))
        model_layout.addWidget(self.cmb_compute)

        self.cmb_language = QComboBox()
        self.cmb_language.addItems(["Auto Detect", "vi", "en", "ja", "ko", "zh"])
        model_layout.addWidget(QLabel("Language:"))
        model_layout.addWidget(self.cmb_language)
        layout.addWidget(self.model_group)

        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QVBoxLayout(advanced_group)
        self.chk_vad = QCheckBox("Enable VAD (lọc khoảng lặng)")
        self.chk_vad.setChecked(True)
        advanced_layout.addWidget(self.chk_vad)

        self.chk_word_timestamps = QCheckBox("Word-level Timestamps")
        advanced_layout.addWidget(self.chk_word_timestamps)

        batch_mode_layout = QHBoxLayout()
        self.cmb_batch_mode = QComboBox()
        self.cmb_batch_mode.addItem("Time-based (Minutes)", "time")
        self.cmb_batch_mode.addItem("Segment-based (Count)", "segments")
        batch_mode_layout.addWidget(QLabel("Batch Mode:"))
        batch_mode_layout.addWidget(self.cmb_batch_mode, stretch=1)
        advanced_layout.addLayout(batch_mode_layout)

        batch_layout = QHBoxLayout()
        self.spin_batch_val = QSpinBox()
        self.spin_batch_val.setRange(1, 30)
        self.spin_batch_val.setValue(5)
        self.spin_batch_val.setSuffix(" min")
        # Compatibility alias for existing timing-panel integrations.
        self.spin_batch = self.spin_batch_val
        batch_layout.addWidget(QLabel("Batch Size:"))
        batch_layout.addWidget(self.spin_batch_val)
        advanced_layout.addLayout(batch_layout)
        self.cmb_batch_mode.currentIndexChanged.connect(
            lambda _index: self._on_batch_mode_changed()
        )
        layout.addWidget(advanced_group)

        layout.addStretch()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setObjectName("btn_primary")
        self.btn_resume = QPushButton("Resume")
        self.btn_resume.setObjectName("btn_warning")
        self.btn_resume.setVisible(False)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setEnabled(False)
        button_layout.addWidget(self.btn_generate)
        button_layout.addWidget(self.btn_resume)
        button_layout.addWidget(self.btn_cancel)
        layout.addLayout(button_layout)

        # Apply the initial batching and ASR/Timing policies before the panel is shown.
        self._on_batch_mode_changed()
        self.refresh_batch_mode_availability()
        self._on_mode_changed()

    def _connect_signals(self):
        self.btn_generate.clicked.connect(self._on_generate_clicked)
        self.btn_resume.clicked.connect(self._on_resume_clicked)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        self.generation_service.on_progress = self._update_progress
        self.generation_service.on_error = self._on_error
        self.generation_service.on_finish = self._on_finish

    @Slot()
    def _on_mode_changed(self):
        """Apply the settings policy for the selected generation pipeline."""
        is_asr = self.cmb_mode.currentData() == "asr"

        # Lock each control directly so a stylesheet cannot hide the disabled
        # state of the individual model settings.
        self.model_group.setEnabled(is_asr)
        self.cmb_model.setEnabled(is_asr)
        self.cmb_compute.setEnabled(is_asr)
        self.cmb_language.setEnabled(is_asr)
        self.chk_word_timestamps.setEnabled(is_asr)
        self.cmb_batch_mode.setEnabled(is_asr)
        # Timing Draft still needs its minute-based batch size; only the mode
        # selector is locked to Time in that pipeline.
        self.spin_batch_val.setEnabled(True)

        if is_asr:
            self.chk_vad.setEnabled(True)
            self.chk_vad.setText("Enable VAD (Lọc khoảng lặng)")
        else:
            self.chk_vad.setChecked(True)
            self.chk_vad.setEnabled(False)
            self.chk_vad.setText("Enable VAD (Bắt buộc cho chế độ này)")

    def _is_timing_mode(self) -> bool:
        return self.cmb_mode.currentData() == "timing"

    @Slot()
    def _on_batch_mode_changed(self):
        """Update batch-value range and suffix for the selected mode."""
        if self.cmb_batch_mode.currentData() == "time":
            self.spin_batch_val.setRange(1, 30)
            self.spin_batch_val.setValue(5)
            self.spin_batch_val.setSuffix(" min")
        else:
            self.spin_batch_val.setRange(5, 50)
            self.spin_batch_val.setValue(10)
            self.spin_batch_val.setSuffix(" segs")

    def set_video_duration(self, duration_ms: int):
        self.video_duration_ms = max(0, int(duration_ms or 0))
        self.refresh_batch_mode_availability()

    def _has_timing_artifact(self) -> bool:
        project_service = getattr(self.generation_service, "project_service", None)
        project = getattr(project_service, "current_project", None)
        timing_state = getattr(getattr(project, "state", None), "timing", None)
        artifact_id = getattr(timing_state, "timing_artifact_id", None)
        store = getattr(project_service, "artifact_store", None)
        artifact = store.get(artifact_id) if store and artifact_id else None
        return bool(artifact and getattr(artifact, "path", None))

    def refresh_batch_mode_availability(self):
        """Allow true segment-count batching only when Timing ranges exist."""
        if not hasattr(self, "cmb_batch_mode"):
            return
        item = self.cmb_batch_mode.model().item(1)
        if item is None:
            return
        enabled = self._has_timing_artifact()
        item.setEnabled(enabled)
        if not enabled and self.cmb_batch_mode.currentData() == "segments":
            self.cmb_batch_mode.setCurrentIndex(0)

    def check_resumable_state(self):
        checkpoint = self.generation_service.checkpoint_manager.load_checkpoint()
        resumable = bool(
            checkpoint and checkpoint.status in {"RUNNING", "CANCELLED", "FAILED"}
        )
        self.btn_resume.setVisible(resumable)
        service_running = bool(getattr(self.generation_service, "is_running", False))
        self.btn_resume.setEnabled(resumable and not service_running)

    @Slot()
    def _on_generate_clicked(self):
        if self.video_duration_ms <= 0:
            QMessageBox.warning(self, "Lỗi", "Chưa tải Video hoặc không đọc được thời lượng.")
            return

        if self._is_timing_mode():
            # Timing Draft is defined in minutes and does not consume the
            # subtitle segment-count planner.
            if self.cmb_batch_mode.currentData() != "time":
                self.cmb_batch_mode.setCurrentIndex(0)
            self._set_ui_state_running()
            self.timing_start_requested.emit(
                self.spin_batch_val.value(),
                {
                    # Keep the domain invariant even if the checkbox was
                    # changed programmatically while the mode was switching.
                    "use_vad": True,
                    "min_silence_ms": 500,
                },
            )
            return

        project = self.generation_service.project_service.current_project
        if not project:
            QMessageBox.warning(self, "Lỗi", "Chưa có dự án nào được mở.")
            return
        source = getattr(project, "source", None)
        source_fp = getattr(source, "fingerprint", "")
        video_path = getattr(source, "path", "")
        if not video_path:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy đường dẫn Video gốc trong Dự án.")
            return

        language = self.cmb_language.currentText()
        request = SubtitleGenerationRequest(
            request_id=str(uuid.uuid4()),
            project_id=project.project_id,
            source_fingerprint=source_fp,
            video_path=video_path,
            model_size=self.cmb_model.currentText(),
            compute_type=self.cmb_compute.currentText(),
            language=None if language == "Auto Detect" else language,
            use_vad=self.chk_vad.isChecked(),
            min_silence_ms=500,
            word_timestamps=self.chk_word_timestamps.isChecked(),
            batch_mode=self.cmb_batch_mode.currentData(),
            batch_size_value=self.spin_batch_val.value(),
            overlap_ms=2000,
        )
        self._set_ui_state_running()
        try:
            self.generation_service.start_generation(request, self.video_duration_ms)
        except Exception as exc:
            self._on_error(str(exc))

    @Slot()
    def _on_resume_clicked(self):
        self._set_ui_state_running()
        try:
            self.generation_service.resume_generation()
        except Exception as exc:
            self._on_error(str(exc))

    @Slot()
    def _on_cancel_clicked(self):
        self.lbl_status.setText("Cancelling...")
        self.btn_cancel.setEnabled(False)
        if self._is_timing_mode():
            self.timing_cancel_requested.emit()
        else:
            self.generation_service.cancel_generation()

    def _set_ui_state_running(self):
        self.btn_generate.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.cmb_mode.setEnabled(False)
        self.cmb_model.setEnabled(False)
        self.cmb_compute.setEnabled(False)
        self.cmb_language.setEnabled(False)
        self.cmb_batch_mode.setEnabled(False)
        self.spin_batch_val.setEnabled(False)
        self.chk_vad.setEnabled(False)
        self.chk_word_timestamps.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")

    def _reset_ui_state(self):
        service_running = bool(getattr(self.generation_service, "is_running", False))
        if service_running:
            # A cancel/error callback must not re-enable controls while the
            # underlying QThread is still winding down.
            self._set_ui_state_running()
            return
        self.btn_generate.setEnabled(not service_running)
        self.cmb_mode.setEnabled(True)
        self.btn_cancel.setEnabled(service_running)
        self.cmb_batch_mode.setEnabled(True)
        self.spin_batch_val.setEnabled(True)
        self.check_resumable_state()
        # Re-apply the current mode after every run/error/cancel transition.
        self._on_mode_changed()

    def _update_progress(self, percent: int, message: str):
        self.progress_bar.setValue(max(0, min(100, int(percent))))
        self.lbl_status.setText(message)

    def _on_error(self, error_message: str):
        self.lbl_status.setText(f"Error: {error_message}")
        self.lbl_status.setStyleSheet(f"color: {Theme.DANGER};")
        QMessageBox.critical(self, "Generation Error", error_message)
        self._reset_ui_state()

    def _on_finish(self):
        checkpoint = self.generation_service.checkpoint_manager.load_checkpoint()
        if checkpoint and checkpoint.status == "CANCELLED":
            self.lbl_status.setText("Cancelled. Resume when ready.")
            self.lbl_status.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            self.progress_bar.setValue(0)
        else:
            self.lbl_status.setStyleSheet(f"color: {Theme.SUCCESS};")
            self.progress_bar.setValue(100)
        self._reset_ui_state()
