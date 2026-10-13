import pytest
from PySide6.QtWidgets import QApplication
from ui.subtitle_generation_panel import SubtitleGenerationPanel
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_generation.range_time_input import (
    parse_range_value_ms, format_range_value_ms
)

def test_range_time_input_ui_lifecycle(qapp, gen_service):
    panel = SubtitleGenerationPanel(gen_service)
    panel.video_duration_ms = 600_000  # 10 minutes

    # 1. Initial State
    assert panel.cmb_range_unit.currentData() == "seconds"
    assert panel._range_input_unit == "seconds"

    # 2. Enter 60,5 and 70 seconds
    panel.txt_start.setText("60,5")
    panel.txt_end.setText("70")
    start_ms = parse_range_value_ms(panel.txt_start.text(), panel._range_input_unit)
    end_ms = parse_range_value_ms(panel.txt_end.text(), panel._range_input_unit)
    assert start_ms == 60_500
    assert end_ms == 70_000

    # 3. Switch unit to 'minutes' - should convert displayed text
    min_idx = panel.cmb_range_unit.findData("minutes")
    panel.cmb_range_unit.setCurrentIndex(min_idx)
    assert panel._range_input_unit == "minutes"
    # Milliseconds preserved
    assert parse_range_value_ms(panel.txt_start.text(), "minutes") == 60_500
    assert parse_range_value_ms(panel.txt_end.text(), "minutes") == 70_000

    # 4. In Minutes mode, enter 1,5 -> 5 (90s -> 300s)
    panel.txt_start.setText("1,5")
    panel.txt_end.setText("5")
    assert parse_range_value_ms(panel.txt_start.text(), "minutes") == 90_000
    assert parse_range_value_ms(panel.txt_end.text(), "minutes") == 300_000

    # Switch back to 'seconds'
    sec_idx = panel.cmb_range_unit.findData("seconds")
    panel.cmb_range_unit.setCurrentIndex(sec_idx)
    assert panel._range_input_unit == "seconds"
    assert panel.txt_start.text() == "90"
    assert panel.txt_end.text() == "300"

    # 5. set_range helper (e.g. from Timeline)
    panel.set_range(120_000, 240_000)
    assert panel.txt_start.text() == "120"
    assert panel.txt_end.text() == "240"

    panel.cmb_range_unit.setCurrentIndex(min_idx)
    panel.set_range(90_000, 150_000)
    assert panel.txt_start.text() == "1.5"
    assert panel.txt_end.text() == "2.5"

    # 6. Validation & Visual error highlighting
    # Case A: Empty start
    panel.txt_start.setText("")
    panel.txt_end.setText("5")
    panel._on_preview_range_clicked()
    assert "#ff5252" in panel.txt_start.styleSheet()

    # Case B: Typing clears error
    panel.txt_start.setText("1")
    assert panel.txt_start.styleSheet() == ""

    # Case C: Non-numeric
    panel.txt_start.setText("abc")
    panel._on_preview_range_clicked()
    assert "#ff5252" in panel.txt_start.styleSheet()

    # Case D: Start >= End (Start 5, End 2)
    panel.txt_start.setText("5")
    panel.txt_end.setText("2")
    panel._on_preview_range_clicked()
    assert "#ff5252" in panel.txt_end.styleSheet()
    assert "lớn hơn" in panel.txt_end.toolTip()
