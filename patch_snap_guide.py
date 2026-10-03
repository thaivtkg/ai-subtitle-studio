import re

with open('ui/timeline/subtitle_track.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add the snap line rendering at the very end of paintEvent
paint_event_append = '''

        if getattr(self, "is_snapped", False) and getattr(self, "snap_line_x", None) is not None:
            painter.setPen(QPen(QColor(Theme.CYAN), 1))
            painter.drawLine(self.snap_line_x, 0, self.snap_line_x, self.height())
'''

# We can just append it before the end of the file, since paintEvent is the last method.
# But let's insert it before the end of the file.
content += paint_event_append

with open('ui/timeline/subtitle_track.py', 'w', encoding='utf-8') as f:
    f.write(content)
