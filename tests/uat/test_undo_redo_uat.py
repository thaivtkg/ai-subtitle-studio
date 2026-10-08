import pytest
from tests.uat.conftest import generate_fake_segments
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from ui.SubEditor import SubtitleEditorWidget

def test_undo_redo(qapp, temp_project_dir, gen_service):
    """
    Test Phase 2: Undo and Redo operations strictly restoring the correct snapshots.
    """
    undo_manager = GlobalUndoManager()
    sub_editor = SubtitleEditorWidget()
    sub_editor.undo_manager = undo_manager
    undo_manager.state_changed.connect(sub_editor.render_page)
    
    # State A = 100
    segments_100 = generate_fake_segments(100)
    sub_editor.all_segments = segments_100
    gen_service.create_history_checkpoint(segments_100, is_initial=True)
    
    # Generate down to State B = 30
    segments_30 = generate_fake_segments(30)
    gen_service.create_history_checkpoint(segments_30)
    
    # Use execute_rollback on the generation service to simulate the UI click
    cp_30 = gen_service.checkpoint_history[0]
    gen_service.execute_rollback(target_count=None, data_provider=sub_editor.all_segments, undo_manager=undo_manager, checkpoint_id=cp_30.checkpoint_id)
    
    # Verify state after rollback
    assert len(sub_editor.all_segments) == 30
    assert sub_editor.all_segments[0]["id"] == "seg_0"
    
    # UNDO -> should go back to State A (100)
    undo_manager.undo()
    assert len(sub_editor.all_segments) == 100
    # Deep Object-level verification
    assert sub_editor.all_segments[99]["id"] == "seg_99"
    assert sub_editor.all_segments[99]["text"] == "Fake subtitle 99"
    
    # REDO -> should go back to State B (30)
    undo_manager.redo()
    assert len(sub_editor.all_segments) == 30
    assert sub_editor.all_segments[-1]["id"] == "seg_29"
    assert sub_editor.all_segments[-1]["text"] == "Fake subtitle 29"
