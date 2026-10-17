import uuid

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import ( QLineEdit, QListWidget, QListWidgetItem,

    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QToolTip,
    QPushButton,
    QSpinBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.subtitle_generation.subtitle_generation_request import (
    SubtitleGenerationRequest,
)
from core.project.project_state import TimingState
from ui.theme import Theme


class SubtitleGenerationPanel(QWidget):
    """Qt view for robust subtitle generation; project data comes from the core."""

    # Timing Draft dùng pipeline VAD riêng, không khởi tạo Whisper ASR.
    timing_start_requested = Signal(int, dict)
    timing_resume_requested = Signal(int, dict)
    timing_cancel_requested = Signal()
    request_context_edit = Signal()
    _timing_settings_controls = (
        "cmb_model", "cmb_compute", "chk_vad", "chk_fix_overlap", "spin_overlap_gap"
    )

    def __init__(self, generation_service, parent=None):
        super().__init__(parent)
        self.generation_service = generation_service
        self._context_compiled = None
        self._context_configured = False
        self.video_duration_ms = 0
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # Panel uses global styling from LiquidThemeEngine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.settings_scroll_area = QScrollArea(self)
        self.settings_scroll_area.setWidgetResizable(True)
        self.settings_scroll_area.setFrameShape(QFrame.NoFrame)
        self.settings_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.settings_scroll_area.setMinimumHeight(60)
        self.settings_scroll_area.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        self.settings_scroll_content = QWidget()
        self.settings_scroll_content.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Minimum
        )
        settings_layout = QVBoxLayout(self.settings_scroll_content)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        title = QLabel("✨ Generate Subtitle")
        title.setProperty("class", "SectionTitle")
        settings_layout.addWidget(title)
        # --- PHASE 5: SUBTITLE SOURCE ---
        source_title = QLabel("Subtitle Source")
        source_title.setProperty("class", "SectionTitle")
        settings_layout.addWidget(source_title)
        
        source_h_layout = QHBoxLayout()
        self.cmb_subtitle_source = QComboBox()
        self.cmb_subtitle_source.addItem("Auto-detected SRT", "default")
        self.cmb_subtitle_source.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        source_h_layout.addWidget(self.cmb_subtitle_source)
        
        self.btn_add_external_srt = QPushButton("+ Add SRT...")
        self.btn_add_external_srt.setObjectName("btn_add_external_srt")
        source_h_layout.addWidget(self.btn_add_external_srt)
        settings_layout.addLayout(source_h_layout)
        
        self.btn_add_external_srt.clicked.connect(self._on_add_external_srt)
        self.cmb_subtitle_source.currentIndexChanged.connect(self._on_subtitle_source_changed)

        # --- PHASE 3: RANGE GENERATION ---
        self.range_group = QGroupBox("🎯 Generate theo khoảng thời gian")
        range_layout = QVBoxLayout(self.range_group)
        range_layout.setContentsMargins(12, 12, 12, 12)
        range_layout.setSpacing(8)
        
        # RANGE_TIME_INPUT_UNIT_SELECTOR: explicit units prevent 1-5 ambiguity.
        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel("Đơn vị nhập:"))
        self.cmb_range_unit = QComboBox()
        self.cmb_range_unit.addItem("Giây (s)", "seconds")
        self.cmb_range_unit.addItem("Phút (min)", "minutes")
        self._range_input_unit = "seconds"
        self.cmb_range_unit.setToolTip(
            "Chọn rõ đơn vị trước khi nhập để tránh nhầm 1–5 giây với 1–5 phút."
        )
        unit_row.addWidget(self.cmb_range_unit)
        unit_row.addStretch()
        range_layout.addLayout(unit_row)

        time_row = QHBoxLayout()
        self.txt_start = QLineEdit()
        self.txt_start.setPlaceholderText("Ví dụ: 60,5")
        self.txt_end = QLineEdit()
        self.txt_end.setPlaceholderText("Ví dụ: 70")
        time_row.addWidget(QLabel("Từ:"))
        time_row.addWidget(self.txt_start)
        time_row.addWidget(QLabel("Đến:"))
        time_row.addWidget(self.txt_end)
        range_layout.addLayout(time_row)
        self.txt_start.textChanged.connect(
            lambda _text: self._clear_range_input_error(self.txt_start)
        )
        self.txt_end.textChanged.connect(
            lambda _text: self._clear_range_input_error(self.txt_end)
        )
        self.cmb_range_unit.currentIndexChanged.connect(
            lambda _index: self._on_range_unit_changed()
        )
        self._refresh_range_input_help()
        
        range_btn_row = QHBoxLayout()
        self.btn_range_timeline = QPushButton("⏱ Lấy từ vùng Timeline")
        self.btn_range_timeline.setProperty("variant", "secondary")
        self.btn_range_preview = QPushButton("Preview Range")
        self.btn_range_preview.setProperty("variant", "primary")
        
        range_btn_row.addWidget(self.btn_range_timeline)
        range_btn_row.addWidget(self.btn_range_preview)
        range_layout.addLayout(range_btn_row)
        
        settings_layout.addWidget(self.range_group)
        
        self.btn_range_preview.clicked.connect(self._on_preview_range_clicked)
        # ---------------------------------


        def _kv_row(label_text, widget, min_width=None):
            row = QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(12)
            lbl = QLabel(label_text)
            lbl.setProperty("class", "Caption")
            lbl.setFixedWidth(100)
            target_min_width = min_width if min_width is not None else max(widget.minimumWidth(), 160)
            widget.setMinimumWidth(target_min_width)
            row.addWidget(lbl)
            row.addWidget(widget)
            row.addStretch()
            return row

        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 4, 0, 4)
        mode_layout.setSpacing(12)
        mode_lbl = QLabel("Task Mode:")
        mode_lbl.setProperty("class", "Caption")
        mode_lbl.setFixedWidth(100)
        mode_layout.addWidget(mode_lbl)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Full Subtitle (Whisper ASR)", "asr")
        self.cmb_mode.addItem("Timing Draft (VAD Only)", "timing")
        self.cmb_mode.setMinimumWidth(210)
        mode_layout.addWidget(self.cmb_mode)
        mode_layout.addStretch()
        settings_layout.addLayout(mode_layout)
        # Adapt Qt's int payload to the no-argument policy slot.
        self.cmb_mode.currentIndexChanged.connect(
            lambda _index: self._on_mode_changed()
        )
        self.cmb_mode.currentIndexChanged.connect(self._on_task_mode_changed)

        self.model_group = QGroupBox("Model Configuration")
        model_layout = QVBoxLayout(self.model_group)
        model_layout.setContentsMargins(0, 6, 0, 6)
        model_layout.setSpacing(8)

        # --- Model Size row: combo + Download button ---
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 2, 0, 2)
        model_row.setSpacing(8)
        model_lbl = QLabel("Model Size:")
        model_lbl.setProperty("class", "Caption")
        model_lbl.setFixedWidth(100)
        self.cmb_model = QComboBox()
        self.cmb_model.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_download_model = QPushButton("⬇ Download")
        self.btn_download_model.setProperty("variant", "secondary")
        self.btn_download_model.setFixedHeight(28)
        self.btn_download_model.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_download_model.setToolTip("Download model from HuggingFace")
        self.btn_download_model.clicked.connect(self._on_download_model_clicked)
        model_row.addWidget(model_lbl)
        model_row.addWidget(self.cmb_model)
        model_row.addWidget(self.btn_download_model)
        model_layout.addLayout(model_row)

        # --- Compute Type row with recommendation ---
        self.cmb_compute = QComboBox()
        self.cmb_compute.setMinimumWidth(160)
        self._populate_compute_combo()
        model_layout.addLayout(_kv_row("Compute Type:", self.cmb_compute))

        self.lbl_effective_compute = QLabel("Effective: not run")
        self.lbl_effective_compute.setProperty("class", "Caption")
        model_layout.addWidget(self.lbl_effective_compute)

        self.cmb_language = QComboBox()
        self.cmb_language.addItems(["Auto Detect", "vi", "en", "ja", "ko", "zh"])
        model_layout.addLayout(_kv_row("Language:", self.cmb_language))
        settings_layout.addWidget(self.model_group)

        # Populate model combo after widget tree is ready
        self._populate_model_combo()

        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QVBoxLayout(advanced_group)
        advanced_layout.setContentsMargins(0, 6, 0, 6)
        advanced_layout.setSpacing(8)

        self.chk_vad = QCheckBox("Enable VAD (lọc khoảng lặng)")
        self.chk_vad.setChecked(True)
        advanced_layout.addWidget(self.chk_vad)

        self.chk_fix_overlap = QCheckBox("Fix subtitle overlap")
        self.chk_fix_overlap.setChecked(True)
        advanced_layout.addWidget(self.chk_fix_overlap)

        self.spin_overlap_gap = QSpinBox()
        self.spin_overlap_gap.setRange(1, 500)
        self.spin_overlap_gap.setValue(50)
        self.spin_overlap_gap.setSuffix(" ms")
        advanced_layout.addLayout(_kv_row("Overlap gap:", self.spin_overlap_gap))

        self.chk_word_timestamps = QCheckBox("Word-level Timestamps")
        advanced_layout.addWidget(self.chk_word_timestamps)

        self.cmb_batch_mode = QComboBox()
        self.cmb_batch_mode.addItem("Time-based (Minutes)", "time")
        self.cmb_batch_mode.addItem("Segment-based (Count)", "segments")
        self.cmb_batch_mode.setMinimumWidth(210)
        advanced_layout.addLayout(_kv_row("Batch Mode:", self.cmb_batch_mode, min_width=210))

        self.spin_batch_val = QSpinBox()
        self.spin_batch_val.setRange(1, 30)
        self.spin_batch_val.setValue(5)
        self.spin_batch_val.setSuffix(" min")
        # Compatibility alias for existing timing-panel integrations.
        self.spin_batch = self.spin_batch_val
        advanced_layout.addLayout(_kv_row("Batch Size:", self.spin_batch_val))
        self.cmb_batch_mode.currentIndexChanged.connect(
            lambda _index: self._on_batch_mode_changed()
        )
        self.chk_fix_overlap.toggled.connect(self._on_timing_setting_changed)
        self.spin_overlap_gap.valueChanged.connect(self._on_timing_setting_changed)
        self.cmb_model.currentTextChanged.connect(self._on_timing_setting_changed)
        self.cmb_compute.currentTextChanged.connect(self._on_timing_setting_changed)
        self.chk_vad.toggled.connect(self._on_timing_setting_changed)
        settings_layout.addWidget(advanced_group)
        # --- PHASE 3: GENERATION HISTORY ---
        self.history_group = QGroupBox("↩ Generation History")
        history_layout = QVBoxLayout(self.history_group)
        history_layout.setContentsMargins(12, 12, 12, 12)
        
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(150)
        history_layout.addWidget(self.history_list)
        
        self.btn_rollback = QPushButton("Khôi phục (Rollback)")
        self.btn_rollback.setProperty("variant", "danger")
        self.btn_rollback.setEnabled(False)
        history_layout.addWidget(self.btn_rollback)
        
        settings_layout.addWidget(self.history_group)
        
        self.history_list.itemSelectionChanged.connect(self._on_history_selection_changed)
        self.btn_rollback.clicked.connect(self._on_rollback_clicked)
        # -----------------------------------


        context_layout = QHBoxLayout()
        context_layout.setContentsMargins(0, 6, 0, 0)
        self.lbl_context_status = QLabel("Context: not configured")
        self.lbl_context_status.setProperty("class", "Caption")
        self.lbl_context_status.setWordWrap(True)
        self.btn_context_edit = QPushButton("Edit context")
        self.btn_context_edit.setProperty("variant", "secondary")
        self.context_status_label = self.lbl_context_status
        self.edit_context_btn = self.btn_context_edit
        context_layout.addWidget(self.lbl_context_status, stretch=1)
        context_layout.addWidget(self.btn_context_edit)
        settings_layout.addLayout(context_layout)
        
        # --- PHASE 3: HISTORY GROUP ---
        self.history_group = QGroupBox("↩ Generation History")
        history_layout = QVBoxLayout(self.history_group)
        history_layout.setContentsMargins(12, 12, 12, 12)
        history_layout.setSpacing(8)
        
        self.history_list_layout = QVBoxLayout()
        history_layout.addLayout(self.history_list_layout)
        
        # Quick Rollback row
        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("Rollback:"))
        self.btn_rb_10 = QPushButton("10")
        self.btn_rb_30 = QPushButton("30")
        self.btn_rb_50 = QPushButton("50")
        self.btn_rb_60 = QPushButton("60")
        self.btn_rb_initial = QPushButton("Initial")
        for btn in (self.btn_rb_10, self.btn_rb_30, self.btn_rb_50, self.btn_rb_60, self.btn_rb_initial):
            quick_row.addWidget(btn)
            btn.clicked.connect(lambda checked=False, b=btn: self._on_quick_rollback_clicked(b.text()))
            
        quick_row.addStretch()
        history_layout.addLayout(quick_row)
        
        settings_layout.addWidget(self.history_group)
        # ------------------------------

        settings_layout.addStretch()
        self.settings_scroll_area.setWidget(self.settings_scroll_content)
        layout.addWidget(self.settings_scroll_area, stretch=1)

        self.action_footer = QWidget(self)
        self.action_footer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        footer_layout = QVBoxLayout(self.action_footer)
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(6)

        self.lbl_status = QLabel("Ready")
        self._configure_status_label(self.lbl_status)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setProperty("class", "Caption")
        footer_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        footer_layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        self.btn_generate = QPushButton("✨ Generate Subtitle")
        self.btn_generate.setFixedHeight(34)
        self.btn_generate.setObjectName("btn_primary")
        self.btn_generate.setProperty("variant", "primary")

        self.btn_resume = QPushButton("Resume")
        self.btn_resume.setFixedHeight(34)
        self.btn_resume.setObjectName("btn_warning")
        self.btn_resume.setProperty("variant", "warning")
        self.btn_resume.setVisible(False)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setProperty("variant", "danger")
        self.btn_cancel.setEnabled(False)

        button_layout.addWidget(self.btn_generate, stretch=3)
        button_layout.addWidget(self.btn_resume, stretch=3)
        button_layout.addWidget(self.btn_cancel, stretch=1)
        footer_layout.addLayout(button_layout)
        layout.addWidget(self.action_footer, stretch=0)

        # Apply the initial batching and ASR/Timing policies before the panel is shown.
        self._on_batch_mode_changed()
        self.refresh_batch_mode_availability()
        self._on_mode_changed()

    def take_action_footer(self):
        """Detach the action footer so the host can pin it outside the tab stack.

        The buttons remain owned by this panel logically: their signal handlers,
        progress callbacks, and state updates continue to target this instance.
        Only the QWidget parent/layout position changes.
        """
        footer = getattr(self, "action_footer", None)
        if footer is None:
            return None
        panel_layout = self.layout()
        if panel_layout is not None:
            panel_layout.removeWidget(footer)
        footer.setParent(None)
        return footer

    @staticmethod
    def _configure_status_label(label):
        """Keep long errors inside the drawer's existing width."""
        label.setWordWrap(True)

    def _connect_signals(self):
        self.btn_generate.clicked.connect(self._on_generate_clicked)
        self.btn_resume.clicked.connect(self._on_resume_clicked)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        self.btn_context_edit.clicked.connect(self.request_context_edit)
        self.generation_service.on_progress = self._update_progress
        self.generation_service.on_error = self._on_error
        self.generation_service.on_finish = self._on_finish
        self.cmb_model.currentIndexChanged.connect(self._on_model_selection_changed)

    # ── Model list helpers ────────────────────────────────────────────────────

    @staticmethod
    def _combo_value(combo):
        if hasattr(combo, "currentData"):
            val = combo.currentData()
            if val is not None:
                return val
        return combo.currentText() if hasattr(combo, "currentText") else ""

    _ALL_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo"]

    def _populate_model_combo(self, preferred: str = "large-v3-turbo") -> None:
        """Fill cmb_model with install-status icons; keep previous selection if valid."""
        from core.services.model_manager import ModelManager
        prev = self.cmb_model.currentData() or preferred
        self.cmb_model.blockSignals(True)
        self.cmb_model.clear()
        try:
            info = {m["size"]: m["installed"] for m in ModelManager.get_discovery_list()}
        except Exception:
            info = {m: False for m in self._ALL_MODELS}
        for size in self._ALL_MODELS:
            installed = info.get(size, False)
            icon = "✅" if installed else "⬇"
            weight = ModelManager.SUPPORTED_MODELS.get(size, "")
            label = f"{icon} {size}  ({weight})"
            self.cmb_model.addItem(label, size)  # userData = bare model size
        self.cmb_model.blockSignals(False)
        # Restore previous or preferred
        for i in range(self.cmb_model.count()):
            if self.cmb_model.itemData(i) == prev:
                self.cmb_model.setCurrentIndex(i)
                break
        else:
            # fall back to preferred
            for i in range(self.cmb_model.count()):
                if self.cmb_model.itemData(i) == preferred:
                    self.cmb_model.setCurrentIndex(i)
                    break
        self._on_model_selection_changed()

    def _on_model_selection_changed(self) -> None:
        """Show/hide Download button based on whether selected model is installed."""
        from core.services.model_manager import ModelManager
        size = self.cmb_model.currentData()
        installed = ModelManager.is_installed(size) if size else False
        self.btn_download_model.setVisible(not installed)

    def _on_download_model_clicked(self) -> None:
        """Trigger background download for the currently selected uninstalled model."""
        from PySide6.QtCore import QThread
        from core.services.model_manager import ModelManager

        size = self.cmb_model.currentData()
        if not size:
            return
        if ModelManager.is_installed(size):
            self._populate_model_combo(preferred=size)
            return

        self.btn_download_model.setEnabled(False)
        self.btn_download_model.setText("Downloading…")
        self.lbl_effective_compute.setText(f"Downloading {size}…")

        class _DlThread(QThread):
            def __init__(self, model_size):
                super().__init__()
                self._size = model_size
            def run(self):
                ModelManager.download_model_sync(self._size)

        thread = _DlThread(size)
        thread.setParent(self)

        def _done():
            self.btn_download_model.setEnabled(True)
            self.btn_download_model.setText("⬇ Download")
            self.lbl_effective_compute.setText("Effective: not run")
            self._populate_model_combo(preferred=size)

        thread.finished.connect(_done)
        thread.start()

    # ── Compute type recommendation ───────────────────────────────────────────

    def _populate_compute_combo(self) -> None:
        """Populate compute combo with ★ marker on the option best for this machine."""
        try:
            import torch
            has_cuda = torch.cuda.is_available()
            vram_gb = (
                torch.cuda.get_device_properties(0).total_memory // (1024 ** 3)
                if has_cuda else 0
            )
        except Exception:
            has_cuda = False
            vram_gb = 0

        # Determine recommended option:
        # GPU >=4 GB VRAM → float16 (fastest, full precision)
        # GPU 2-3 GB VRAM → int8_float16 (saves VRAM, still GPU)
        # CPU only         → int8 (CPU only option)
        if has_cuda and vram_gb >= 4:
            recommended = "float16"
        elif has_cuda:
            recommended = "int8_float16"
        else:
            recommended = "int8"

        options = ["float16", "int8_float16", "int8"]
        self.cmb_compute.clear()
        for opt in options:
            label = f"★ {opt}  (Recommended)" if opt == recommended else opt
            self.cmb_compute.addItem(label, opt)
        # Select recommended by default
        for i in range(self.cmb_compute.count()):
            if self.cmb_compute.itemData(i) == recommended:
                self.cmb_compute.setCurrentIndex(i)
                break

    def apply_recommended_settings(self, model: str, compute: str) -> None:
        """Apply recommended model and compute type to panel combos."""
        for i in range(self.cmb_model.count()):
            if self.cmb_model.itemData(i) == model:
                self.cmb_model.setCurrentIndex(i)
                break
        for i in range(self.cmb_compute.count()):
            if self.cmb_compute.itemData(i) == compute:
                self.cmb_compute.setCurrentIndex(i)
                break

    def set_context_status(self, compiled, configured: bool) -> None:
        self._context_compiled = compiled
        self._context_configured = configured
        self._render_context_status()

    def _render_context_status(self) -> None:
        label = getattr(self, "context_status_label", None)
        if label is None:
            return
        if self._is_timing_mode():
            label.setText("Context: not used in Timing Draft")
            return
        if not self._context_configured or self._context_compiled is None:
            label.setText("Context: not configured")
            return
        compiled = self._context_compiled
        total_glossary = compiled.glossary_items_used + compiled.glossary_items_dropped
        label.setText(
            "Context: configured · "
            f"{compiled.glossary_items_used}/{total_glossary} glossary · "
            f"~{compiled.token_count}/{compiled.max_tokens} tokens"
        )

    @Slot()
    def _on_mode_changed(self):
        """Apply the settings policy for the selected generation pipeline."""
        is_asr = self.cmb_mode.currentData() == "asr"

        # Lock each control directly so a stylesheet cannot hide the disabled
        # state of the individual model settings.
        self.model_group.setEnabled(True)
        self.cmb_model.setEnabled(True)
        self.cmb_compute.setEnabled(True)
        self.cmb_language.setEnabled(is_asr)
        self.chk_word_timestamps.setEnabled(is_asr)
        self.cmb_batch_mode.setEnabled(True)
        # Timing Draft accepts both the legacy time setting and its native
        # segment-count setting. The worker already consumes this value as a
        # target segment count.
        self.spin_batch_val.setEnabled(True)

        if is_asr:
            self.chk_vad.setEnabled(True)
            self.chk_vad.setText("Enable VAD (Lọc khoảng lặng)")
        else:
            self.chk_vad.setChecked(True)
            self.chk_vad.setEnabled(False)
            self.chk_vad.setText("Enable VAD (Bắt buộc cho chế độ này)")

        fix_overlap = getattr(self, "chk_fix_overlap", None)
        overlap_gap = getattr(self, "spin_overlap_gap", None)
        if fix_overlap is not None:
            fix_overlap.setEnabled(not is_asr)
        if overlap_gap is not None:
            overlap_gap.setEnabled(not is_asr and fix_overlap.isChecked())

        if hasattr(self, "btn_resume"):
            self.check_resumable_state()
        self.refresh_batch_mode_availability()
        self._render_context_status()

    def _is_timing_mode(self) -> bool:
        return self.cmb_mode.currentData() == "timing"

    def _on_task_mode_changed(self, *_args):
        if getattr(self, "_restoring_timing_settings", False):
            return
        project_service = getattr(self.generation_service, "project_service", None)
        project = getattr(project_service, "current_project", None)
        state = getattr(project, "state", None)
        if state is None or not hasattr(state, "task_mode"):
            return
        state.task_mode = self.cmb_mode.currentData()
        project_service.mark_dirty()

    @Slot()
    def _on_batch_mode_changed(self):
        """Update batch-value range and suffix for the selected mode."""
        if (
            self.cmb_batch_mode.currentData() == "segments"
            and not self._is_timing_mode()
            and not self._timing_segments_available()
        ):
            res = QMessageBox.question(
                self,
                "Yêu cầu Timing Draft",
                "Chế độ băm theo số câu (Segment-based) cần mốc câu có sẵn từ Timing Draft để Whisper biết vị trí từng câu.\n\n"
                "Bạn có muốn chuyển sang chế độ 'Timing Draft (VAD Only)' để tạo mốc câu trước không (chỉ mất vài giây)?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if res == QMessageBox.Yes:
                idx = self.cmb_mode.findData("timing") if hasattr(self.cmb_mode, "findData") else -1
                if idx >= 0:
                    self.cmb_mode.setCurrentIndex(idx)
                    if hasattr(self.spin_batch_val, "setRange"):
                        self.spin_batch_val.setRange(5, 50)
                        self.spin_batch_val.setValue(10)
                        self.spin_batch_val.setSuffix(" segs")
                    return
            self.cmb_batch_mode.setCurrentIndex(0)
            return
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

    def _timing_segments_available(self) -> bool:
        project_service = getattr(self.generation_service, "project_service", None)
        project = getattr(project_service, "current_project", None)
        timing_status = getattr(
            getattr(project, "state", None), "timing_status", None
        )
        return timing_status in {"DRAFT", "READY"} and self._has_timing_artifact()

    def refresh_batch_mode_availability(self):
        """Allow true segment-count batching only when Timing ranges exist; hide otherwise."""
        if not hasattr(self, "cmb_batch_mode"):
            return
        seg_idx = -1
        if hasattr(self.cmb_batch_mode, "findData"):
            seg_idx = self.cmb_batch_mode.findData("segments")
        if seg_idx < 0:
            seg_idx = 1
        item = (
            self.cmb_batch_mode.model().item(seg_idx)
            if hasattr(self.cmb_batch_mode, "model")
            else None
        )
        if item is None:
            return
        # Timing Draft is what creates the Timing Artifact, so it must be
        # allowed to use segment-count batching before an artifact exists.
        enabled = self._is_timing_mode() or (
            self._timing_segments_available()
        )
        if hasattr(item, "setEnabled"):
            item.setEnabled(enabled)
        view = getattr(self.cmb_batch_mode, "view", None)
        if callable(view):
            v = view()
            if hasattr(v, "setRowHidden"):
                v.setRowHidden(seg_idx, not enabled)
        if not enabled and self.cmb_batch_mode.currentData() == "segments":
            self.cmb_batch_mode.setCurrentIndex(0)

    def check_resumable_state(self):
        current_request = getattr(self.generation_service, "current_request", None)
        current_checkpoint = getattr(self.generation_service, "current_checkpoint", None)
        range_run_terminal = bool(
            current_request
            and current_request.range_start_ms is not None
            and current_checkpoint
            and current_checkpoint.status in {"COMPLETED", "CANCELLED", "FAILED"}
        )
        if range_run_terminal:
            resumable = False
        elif self._is_timing_mode():
            resumable = self._has_resumable_timing_checkpoint()
        else:
            checkpoint = self.generation_service.checkpoint_manager.load_checkpoint()
            resumable = bool(
                checkpoint
                and checkpoint.status in {"RUNNING", "CANCELLED", "FAILED"}
            )
        self.btn_resume.setVisible(resumable)
        service_running = bool(getattr(self.generation_service, "is_running", False))
        self.btn_resume.setEnabled(resumable and not service_running)

    def _has_resumable_timing_checkpoint(self) -> bool:
        project_service = getattr(self.generation_service, "project_service", None)
        load_checkpoint = getattr(project_service, "load_timing_checkpoint", None)
        checkpoint = load_checkpoint() if callable(load_checkpoint) else None
        if not checkpoint:
            return False

        project = getattr(project_service, "current_project", None)
        timing_state = getattr(getattr(project, "state", None), "timing", None)
        if getattr(timing_state, "status", None) == "COMPLETED":
            return False
        return bool(
            getattr(checkpoint, "timing_artifact_id", None)
            or getattr(checkpoint, "active_batch", None)
        )

    @Slot()
    def _on_generate_clicked(self):
        if self.video_duration_ms <= 0:
            project = getattr(
                getattr(self.generation_service, "project_service", None),
                "current_project",
                None,
            )
            video_path = getattr(getattr(project, "source", None), "path", "")
            if video_path and os.path.exists(video_path):
                try:
                    from workers.TaskQueue import get_video_duration

                    dur_sec = get_video_duration(video_path)
                    if dur_sec > 0:
                        self.set_video_duration(int(dur_sec * 1000))
                except Exception:
                    pass

        if self.video_duration_ms <= 0:
            QMessageBox.warning(self, "Lỗi", "Chưa tải Video hoặc không đọc được thời lượng.")
            return

        if self._is_timing_mode():
            timing_settings = self._timing_settings()
            self._set_ui_state_running()
            if self._has_resumable_timing_checkpoint():
                self.timing_resume_requested.emit(
                    self.spin_batch_val.value(), timing_settings
                )
            else:
                self.timing_start_requested.emit(
                    self.spin_batch_val.value(), timing_settings
                )
            return

        request = self._build_asr_request()
        if request is None:
            return

        self._set_ui_state_running()
        try:
            self.generation_service.start_generation(request, self.video_duration_ms)
        except Exception as exc:
            self._on_error(str(exc))

    def _build_asr_request(self, range_start_ms=None, range_end_ms=None):
        project = self.generation_service.project_service.current_project
        if not project:
            QMessageBox.warning(self, "Lỗi", "Chưa có dự án nào được mở.")
            return None
        source = getattr(project, "source", None)
        video_path = getattr(source, "path", "")
        if not video_path:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy đường dẫn Video gốc trong Dự án.")
            return None
        compiled_context = self.generation_service.compile_prompt_context(
            project.transcription_context
        )
        language = self.cmb_language.currentText()
        return SubtitleGenerationRequest(
            request_id=str(uuid.uuid4()),
            project_id=project.project_id,
            source_fingerprint=getattr(source, "fingerprint", ""),
            video_path=video_path,
            model_size=self._combo_value(self.cmb_model),
            compute_type=self._combo_value(self.cmb_compute),
            language=None if language == "Auto Detect" else language,
            use_vad=self.chk_vad.isChecked(),
            min_silence_ms=500,
            word_timestamps=self.chk_word_timestamps.isChecked(),
            batch_mode=self.cmb_batch_mode.currentData(),
            batch_size_value=self.spin_batch_val.value(),
            overlap_ms=2000,
            prompt_context=compiled_context.text,
            range_start_ms=range_start_ms,
            range_end_ms=range_end_ms,
        )

    def start_range_generation(self, start_ms, end_ms, existing_segments):
        if self.video_duration_ms <= 0 or self._is_timing_mode():
            self._on_error("Range generation requires loaded media in Full Subtitle mode.")
            return
        request = self._build_asr_request(start_ms, end_ms)
        if request is None:
            return
        self._set_ui_state_running()
        try:
            self.generation_service.start_generation(
                request,
                self.video_duration_ms,
                existing_segments=existing_segments,
            )
        except Exception as exc:
            self._on_error(self._range_error_message(str(exc)))

    @staticmethod
    def _range_error_message(message):
        if message.startswith("TIMING_RECONCILIATION_REQUIRED:"):
            return "Kết quả phụ đề vượt ngoài khoảng thời gian đã chọn. Khoảng hiện có chưa được thay đổi."
        if message.startswith("STALE_RANGE_CONFLICT:"):
            return "Khoảng đã chọn đã thay đổi. Vui lòng kiểm tra lại trước khi tạo."
        if message.startswith("RECONCILIATION_UNSAFE:"):
            return "Không thể tự điều chỉnh thời gian an toàn. Phụ đề chưa được thêm."
        if message.startswith("OVERLAPS_SUBTITLE:"):
            return "Khoảng đã chọn hiện có phụ đề; hãy chọn một khoảng trống khác."
        return message

    @Slot()
    def _on_resume_clicked(self):
        self._set_ui_state_running()
        try:
            if self._is_timing_mode():
                self.timing_resume_requested.emit(
                    self.spin_batch_val.value(),
                    self._timing_settings(),
                )
            else:
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
        if hasattr(self, "chk_fix_overlap"):
            self.chk_fix_overlap.setEnabled(False)
        if hasattr(self, "spin_overlap_gap"):
            self.spin_overlap_gap.setEnabled(False)
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

    def _timing_settings(self) -> dict:
        project_service = getattr(self.generation_service, "project_service", None)
        timing = getattr(
            getattr(getattr(project_service, "current_project", None), "state", None),
            "timing",
            None,
        )
        if timing is not None and hasattr(timing, "model_size"):
            values = {
                name: getattr(timing, name, getattr(TimingState(), name))
                for name in (
                    "model_size", "compute_type", "use_vad", "min_silence_ms",
                    "fix_overlap", "overlap_gap_ms", "overlap_ms", "max_window_ms",
                )
            }
            if self._is_timing_mode():
                values["use_vad"] = True
            return values
        return {
            "model_size": self._combo_value(self.cmb_model),
            "compute_type": self._combo_value(self.cmb_compute),
            "use_vad": True,
            "min_silence_ms": 500,
            "fix_overlap": getattr(self, "chk_fix_overlap", None).isChecked()
            if hasattr(self, "chk_fix_overlap") else True,
            "overlap_gap_ms": getattr(self, "spin_overlap_gap", None).value()
            if hasattr(self, "spin_overlap_gap") else 50,
            "overlap_ms": 800,
            "max_window_ms": 120000,
        }

    def _on_timing_setting_changed(self, *_args):
        if getattr(self, "_restoring_timing_settings", False) or not self._is_timing_mode():
            return
        project_service = getattr(self.generation_service, "project_service", None)
        project = getattr(project_service, "current_project", None)
        timing = getattr(getattr(project, "state", None), "timing", None)
        if timing is None:
            return
        values = self._timing_settings()
        values.update(
            {
                "model_size": self._combo_value(self.cmb_model),
                "compute_type": self._combo_value(self.cmb_compute),
                "use_vad": True,
                "fix_overlap": self.chk_fix_overlap.isChecked(),
                "overlap_gap_ms": self.spin_overlap_gap.value(),
            }
        )
        for name, value in values.items():
            setattr(timing, name, value)
        project_service.mark_dirty()
        if hasattr(self, "spin_overlap_gap"):
            self.spin_overlap_gap.setEnabled(self.chk_fix_overlap.isChecked())

    def sync_timing_settings_from_project(self):
        project_service = getattr(self.generation_service, "project_service", None)
        timing = getattr(
            getattr(getattr(project_service, "current_project", None), "state", None),
            "timing",
            None,
        )
        if not isinstance(timing, TimingState):
            return
        self._restoring_timing_settings = True
        try:
            task_mode = getattr(getattr(project_service.current_project, "state", None), "task_mode", "asr")
            mode_index = self.cmb_mode.findData(task_mode)
            if mode_index >= 0:
                self.cmb_mode.setCurrentIndex(mode_index)
            for i in range(self.cmb_model.count()):
                if self.cmb_model.itemData(i) == timing.model_size:
                    self.cmb_model.setCurrentIndex(i)
                    break
            for i in range(self.cmb_compute.count()):
                if self.cmb_compute.itemData(i) == timing.compute_type:
                    self.cmb_compute.setCurrentIndex(i)
                    break
            self.chk_vad.setChecked(timing.use_vad)
            self.chk_fix_overlap.setChecked(timing.fix_overlap)
            self.spin_overlap_gap.setValue(timing.overlap_gap_ms)
            self._on_mode_changed()
        finally:
            self._restoring_timing_settings = False

    def set_effective_compute_type(self, configured: str, effective: str):
        self.lbl_effective_compute.setText(
            f"Configured: {configured} · Effective: {effective}"
        )

    def _update_progress(self, percent: int, message: str):
        self.progress_bar.setValue(max(0, min(100, int(percent))))
        self.lbl_status.setText(message)


    def _on_quick_rollback_clicked(self, target_str):
        if target_str == "Initial":
            target_count = 0
        else:
            try:
                target_count = int(target_str)
            except ValueError:
                return
                
        cp = self.generation_service.get_rollback_checkpoint(target_count=target_count)
        if not cp:
            self._on_error(f"Không có checkpoint nào tương ứng với {target_str} subtitles.")
            return
            
        self._trigger_rollback(cp)

    def _trigger_rollback(self, cp):
        from ui.dialogs.restore_preview_dialog import RestorePreviewDialog
        
        current_segments = self._get_current_segments()
        current_count = len(current_segments)
        target_count = cp.generated_count
        
        manual_edits = 0
        # Check manual edits
        if len(current_segments) == len(cp.segments_snapshot):
            for cur, snap in zip(current_segments, cp.segments_snapshot):
                if cur.get("source") == "manual" and snap.get("source") != "manual":
                    manual_edits += 1
                elif cur.get("start") != snap.get("start") or cur.get("end") != snap.get("end") or cur.get("text") != snap.get("text"):
                    manual_edits += 1
        else:
            manual_edits = sum(1 for s in current_segments if s.get("source") == "manual")
            
        dialog = RestorePreviewDialog(current_count, target_count, manual_edits, self)
        if dialog.exec():
            # Perform rollback
            from PySide6.QtWidgets import QApplication
            main_window = QApplication.instance().activeWindow()
            if main_window and hasattr(main_window, 'undo_manager'):
                try:
                    self.generation_service.execute_rollback(target_count, self._get_current_segments(), main_window.undo_manager, checkpoint_id=cp.checkpoint_id)
                    if hasattr(main_window, 'sub_editor'):
                        main_window.sub_editor.render_page()
                    # We might need to refresh history UI
                    self.refresh_history_ui()
                except Exception as e:
                    self._on_error(str(e))
            else:
                self._on_error("Khong tim thay Undo Manager.")

    def refresh_history_ui(self):
        # Clear existing
        if not hasattr(self, 'history_list_layout'):
            return
        while self.history_list_layout.count():
            child = self.history_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # Build history list
        from PySide6.QtWidgets import QPushButton
        
        if hasattr(self.generation_service, "_ensure_history_loaded"):
            self.generation_service._ensure_history_loaded()
            
        history = list(getattr(self.generation_service, "checkpoint_history", []))
        initial = getattr(self.generation_service, "initial_state", None)
        if initial:
            history.insert(0, initial)
            
        # Sort newest first for display
        history.reverse()
        
        for cp in history:
            label_text = "Initial" if cp.checkpoint_type == "INITIAL" else f"#{cp.generated_count} ({cp.checkpoint_type})"
            if cp.checkpoint_type == "RANGE" and cp.generation_range:
                from ui.SubEditor import ms_to_time_str
                label_text += f" {ms_to_time_str(cp.generation_range.get('start_ms', 0))} -> {ms_to_time_str(cp.generation_range.get('end_ms', 0))}"
            
            btn = QPushButton(label_text)
            btn.setStyleSheet("text-align: left; padding: 4px;")
            btn.clicked.connect(lambda checked=False, c=cp: self._trigger_rollback(c))
            self.history_list_layout.addWidget(btn)

    def _on_error(self, error_message: str):
        self.lbl_status.setText(f"Error: {error_message}")
        self.lbl_status.setStyleSheet(f"color: {Theme.DANGER};")
        QMessageBox.critical(self, "Generation Error", error_message)
        self._reset_ui_state()

    def _on_finish(self):
        current = getattr(self.generation_service, "current_checkpoint", None)
        range_run = bool(
            getattr(self.generation_service, "current_request", None)
            and self.generation_service.current_request.range_start_ms is not None
        )
        checkpoint = (
            None if range_run
            else self.generation_service.checkpoint_manager.load_checkpoint()
        )
        if (range_run and current and current.status == "CANCELLED") or (
            checkpoint and checkpoint.status == "CANCELLED"
        ):
            self.lbl_status.setText("Cancelled. Resume when ready.")
            self.lbl_status.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            self.progress_bar.setValue(0)
        else:
            self.lbl_status.setStyleSheet(f"color: {Theme.SUCCESS};")
            self.progress_bar.setValue(100)
        self._reset_ui_state()

    # --- PHASE 3: RANGE & HISTORY LOGIC ---
    def _range_unit_factor_ms(self, unit=None):
        unit = unit or self._range_input_unit
        return 1000 if unit == "seconds" else 60000

    def _range_unit_label(self, unit=None):
        unit = unit or self._range_input_unit
        return "giây" if unit == "seconds" else "phút"

    def _range_input_help(self):
        if self._range_input_unit == "seconds":
            return (
                "Nhập số giây không âm, không cần gõ s. Ví dụ: 60–70 hoặc "
                "60,5–70. Dấu phẩy (,) và dấu chấm (.) đều dùng được cho số lẻ."
            )
        return (
            "Nhập số phút không âm, không cần gõ chữ phút. Ví dụ: 1–5 hoặc "
            "1,5–2. Dấu phẩy (,) và dấu chấm (.) đều dùng được cho số lẻ."
        )

    def _refresh_range_input_help(self):
        help_text = self._range_input_help()
        for widget in (self.txt_start, self.txt_end):
            widget.setToolTip(help_text)
        if self._range_input_unit == "seconds":
            self.txt_start.setPlaceholderText("Ví dụ: 60,5")
            self.txt_end.setPlaceholderText("Ví dụ: 70")
        else:
            self.txt_start.setPlaceholderText("Ví dụ: 1,5")
            self.txt_end.setPlaceholderText("Ví dụ: 5")

    def _clear_range_input_error(self, widget):
        widget.setStyleSheet("")
        if hasattr(self, "_range_input_unit"):
            widget.setToolTip(self._range_input_help())

    def _show_range_input_error(self, widget, message):
        help_text = f"{message}\n\nCách nhập đúng: {self._range_input_help()}"
        widget.setStyleSheet("border: 1px solid #ff5252;")
        widget.setToolTip(help_text)
        widget.setFocus()
        QToolTip.showText(
            widget.mapToGlobal(widget.rect().bottomLeft()),
            help_text,
            widget,
            widget.rect(),
            7000,
        )

    def _on_range_unit_changed(self):
        from core.subtitle_generation.range_time_input import (
            RangeInputError, parse_range_value_ms, format_range_value_ms,
        )
        old_unit = getattr(self, "_range_input_unit", "seconds")
        new_unit = self.cmb_range_unit.currentData()
        if new_unit == old_unit:
            self._refresh_range_input_help()
            return

        converted = []
        for widget in (self.txt_start, self.txt_end):
            raw = widget.text().strip()
            if not raw:
                converted.append((widget, ""))
                continue
            try:
                value_ms = parse_range_value_ms(raw, old_unit)
            except RangeInputError as exc:
                self.cmb_range_unit.blockSignals(True)
                self.cmb_range_unit.setCurrentIndex(
                    self.cmb_range_unit.findData(old_unit)
                )
                self.cmb_range_unit.blockSignals(False)
                self._show_range_input_error(
                    widget,
                    f"Không thể đổi đơn vị vì giá trị đang nhập chưa hợp lệ: {exc}",
                )
                return
            converted.append((widget, value_ms))

        self._range_input_unit = new_unit
        for widget, value in converted:
            widget.setText(
                "" if value == "" else format_range_value_ms(value, new_unit)
            )
        self._refresh_range_input_help()

    def set_range(self, start_ms: int, end_ms: int):
        from core.subtitle_generation.range_time_input import format_range_value_ms
        unit = getattr(self, "_range_input_unit", "seconds")
        self.txt_start.setText(format_range_value_ms(start_ms, unit))
        self.txt_end.setText(format_range_value_ms(end_ms, unit))

    def _on_preview_range_clicked(self):
        from ui.SubEditor import ms_to_time_str
        from core.subtitle_generation.range_time_input import (
            RangeInputError, parse_range_value_ms, format_range_value_ms,
        )
        from core.subtitle_generation.range_validation import RangeValidator, RangeErrorCode
        from ui.dialogs.preview_range_dialog import PreviewRangeDialog

        try:
            start_ms = parse_range_value_ms(
                self.txt_start.text(), self._range_input_unit
            )
        except RangeInputError as exc:
            self._show_range_input_error(
                self.txt_start, f"Thời điểm bắt đầu không hợp lệ: {exc}"
            )
            return
        try:
            end_ms = parse_range_value_ms(
                self.txt_end.text(), self._range_input_unit
            )
        except RangeInputError as exc:
            self._show_range_input_error(
                self.txt_end, f"Thời điểm kết thúc không hợp lệ: {exc}"
            )
            return

        self._clear_range_input_error(self.txt_start)
        self._clear_range_input_error(self.txt_end)
        if start_ms >= end_ms:
            self._show_range_input_error(
                self.txt_end,
                "Thời điểm kết thúc phải lớn hơn thời điểm bắt đầu.",
            )
            return

        # Call Validator
        result = RangeValidator.preview_range(
            start_ms, end_ms, self.video_duration_ms, 
            self._get_current_segments(), 
            self.generation_service.is_running
        )
        
        if not result.is_valid:
            if result.suggested_end_ms:
                # Keep the existing explicit clamp confirmation, but display the
                # proposed value in the currently selected input unit.
                from PySide6.QtWidgets import QMessageBox
                suggested = format_range_value_ms(
                    result.suggested_end_ms, self._range_input_unit
                )
                ans = QMessageBox.question(
                    self,
                    "Khoảng thời gian vượt video",
                    f"⚠ {result.message}\nBạn có muốn đưa thời điểm kết thúc về {suggested} {self._range_unit_label()}?",
                )
                if ans == QMessageBox.Yes:
                    self.txt_end.setText(suggested)
                    self._on_preview_range_clicked()  # Re-preview
                else:
                    self._show_range_input_error(
                        self.txt_end,
                        f"Thời điểm kết thúc vượt thời lượng video. Giá trị gợi ý: {suggested} {self._range_unit_label()}.",
                    )
            else:
                if result.status == RangeErrorCode.START_BEYOND_END:
                    if start_ms > self.video_duration_ms:
                        target = self.txt_start
                        message = "Thời điểm bắt đầu vượt quá thời lượng video. Hãy giảm giá trị bắt đầu."
                    else:
                        target = self.txt_end
                        message = "Thời điểm kết thúc phải lớn hơn thời điểm bắt đầu."
                elif result.status == RangeErrorCode.RANGE_TOO_SHORT:
                    target = self.txt_end
                    message = "Khoảng chọn quá ngắn. Hãy chọn khoảng dài hơn ít nhất 0,05 giây."
                elif result.status == RangeErrorCode.BEYOND_VIDEO_DURATION:
                    target = self.txt_end
                    message = "Thời điểm kết thúc vượt quá thời lượng video. Hãy nhập giá trị nhỏ hơn hoặc bằng thời lượng video."
                else:
                    target = self.txt_end
                    message = result.message
                self._show_range_input_error(target, message)
            return
            
        dialog = PreviewRangeDialog(ms_to_time_str(start_ms), ms_to_time_str(end_ms), result, self)
        if dialog.exec():
            # If accepted, trigger range generation
            strategy = dialog.selected_strategy
            # Call generation with strategy
            self._start_generation_with_strategy(start_ms, end_ms, strategy)

    def _start_generation_with_strategy(self, start_ms, end_ms, strategy):
        request = self._build_asr_request(start_ms, end_ms)
        if request is None:
            return
        self._set_ui_state_running()
        try:
            self.generation_service.start_generation(
                request,
                self.video_duration_ms,
                existing_segments=self._get_current_segments(),
                conflict_strategy=strategy
            )
        except Exception as exc:
            self._on_error(str(exc))
            self._set_ui_state_idle()
        self.refresh_history_ui()
            
    def _get_current_segments(self):
        # The panel lives inside MainWindow's overlay drawer; window() reaches it.
        sub_editor = getattr(self.window(), "sub_editor", None)
        return sub_editor.all_segments if sub_editor is not None else []
        
    def refresh_history(self):
        from PySide6.QtWidgets import QListWidgetItem
        from core.subtitle_generation.generation_checkpoint import GenerationCheckpoint
        
        self.history_list.clear()
        
        history = []
        if self.generation_service.initial_state:
            history.append(self.generation_service.initial_state)
        history.extend(self.generation_service.checkpoint_history)
        
        for cp in reversed(history): # Latest first
            label = f"{cp.checkpoint_type} - {cp.generated_count} subs"
            if cp.checkpoint_type == "INITIAL":
                label = "Initial State"
                
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, cp.checkpoint_id)
            self.history_list.addItem(item)
            
    def _on_history_selection_changed(self):
        self.btn_rollback.setEnabled(bool(self.history_list.selectedItems()))

    def _on_rollback_clicked(self):
        selected = self.history_list.selectedItems()
        if not selected:
            return
            
        cp_id = selected[0].data(Qt.UserRole)
        cp = self.generation_service.get_rollback_checkpoint(checkpoint_id=cp_id)
        if not cp:
            return
            
        current_segments = self._get_current_segments()
        has_manual = cp.has_manual_edits_compared_to(current_segments)
        
        from ui.dialogs.rollback_preview_dialog import RollbackPreviewDialog
        dialog = RollbackPreviewDialog(cp, has_manual, self)
        if dialog.exec():
            # Rollback goes through the undo manager, whose state_changed already
            # re-renders the editor and the timeline.
            undo_manager = getattr(self.window(), "undo_manager", None)
            if undo_manager is not None:
                self.generation_service.execute_rollback(
                    None, current_segments, undo_manager, checkpoint_id=cp_id
                )
                self.refresh_history()

    def _replace_editor_segments(self, segments):
        """Load segments into MainWindow's editor, timeline and draft."""
        win = self.window()
        sub_editor = getattr(win, "sub_editor", None)
        if sub_editor is None:
            return False
        sub_editor.all_segments.clear()
        sub_editor.all_segments.extend(segments)
        sub_editor.render_page()
        provider = getattr(win, "timeline_data_provider", None)
        if provider is not None:
            duration_ms = self.video_duration_ms or 3600000
            provider.load_runtime_data(sub_editor.all_segments, duration_ms)
            win.timeline_widget.load_project_data(duration_ms, provider.get_all_segments())
        sub_editor.save_draft(silent=True)
        self.refresh_history()
        return True
    # ----------------------------------------

    def sync_subtitle_sources_from_project(self):
        project_service = getattr(self.generation_service, "project_service", None)
        project = getattr(project_service, "current_project", None)
        if not project: return
        sources = getattr(project.state, "subtitle_sources", [])
        active_id = getattr(project.state, "active_subtitle_source_id", "default")
        
        self.cmb_subtitle_source.blockSignals(True)
        self.cmb_subtitle_source.clear()
        self.cmb_subtitle_source.addItem("Auto-detected SRT", "default")
        for src in sources:
            self.cmb_subtitle_source.addItem(src.get("name", "External SRT"), src.get("id"))
        
        idx = self.cmb_subtitle_source.findData(active_id)
        if idx >= 0:
            self.cmb_subtitle_source.setCurrentIndex(idx)
        self.cmb_subtitle_source.blockSignals(False)

    def _on_add_external_srt(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(self, "Ch?n file SRT...", "", "Subtitle Files (*.srt)")
        if not path: return
        
        import uuid
        import os
        from core.srt_parser import SrtParser
        
        try:
            segments = SrtParser.parse(path)
            if not segments:
                raise ValueError("File SRT tr?ng ho?c khng h?p l?.")
                
            source_id = f"ext_srt_{uuid.uuid4().hex[:8]}"
            project_service = getattr(self.generation_service, "project_service", None)
            project = getattr(project_service, "current_project", None)
            if not project: return
            
            new_source = {
                "id": source_id,
                "name": os.path.basename(path),
                "original_path": path,
            }
            if not hasattr(project.state, "subtitle_sources"):
                project.state.subtitle_sources = []
            project.state.subtitle_sources.append(new_source)
            project.state.active_subtitle_source_id = source_id
            if hasattr(project_service, "mark_dirty"):
                project_service.mark_dirty()
                
            self.sync_subtitle_sources_from_project()
            
            # Store initial checkpoint for new source
            self.generation_service.create_history_checkpoint(segments, is_initial=True)
            
            # Refresh UI
            self._replace_editor_segments(segments)
                
        except Exception as e:
            QMessageBox.critical(self, "L?i import", f"Khng th? d?c file SRT:\n{e}")
    def _on_subtitle_source_changed(self, idx):
        if idx < 0: return
        source_id = self.cmb_subtitle_source.itemData(idx)
        project_service = getattr(self.generation_service, "project_service", None)
        project = getattr(project_service, "current_project", None)
        if not project: return
        
        if getattr(project.state, "active_subtitle_source_id", "default") == source_id:
            return
            
        project.state.active_subtitle_source_id = source_id
        if hasattr(project_service, "mark_dirty"):
            project_service.mark_dirty()
            
        # Clear editor and reload from this source's latest checkpoint.
        history = self.generation_service.checkpoint_history
        cp = history[-1] if history else self.generation_service.initial_state
        import copy
        segments = copy.deepcopy(getattr(cp, "segments_snapshot", None) or [])
        self._replace_editor_segments(segments)
