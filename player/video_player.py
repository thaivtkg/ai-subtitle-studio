import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QStyle, QSizePolicy
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


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

        # 1. Màn hình Video
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        layout.addWidget(self.video_widget)

        # 2. Thanh điều khiển (Control Bar)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(5, 5, 5, 5)

        # Nút Play/Pause (dùng icon mặc định của hệ thống)
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.setFixedSize(30, 30)
        self.btn_play.setStyleSheet("background: #2B3547; border: none; border-radius: 15px;")
        self.btn_play.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.btn_play)

        # Thanh cuộn thời gian (Seek Slider)
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

        # Thêm Icon Loa (🔊)
        self.lbl_vol_icon = QLabel("🔊")
        self.lbl_vol_icon.setStyleSheet("color: #98A2B3; font-size: 12px; margin-left: 10px;")
        controls_layout.addWidget(self.lbl_vol_icon)

        # Thanh cuộn âm lượng (Thêm Tooltip)
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
        # Khởi tạo Core Player và Audio Output (Bắt buộc trong Qt6)
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()

        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.audio_output.setVolume(0.8)  # Mặc định 80%

        # Kết nối các tín hiệu (Signals)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playingChanged.connect(self.update_play_button)

    def load_video(self, file_path):
        """ Gọi hàm này để nạp video mới vào Player """
        if os.path.exists(file_path):
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.pause()  # Load xong để đó, không tự động phát

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
        # Trong Qt6, Volume chạy từ 0.0 đến 1.0
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
        """ Dọn dẹp tài nguyên khi đóng ứng dụng """
        self.player.stop()
        self.player.setSource(QUrl())

class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Tính toán % vị trí chuột click trên tổng chiều rộng của slider
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(self.value()) # Phát tín hiệu bắt buộc Player nhảy tới
        super().mousePressEvent(event)