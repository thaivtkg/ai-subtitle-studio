import os
from PySide6.QtCore import Signal

from PySide6.QtCore import QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.subtitle_controller import SubtitleController
from player.subtitle_overlay import SubtitleOverlay
from ui.animations.animation_config import SubtitleAnimationConfig
from ui.animations.animation_types import SubtitleRenderInput
from ui.animations.subtitle_animation_controller import SubtitleAnimationController


class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, video_item, overlay_proxy, parent=None):
        super().__init__(scene, parent)
        self.video_item = video_item
        self.overlay_proxy = overlay_proxy
        
        # Cấu hình render tối ưu, mượt mà
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Giữ nền Đen tuyền (#000000) để tạo dải viền vô cực (Cinematic)
        self.setStyleSheet("background-color: #000000; border-radius: 8px; border: none;")

        # [FIX] Khóa căn giữa tuyệt đối cho khung nhìn
        self.setAlignment(Qt.AlignCenter)

        # Tắt Aspect Ratio mặc định của Qt để tự tính toán thủ công (chống lệch sang phải)
        self.video_item.setAspectRatioMode(Qt.IgnoreAspectRatio)
        
        # Lắng nghe sự thay đổi khung hình thực tế của Video để cập nhật
        self.video_item.nativeSizeChanged.connect(self.update_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout()

    def update_layout(self, *args):
        """Tự động tính toán khung hình để video và subtitle luôn nằm chính giữa, không bị méo."""
        view_w = self.viewport().width()
        view_h = self.viewport().height()

        if view_w <= 0 or view_h <= 0:
            return

        # Ép không gian diễn họa (Scene) bằng đúng kích thước Viewport
        self.scene().setSceneRect(0, 0, view_w, view_h)

        native_size = self.video_item.nativeSize()
        
        if native_size.isValid() and native_size.width() > 0 and native_size.height() > 0:
            aspect = native_size.width() / native_size.height()
            target_w = view_w
            target_h = int(target_w / aspect)

            # Nếu chiều cao tính ra lớn hơn khung nhìn, scale ngược lại theo chiều cao
            if target_h > view_h:
                target_h = view_h
                target_w = int(target_h * aspect)

            # Tọa độ căn giữa
            pos_x = (view_w - target_w) / 2
            pos_y = (view_h - target_h) / 2

            self.video_item.setSize(QSizeF(target_w, target_h))
            self.video_item.setPos(pos_x, pos_y)
            
            # Overlay phụ đề phải đè khớp chính xác lên khung hình video
            self.overlay_proxy.setGeometry(QRectF(pos_x, pos_y, target_w, target_h))
        else:
            self.video_item.setSize(QSizeF(view_w, view_h))
            self.video_item.setPos(0, 0)
            self.overlay_proxy.setGeometry(QRectF(0, 0, view_w, view_h))


class VideoPlayerWidget(QWidget):
    timeline_position_changed = Signal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.anim_config = SubtitleAnimationConfig()
        self.anim_controller = SubtitleAnimationController(self.anim_config)
        
        # [FIX] Thêm biến theo dõi dòng đang được Highlight để tránh spam UI
        self._last_highlighted_stt = None 
        
        self.init_ui()
        self.init_player()

    def init_ui(self):
        # Layout chính của Player
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8) 

        # --- VŨ KHÍ TỐI THƯỢNG: QGRAPHICSVIEW ---
        self.scene = QGraphicsScene(self)

        # 1. Video Item (Nằm dưới cùng)
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)

        # 2. Subtitle Overlay (Lớp trên)
        self.subtitle_overlay = SubtitleOverlay(controller=self.anim_controller)
        self.subtitle_overlay.setStyleSheet("background: transparent;")

        self.overlay_proxy = self.scene.addWidget(self.subtitle_overlay)
        self.overlay_proxy.setZValue(1)  

        # 3. Tạo khung nhìn tổng
        self.view = CustomGraphicsView(self.scene, self.video_item, self.overlay_proxy)
        layout.addWidget(self.view, stretch=1)
        
        # =============================================================
        # EMPTY STATE (Placeholder khi chưa có video)
        # =============================================================
        view_layout = QVBoxLayout(self.view)
        
        self.empty_state_lbl = QLabel(
            "<div style='text-align: center;'>"
            "<span style='font-size: 38px;'>🎬</span><br><br>"
            "<span style='font-size: 14px; font-weight: bold; color: #F8FAFC;'>No video loaded</span><br><br>"
            "<span style='font-size: 12px; color: #64748B;'>Select a video from the Queue to start editing</span>"
            "</div>"
        )
        self.empty_state_lbl.setAlignment(Qt.AlignCenter)
        self.empty_state_lbl.setStyleSheet("background: transparent; border: none;")
        view_layout.addWidget(self.empty_state_lbl)

        # =============================================================
        # THANH ĐIỀU KHIỂN (MODERN CONTROL BAR)
        # =============================================================
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 4, 10, 8)
        controls_layout.setSpacing(12)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.setFixedSize(34, 34)
        self.btn_play.setStyleSheet("""
            QPushButton { 
                background: #1B263B; 
                border: none; 
                border-radius: 17px; 
            }
            QPushButton:hover { background: #273247; }
            QPushButton:pressed { background: #38BDF8; }
        """)
        self.btn_play.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.btn_play)    

        # Timeline Slider
        self.slider_seek = ClickableSlider(Qt.Horizontal)
        self.slider_seek.setRange(0, 0)
        self.slider_seek.setStyleSheet("""
            QSlider::groove:horizontal { 
                background: #172033; height: 4px; border-radius: 2px; 
            }
            QSlider::sub-page:horizontal { 
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #8B5CF6, stop: 1 #EC4899); 
                border-radius: 2px; 
            }
            QSlider::handle:horizontal { 
                background: #F8FAFC; width: 12px; margin: -4px 0; border-radius: 6px; 
            }
            QSlider::handle:horizontal:hover { background: #38BDF8; }
        """)
        self.slider_seek.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.slider_seek)

        # Label Thời gian
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 500;")
        controls_layout.addWidget(self.lbl_time)

        # Icon Loa
        self.lbl_vol_icon = QLabel("🔊")
        self.lbl_vol_icon.setStyleSheet("color: #94A3B8; font-size: 14px; margin-left: 8px; background: transparent; border: none;")
        controls_layout.addWidget(self.lbl_vol_icon)

        # Volume Slider
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.slider_volume.setMaximumWidth(70)
        self.slider_volume.setToolTip("Volume: 80%")
        self.slider_volume.setStyleSheet("""
            QSlider::groove:horizontal { background: #172033; height: 4px; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #38BDF8; border-radius: 2px; }
            QSlider::handle:horizontal { background: #F8FAFC; width: 10px; margin: -3px 0; border-radius: 5px; }
            QSlider::handle:horizontal:hover { background: #FFFFFF; }
        """)
        self.slider_volume.valueChanged.connect(self.set_volume)
        controls_layout.addWidget(self.slider_volume)

        layout.addLayout(controls_layout)

    def init_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_item)

        self.sub_controller = SubtitleController()
        self.player.positionChanged.connect(self.sub_controller.sync_position)
        
        # [FIX CRITICAL] Đã xóa bỏ kết nối subtitle_cleared tại đây.
        # Giao quyền quản lý hiển thị/ẩn hoàn toàn cho position_changed.

        self.audio_output.setVolume(0.8)

        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playingChanged.connect(self.update_play_button)

        self.update_play_button()

    def load_video(self, file_path):
        if os.path.exists(file_path):
            self.empty_state_lbl.hide()
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.pause()

    def toggle_playback(self):
        if self.player.isPlaying():
            self.player.pause()
        else:
            self.player.play()

    def get_current_time_ms(self):
        return self.player.position()

    def get_video_duration_ms(self):
        return self.player.duration()

    def update_play_button(self):
        if self.player.isPlaying():
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def position_changed(self, position):
        self.slider_seek.setValue(position)
        self.update_time_label()

        # [FIX BLOCKER] Đồng nhất tên cờ 'is_enabled' với SubtitleController
        is_preview_enabled = getattr(self.sub_controller, 'is_enabled', True)
        if not is_preview_enabled:
            self.subtitle_overlay.clear_subtitle()
            return

        # 1. LẤY DỮ LIỆU TRỰC TIẾP TỪ EDITOR BẢNG BÊN DƯỚI
        main_window = self.window()
        if hasattr(main_window, 'sub_editor') and hasattr(main_window.sub_editor, 'all_segments'):
            subs = main_window.sub_editor.all_segments
        else:
            subs = getattr(self.sub_controller, 'subs', []) or getattr(self.sub_controller, 'live_data', [])

        current_seg = None
        
        def parse_ms(val):
            if isinstance(val, (int, float)): return int(val)
            if isinstance(val, str):
                try:
                    val = val.replace(',', '.')
                    parts = val.split(':')
                    if len(parts) == 3:
                        return int(parts[0])*3600000 + int(parts[1])*60000 + int(float(parts[2])*1000)
                except Exception: pass
            return 0

        # 2. THUẬT TOÁN QUÉT CHÍNH XÁC TUYỆT ĐỐI
        for item in subs:
            try:
                if isinstance(item, tuple) and len(item) >= 4:
                    start_ms, end_ms, text, stt = item[0], item[1], item[2], item[3]
                elif isinstance(item, dict):
                    start_ms = item.get('start_ms') if 'start_ms' in item else parse_ms(item.get('start', 0))
                    end_ms = item.get('end_ms') if 'end_ms' in item else parse_ms(item.get('end', 0))
                    text = item.get('text', '')
                    stt = item.get('stt', 0)
                else: 
                    start_ms = item.start.ordinal
                    end_ms = item.end.ordinal
                    text = item.text
                    stt = item.index

                # [FIX BOUNDARY] Đồng nhất ranh giới [start_ms, end_ms)
                if start_ms <= position < end_ms:
                    # Bỏ qua những câu trống để không render lớp phủ vô nghĩa
                    if text and text != "[ Chưa có nội dung ]":
                        current_seg = {'stt': stt, 'start_ms': start_ms, 'end_ms': end_ms, 'text': text}
                    break
            except Exception:
                continue

        # 3. Đẩy lên Overlay để Render Animation và Đồng bộ Table Highlight
        if current_seg:
            stt_val = int(current_seg.get('stt', 0))
            render_input = SubtitleRenderInput(
                segment_id=stt_val,
                start_ms=int(current_seg.get('start_ms', 0)),
                end_ms=int(current_seg.get('end_ms', 0)),
                text=str(current_seg.get('text', ''))
            )
            
            visual_time = position
            if not self.player.isPlaying() and (visual_time - render_input.start_ms < 300):
                visual_time = render_input.start_ms + 300
                
            self.subtitle_overlay.update_subtitle(render_input, visual_time)

            # [FIX] Kích hoạt thanh Highlight của bảng Editor
            if self._last_highlighted_stt != stt_val:
                self._last_highlighted_stt = stt_val
                if hasattr(main_window, 'sub_editor'):
                    main_window.sub_editor.highlight_row_by_stt(stt_val)
        else:
            self.subtitle_overlay.clear_subtitle()
            
            # [FIX] Xóa Highlight khi kim thời gian rơi vào khoảng nghỉ (không có sub)
            if self._last_highlighted_stt is not None:
                self._last_highlighted_stt = None
                if hasattr(main_window, 'sub_editor'):
                    main_window.sub_editor.clear_highlight()
        self.timeline_position_changed.emit(position)

    def duration_changed(self, duration):
        self.slider_seek.setRange(0, duration)
        self.update_time_label()

    def set_position(self, position):
        self.player.setPosition(position)
        # [FIX] Ép đồng bộ giao diện phụ đề ngay lập tức nếu video đang Tạm dừng
        if not self.player.isPlaying():
            self.position_changed(position)

    def set_volume(self, volume):
        self.audio_output.setVolume(volume / 100.0)
        self.slider_volume.setToolTip(f"Volume: {volume}%")

    def update_time_label(self):
        pos_str = self.format_time(self.player.position())
        dur_str = self.format_time(self.player.duration())
        self.lbl_time.setText(f"{pos_str} / {dur_str}")

    def format_time(self, ms):
        s = ms // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def cleanup(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.empty_state_lbl.show()
        self.slider_seek.setValue(0)
        self.lbl_time.setText("00:00 / 00:00")
        
        # [FIX] Dọn dẹp "bóng ma" phụ đề kẹt trên màn hình
        if hasattr(self, 'subtitle_overlay') and self.subtitle_overlay:
            self.subtitle_overlay.clear_subtitle()
        if hasattr(self, 'sub_controller') and self.sub_controller:
            self.sub_controller.load_srt(None)


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)
