import pytest
from tests.uat.conftest import generate_fake_segments
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_editing.commands.restore_generation_command import RestoreGenerationCommand
from ui.SubEditor import SubtitleEditorWidget

def test_ui_sync_after_rollback_undo_redo(qapp, temp_project_dir, gen_service):
    """
    Test that the UI (Table, Current Subtitle, all_segments) stays fully synchronized
    after Rollback, Undo, and Redo.
    """
    undo_manager = GlobalUndoManager()
    sub_editor = SubtitleEditorWidget()
    sub_editor.undo_manager = undo_manager
    undo_manager.state_changed.connect(sub_editor.render_page)
    
    # Setup initial state (100 segments)
    segments_100 = generate_fake_segments(100)
    sub_editor.all_segments = segments_100
    sub_editor.render_page()
    
    # Assert initial UI
    assert sub_editor.table.rowCount() == 100
    # Simulate selection (since SelectionController is not instantiated in UAT)
    sub_editor.current_index = 20
    sub_editor._load_current_editor()
    
    # We expect text boxes to hold the values of segment 20
    seg_20 = segments_100[20]
    from ui.SubEditor import ms_to_time_str
    expected_start = ms_to_time_str(seg_20['start'])
    assert sub_editor.inp_start.text() == expected_start

    # State B (30 segments)
    segments_30 = generate_fake_segments(30)
    
    # Execute Rollback (push command)
    cmd = RestoreGenerationCommand(sub_editor.all_segments, segments_30, sub_editor.all_segments)
    undo_manager.push(cmd)
    qapp.processEvents()
    
    # Verification 1: After Rollback
    assert len(sub_editor.all_segments) == 30
    assert sub_editor.table.rowCount() == 30
    
    sub_editor.current_index = 20
    sub_editor._load_current_editor()
    
    # The current index was 20, it should still be 20 and show seg_20 from the new 30-segments array
    seg_20_new = segments_30[20]
    from ui.SubEditor import ms_to_time_str
    expected_start_new = ms_to_time_str(seg_20_new['start'])
    assert sub_editor.inp_start.text() == expected_start_new

    # Execute Undo
    undo_manager.undo()
    qapp.processEvents()
    
    # Verification 2: After Undo
    assert len(sub_editor.all_segments) == 100
    assert sub_editor.table.rowCount() == 100
    sub_editor.current_index = 20
    sub_editor._load_current_editor()
    assert sub_editor.inp_start.text() == expected_start

    # Execute Redo
    undo_manager.redo()
    qapp.processEvents()
    
    # Verification 3: After Redo
    assert len(sub_editor.all_segments) == 30
    assert sub_editor.table.rowCount() == 30
    sub_editor.current_index = 20
    sub_editor._load_current_editor()
    assert sub_editor.inp_start.text() == expected_start_new
