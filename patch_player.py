import sys

with open('player/video_player.py', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

for i, line in enumerate(lines):
    if line.startswith('    def set_position(self, position):'):
        start_idx = i
        break

for i in range(start_idx, len(lines)):
    if line.startswith('    def set_volume'):
        end_idx = i
        break

# I will replace it using regex just in case
import re

content = '\n'.join(lines)

new_set_position = """    def set_position(self, position):
        self.player.setPosition(position)
        self.position_changed(position)
        # ÉP CẬP NHẬT LABEL NGAY LẬP TỨC ĐỂ HIỂN THỊ REALTIME KHI SCRUBBING
        self.update_time_label()

    def set_volume(self, volume):"""

content = re.sub(r'    def set_position\(self, position\):.*?    def set_volume\(self, volume\):', new_set_position, content, flags=re.DOTALL)

new_update_time = """    def update_time_label(self):
        position = self.player.position()
        bounds = getattr(self, "_segment_bounds", None)
        playback_active = getattr(self, "_segment_playback_active", False)
        
        # Chỉ hiển thị Local Time khi đang Focus
        if bounds:
            start_ms, end_ms = bounds
            
            # Tính thời gian tương đối
            local_position = max(0, position - start_ms)
            local_duration = max(0, end_ms - start_ms)
            
            # Đảm bảo local_position không vượt quá local_duration
            local_position = min(local_position, local_duration)
            
            pos_str = self.format_time(local_position)
            dur_str = self.format_time(local_duration)
            self.lbl_time.setText(f"{pos_str} / {dur_str}")
            from ui.theme import Theme
            self.lbl_time.setStyleSheet(f"color: {Theme.CYAN};")
        else:
            # Global Time
            pos_str = self.format_time(position)
            dur_str = self.format_time(self.player.duration())
            self.lbl_time.setText(f"{pos_str} / {dur_str}")
            self.lbl_time.setStyleSheet("")"""

content = re.sub(r'    def update_time_label\(self\):.*?(?=\n    def |$)', new_update_time, content, flags=re.DOTALL)

with open('player/video_player.py', 'w', encoding='utf-8') as f:
    f.write(content)
