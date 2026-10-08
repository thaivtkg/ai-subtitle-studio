import pytest
from tests.uat.conftest import generate_fake_segments
from core.subtitle_editing.global_undo_manager import GlobalUndoManager

def test_checkpoint_and_rollback(gen_service):
    """
    Test Phase 1: Checkpoint creation, Rollback matching, duplicate handling.
    """
    # 1. Create Checkpoints
    # Initial (100) -> 60 -> 50 -> 30 -> 10 -> 30 (duplicate count)
    
    # We will simulate consecutive generations by setting gen_service.create_history_checkpoint
    segments_initial = generate_fake_segments(100)
    gen_service.create_history_checkpoint(segments_initial, is_initial=True)
    
    segments_60 = generate_fake_segments(60)
    gen_service.create_history_checkpoint(segments_60)
    
    segments_50 = generate_fake_segments(50)
    gen_service.create_history_checkpoint(segments_50)
    
    segments_30_1 = generate_fake_segments(30)
    gen_service.create_history_checkpoint(segments_30_1)
    
    segments_10 = generate_fake_segments(10)
    gen_service.create_history_checkpoint(segments_10)
    
    # Duplicate count
    segments_30_2 = generate_fake_segments(30)
    segments_30_2[0]["text"] = "Duplicate 30"
    gen_service.create_history_checkpoint(segments_30_2)
    
    history = gen_service.checkpoint_history
    assert len(history) == 5 # 60, 50, 30, 10, 30_2 (initial is stored in initial_state)
    assert gen_service.initial_state is not None
    
    # Verify exact matches using target_count
    cp_60 = gen_service.get_rollback_checkpoint(target_count=60)
    assert cp_60 is not None
    assert cp_60.generated_count == 60
    assert len(cp_60.segments_snapshot) == 60
    
    # Verify Rollback to INITIAL
    cp_init = gen_service.get_rollback_checkpoint(target_count=0)
    assert cp_init == gen_service.initial_state
    
    # Verify ambiguity resolution (Duplicate 30).
    # Since we have two checkpoints with count 30, get_rollback_checkpoint by ID should resolve perfectly.
    id_1 = history[2].checkpoint_id # The first 30
    id_2 = history[4].checkpoint_id # The second 30
    
    cp_30_1 = gen_service.get_rollback_checkpoint(checkpoint_id=id_1)
    assert cp_30_1.segments_snapshot[0]["text"] != "Duplicate 30"
    
    cp_30_2 = gen_service.get_rollback_checkpoint(checkpoint_id=id_2)
    assert cp_30_2.segments_snapshot[0]["text"] == "Duplicate 30"
    
    # Checkpoint snapshot deepcopy invariant
    # Ensure mutating the passed-in array doesn't affect the snapshot
    segments_60[0]["text"] = "Mutated"
    assert cp_60.segments_snapshot[0]["text"] != "Mutated"
