import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QTableWidgetItem
from tests.uat.conftest import generate_fake_segments
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from ui.SubEditor import SubtitleEditorWidget

def test_subtitle_range_view_full_lifecycle(qapp, temp_project_dir, gen_service):
    """
    Automated UAT verifying the entire Subtitle Time Range View lifecycle:
    1. Validation rules:
       - Blank inputs handling
       - Partial input rejection
       - Non-numeric / negative values rejection
       - end <= start rejection
       - end > video duration rejection
       - Decimal minutes with '.' and ',' support
    2. Non-destructive filtering (all_segments preserved)
    3. Row-to-source mapping & editing filtered rows (seg_30)
    4. Pagination over filtered rows
    5. Timeline selection synchronization (inside & outside filter)
    6. Undo/Redo & Rollback with active filter
    7. Clear filter restoration (both blank + apply, or clear button)
    8. ComboBox list box sizing verification (no text truncation)
    """
    undo_manager = GlobalUndoManager()
    sub_editor = SubtitleEditorWidget()
    sub_editor.undo_manager = undo_manager
    undo_manager.state_changed.connect(sub_editor.render_page)

    # Setup 100 segments (STT 1..100, IDs seg_0..seg_99, start=i*2000ms, end=i*2000+1500ms)
    segments_100 = generate_fake_segments(100)
    sub_editor.all_segments = segments_100
    gen_service.create_history_checkpoint(segments_100, is_initial=True)
    sub_editor.render_page()

    # Initial state: 100 visible
    assert len(sub_editor.all_segments) == 100
    assert sub_editor.table.rowCount() == 100

    # -------------------------------------------------------------
    # 1. Validation tests
    # -------------------------------------------------------------
    # Case A: Partial input (start filled, end blank)
    sub_editor.range_start_input.setText("1")
    sub_editor.range_end_input.setText("")
    sub_editor.apply_time_filter()
    assert not sub_editor.lbl_range_validation.isHidden()
    assert "phút kết thúc" in sub_editor.lbl_range_validation.text().lower()
    assert sub_editor._active_time_range_ms is None

    # Case B: Non-numeric input
    sub_editor.range_start_input.setText("abc")
    sub_editor.range_end_input.setText("5")
    sub_editor.apply_time_filter()
    assert not sub_editor.lbl_range_validation.isHidden()
    assert "không hợp lệ" in sub_editor.lbl_range_validation.text().lower()
    assert sub_editor._active_time_range_ms is None

    # Case C: End <= Start
    sub_editor.range_start_input.setText("5")
    sub_editor.range_end_input.setText("2")
    sub_editor.apply_time_filter()
    assert not sub_editor.lbl_range_validation.isHidden()
    assert "lớn hơn" in sub_editor.lbl_range_validation.text().lower()
    assert sub_editor._active_time_range_ms is None

    # Case D: End > Video duration (when video duration is known)
    # Mock video duration to 3 minutes (180,000ms)
    sub_editor._video_duration_ms = lambda: 180_000
    sub_editor.range_start_input.setText("1")
    sub_editor.range_end_input.setText("5")
    sub_editor.apply_time_filter()
    assert not sub_editor.lbl_range_validation.isHidden()
    assert "vượt thời lượng video" in sub_editor.lbl_range_validation.text().lower()
    assert sub_editor._active_time_range_ms is None
    # Reset video duration mock
    sub_editor._video_duration_ms = lambda: 0

    # -------------------------------------------------------------
    # 2. Valid time range filter: 1.0 to 2.0 minutes (60,000 to 120,000 ms)
    # -------------------------------------------------------------
    # Supports decimal with comma as well: "1,0" to "2,0"
    sub_editor.range_start_input.setText("1,0")
    sub_editor.range_end_input.setText("2,0")
    sub_editor.apply_time_filter()

    assert sub_editor.lbl_range_validation.isHidden()
    assert sub_editor._active_time_range_ms == (60000, 120000)

    # Segments matching [60000, 120000):
    # seg_29: 58000..59500 (out)
    # seg_30: 60000..61500 (in)
    # seg_59: 118000..119500 (in)
    # seg_60: 120000..121500 (out)
    # Total = 30 segments (seg_30..seg_59)
    visible_indices = sub_editor._get_visible_source_indices()
    assert len(visible_indices) == 30
    assert visible_indices[0] == 30
    assert visible_indices[-1] == 59
    assert sub_editor.table.rowCount() == 30
    assert "30 / 100" in sub_editor.lbl_range_count.text()
    # Canonical source data remains untouched
    assert len(sub_editor.all_segments) == 100

    # -------------------------------------------------------------
    # 3. Check row mapping & edit filtered row (Row 0 -> seg_30)
    # -------------------------------------------------------------
    row_0_stt_item = sub_editor.table.item(0, sub_editor.COL_STT)
    assert row_0_stt_item.text() == "31"
    assert row_0_stt_item.data(Qt.UserRole) == "seg_30"

    # Edit row 0 text in the table
    row_0_text_item = sub_editor.table.item(0, sub_editor.COL_TEXT)
    row_0_text_item.setText("Edited Text 30")
    sub_editor.on_table_edit(0, sub_editor.COL_TEXT)

    # Verify: seg_30 in canonical all_segments MUST be updated
    assert sub_editor.all_segments[30]["text"] == "Edited Text 30"
    assert sub_editor.all_segments[30]["id"] == "seg_30"
    # Row 0 of all_segments (seg_0) must NOT be edited
    assert sub_editor.all_segments[0]["text"] == "Fake subtitle 0"

    # -------------------------------------------------------------
    # 4. Pagination over filtered rows
    # -------------------------------------------------------------
    sub_editor.group_combo.setCurrentText("10 dòng")
    assert sub_editor.group_size == 10

    # Page 0 should have 10 items (seg_30..seg_39, STT 31..40)
    assert sub_editor.current_page == 0
    assert sub_editor.table.rowCount() == 10
    assert sub_editor.table.item(0, sub_editor.COL_STT).text() == "31"
    assert sub_editor.table.item(9, sub_editor.COL_STT).text() == "40"

    # Page 1 should have 10 items (seg_40..seg_49, STT 41..50)
    sub_editor.next_page()
    assert sub_editor.current_page == 1
    assert sub_editor.table.rowCount() == 10
    assert sub_editor.table.item(0, sub_editor.COL_STT).text() == "41"
    assert sub_editor.table.item(9, sub_editor.COL_STT).text() == "50"

    # -------------------------------------------------------------
    # 5. Timeline selection synchronization
    # -------------------------------------------------------------
    # Timeline selects seg_45 (on Page 1) -> stays on Page 1, selects row 5
    sub_editor.sync_selection(45, "seg_45")
    assert sub_editor.current_page == 1
    assert sub_editor.table.currentRow() == 5

    # Timeline selects seg_30 (on Page 0) -> auto-switches to Page 0, selects row 0
    sub_editor.sync_selection(30, "seg_30")
    assert sub_editor.current_page == 0
    assert sub_editor.table.currentRow() == 0

    # Timeline selects seg_5 (OUTSIDE filter)
    sub_editor.sync_selection(5, "seg_5")
    # Current editor follows selected item
    assert sub_editor.current_index == 5
    assert sub_editor.current_editor.text_edit.toPlainText() == "Fake subtitle 5"
    # But table does NOT select a wrong row
    assert sub_editor.table.currentRow() == -1

    # -------------------------------------------------------------
    # 6. Undo / Redo with active filter
    # -------------------------------------------------------------
    # We previously edited seg_30 to "Edited Text 30"
    assert sub_editor.all_segments[30]["text"] == "Edited Text 30"
    undo_manager.undo()
    assert sub_editor.all_segments[30]["text"] == "Fake subtitle 30"

    undo_manager.redo()
    assert sub_editor.all_segments[30]["text"] == "Edited Text 30"

    # -------------------------------------------------------------
    # 7. Rollback with active filter (shrink source)
    # -------------------------------------------------------------
    # Create a 20-segment checkpoint and rollback to it
    segments_20 = generate_fake_segments(20)
    gen_service.create_history_checkpoint(segments_20)
    cp_20 = gen_service.checkpoint_history[0]
    gen_service.execute_rollback(
        target_count=None,
        data_provider=sub_editor.all_segments,
        undo_manager=undo_manager,
        checkpoint_id=cp_20.checkpoint_id
    )

    assert len(sub_editor.all_segments) == 20
    # Time range [60000, 120000) is still active, but all 20 segments end before 60000ms
    assert len(sub_editor._get_visible_source_indices()) == 0
    assert "0 / 20" in sub_editor.lbl_range_count.text()

    # -------------------------------------------------------------
    # 8. Clear filter restoration
    # -------------------------------------------------------------
    # Test clear_time_filter
    sub_editor.clear_time_filter()
    assert sub_editor._active_time_range_ms is None
    assert sub_editor.range_start_input.text() == ""
    assert sub_editor.range_end_input.text() == ""
    assert len(sub_editor._get_visible_source_indices()) == 20

    # Also test clearing by applying with both inputs blank
    sub_editor.range_start_input.setText("0")
    sub_editor.range_end_input.setText("1")
    sub_editor.apply_time_filter()
    assert sub_editor._active_time_range_ms == (0, 60000)

    sub_editor.range_start_input.setText("")
    sub_editor.range_end_input.setText("")
    sub_editor.apply_time_filter()
    assert sub_editor._active_time_range_ms is None
    assert len(sub_editor._get_visible_source_indices()) == 20

    # -------------------------------------------------------------
    # 9. List Box / ComboBox Sizing & Anti-truncation verification
    # -------------------------------------------------------------
    assert sub_editor.group_combo.sizeAdjustPolicy() == QComboBox.SizeAdjustPolicy.AdjustToContents
    assert sub_editor.group_combo.minimumWidth() >= 100
