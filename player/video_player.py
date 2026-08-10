import os

from PySide6.QtCore import QRectF, Qt, QUrl
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
        self.setStyleSheet("background-color: #000000; border-radius: 6px; border: none;")

        # [Safety] Lắng nghe sự thay đổi khung hình thực tế của Video để cập nhật Overlay
        self.video_item.nativeSizeChanged.connect(self.update_overlay_geometry)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.video_item.setSize(QRectF(self.viewport().rect()).size())
        self.update_overlay_geometry()

    def update_overlay_geometry(self, *args):
        view_rect = self.viewport().rect()
        
        # [Safety Check] Chặn chia cho 0 nếu Viewport chưa kịp render
        if view_rect.height() == 0: 
            return

        native_size = self.video_item.nativeSize()
        
        # Kiểm tra kích thước video thực tế hợp lệ
        if native_size.isValid() and native_size.width() > 0 and native_size.height() > 0:
            view_ratio = view_rect.width() / view_rect.height()
            video_ratio = native_size.width() / native_size.height()
            
            if video_ratio > view_ratio:
                # Video rộng hơn View -> Xuất hiện viền đen Letterbox (trên/dưới)
                w = view_rect.width()
                h = w / video_ratio
                x = 0
                y = (view_rect.height() - h) / 2
            else:
                # Video hẹp hơn View -> Xuất hiện viền đen Pillarbox (trái/phải - như trong ảnh)
                h = view_rect.height()
                w = h * video_ratio
                x = (view_rect.width() - w) / 2
                y = 0
            
            # Ép Overlay nằm khít với pixels của video
            self.overlay_proxy.setGeometry(QRectF(x, y, w, h))
        else:
            self.overlay_proxy.setGeometry(QRectF(view_rect))


class VideoPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.init_player()

    def init_ui(self):
        # Layout chính của Player
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # --- VŨ KHÍ TỐI THƯỢNG: QGRAPHICSVIEW ---
        self.scene = QGraphicsScene(self)

        # 1. Video Item (Nằm dưới cùng)
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)

        # 2. Subtitle Overlay (Lớp trên)
        self.subtitle_overlay = SubtitleOverlay()
        # Đảm bảo nền Overlay phải trong suốt
        self.subtitle_overlay.setStyleSheet("background: transparent;")

        self.overlay_proxy = self.scene.addWidget(self.subtitle_overlay)
        self.overlay_proxy.setZValue(1)  # Lệnh hoàng gia: Bắt buộc đè lên Video!

        # 3. Tạo khung nhìn tổng
        self.view = CustomGraphicsView(self.scene, self.video_item, self.overlay_proxy)
        layout.addWidget(self.view)
        # ----------------------------------------

        # Thanh điều khiển (Control Bar)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(5, 5, 5, 5)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.setFixedSize(30, 30)
        self.btn_play.setStyleSheet("background: #2B3547; border: none; border-radius: 15px;")
        self.btn_play.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.btn_play)

        self.slider_seek = ClickableSlider(Qt.Horizontal)
        self.slider_seek.setRange(0, 0)
        self.slider_seek.setStyleSheet("""
            QSlider::groove:horizontal { background: #273247; height: 6px; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #35C8FF; border-radius: 3px; }
            QSlider::handle:horizontal { background: #FFF; width: 12px; margin: -3px 0; border-radius: 6px; }
        """)
        self.slider_seek.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.slider_seek)

        self.lbl_time = QLabel("00:00 / --:--")
        self.lbl_time.setStyleSheet("color: #98A2B3; font-size: 11px; font-family: Consolas;")
        controls_layout.addWidget(self.lbl_time)

        self.lbl_vol_icon = QLabel("🔊")
        self.lbl_vol_icon.setStyleSheet("color: #98A2B3; font-size: 12px; margin-left: 10px;")
        controls_layout.addWidget(self.lbl_vol_icon)

        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.slider_volume.setMaximumWidth(80)
        self.slider_volume.setToolTip("Volume: 80%")
        self.slider_volume.setStyleSheet("""
            QSlider::groove:horizontal { background: #273247; height: 4px; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #7B61FF; border-radius: 2px; }
            QSlider::handle:horizontal { background: #FFF; width: 10px; margin: -3px 0; border-radius: 5px; }
        """)
        self.slider_volume.valueChanged.connect(self.set_volume)
        controls_layout.addWidget(self.slider_volume)

        layout.addLayout(controls_layout)

    def init_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # --- BƠM TRỰC TIẾP VIDEO VÀO GRAPHICS ITEM ---
        self.player.setVideoOutput(self.video_item)

        # Nối hệ thống Subtitle Controller
        self.sub_controller = SubtitleController()
        self.player.positionChanged.connect(self.sub_controller.sync_position)
        self.sub_controller.subtitle_changed.connect(lambda stt, start, text: self.subtitle_overlay.set_subtitle(text))
        self.sub_controller.subtitle_cleared.connect(self.subtitle_overlay.clear_subtitle)

        self.audio_output.setVolume(0.8)

        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playingChanged.connect(self.update_play_button)

    def load_video(self, file_path):
        if os.path.exists(file_path):
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.pause()

    def toggle_playback(self):
        if self.player.isPlaying():
            self.player.pause()
        else:
            self.player.play()

    def update_play_button(self):
        if self.player.isPlaying():
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def position_changed(self, position):
        self.slider_seek.setValue(position)
        self.update_time_label()

    def duration_changed(self, duration):
        self.slider_seek.setRange(0, duration)
        self.update_time_label()

    def set_position(self, position):
        self.player.setPosition(position)

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


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)