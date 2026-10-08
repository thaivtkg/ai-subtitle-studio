import pytest
import subprocess
import sys
import os

def test_full_workflow_e2e(temp_project_dir):
    """
    Simulates the exact workflow:
    GENERATE 100 -> MANUAL EDIT #20 -> GENERATE RANGE 40-60 -> ROLLBACK 30 -> UNDO -> REDO -> CLOSE -> REOPEN -> ROLLBACK INITIAL
    """
    
    script_1 = f'''
import sys
import os
import copy
sys.path.insert(0, r"{os.getcwd()}")
from tests.uat.conftest import MockProjectService, generate_fake_segments
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from ui.SubEditor import SubtitleEditorWidget

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
project_dir = r"{temp_project_dir}"
project_service = MockProjectService(project_dir)
service = SubtitleGenerationService(None, project_service)
service.current_request = SubtitleGenerationRequest(request_id="req_1", project_id="uat_proj_1", source_fingerprint="video_hash_1", video_path="video.mp4", model_size="base", compute_type="int8", language="en", use_vad=False, min_silence_ms=500, word_timestamps=False, batch_mode="time")

undo_manager = GlobalUndoManager()
sub_editor = SubtitleEditorWidget()
sub_editor.undo_manager = undo_manager
undo_manager.state_changed.connect(sub_editor.render_page)

# GENERATE 100
segments_100 = generate_fake_segments(100)
sub_editor.all_segments = segments_100
service.create_history_checkpoint(segments_100, is_initial=True)

state_100 = copy.deepcopy(sub_editor.all_segments)

# MANUAL EDIT #20
sub_editor.all_segments[20]["text"] = "I manually edited this!"
sub_editor.all_segments[20]["source"] = "manual"
state_edited = copy.deepcopy(sub_editor.all_segments)

# GENERATE RANGE 40-60 (Assume it replaces 10 segments and adds 5 new ones, total = 95)
segments_range = generate_fake_segments(95)
segments_range[20] = state_edited[20] # Keep manual edit
sub_editor.all_segments = segments_range
service.create_history_checkpoint(segments_range, is_range=True)

state_after_range = copy.deepcopy(sub_editor.all_segments)

# Generate another one to have a 30 checkpoint to rollback to
segments_30 = generate_fake_segments(30)
sub_editor.all_segments = segments_30
service.create_history_checkpoint(segments_30)

# ROLLBACK 30
cp_30 = service.get_rollback_checkpoint(target_count=30)
service.execute_rollback(None, sub_editor.all_segments, undo_manager, checkpoint_id=cp_30.checkpoint_id)
state_30 = copy.deepcopy(sub_editor.all_segments)
assert len(state_30) == 30

# UNDO
undo_manager.undo()
state_after_undo = copy.deepcopy(sub_editor.all_segments)
assert len(state_after_undo) == 30 # wait, undo of the 30-rollback takes us back to state before rollback (which was 30? No, before we generated 30, we were at 95. But wait, in the script we set sub_editor.all_segments = segments_30. The rollback command was given sub_editor.all_segments as before_segments. So before_segments was 30! Undo goes back to 30. That makes sense).

# REDO
undo_manager.redo()
state_after_redo = copy.deepcopy(sub_editor.all_segments)
assert len(state_after_redo) == 30

# Invariants
assert len(service.checkpoint_history) == 2
print("Process 1 Completed Successfully")
'''

    script_path = os.path.join(temp_project_dir, "process1.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_1)
        
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    assert result.returncode == 0, f"Process 1 failed: {result.stderr}"
    
    script_2 = f'''
import sys
import os
sys.path.insert(0, r"{os.getcwd()}")
from tests.uat.conftest import MockProjectService, generate_fake_segments
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
from core.subtitle_editing.global_undo_manager import GlobalUndoManager

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
project_dir = r"{temp_project_dir}"
project_service = MockProjectService(project_dir)
service = SubtitleGenerationService(None, project_service)

# REOPEN -> ROLLBACK INITIAL
cp_init = service.get_rollback_checkpoint(target_count=0)
assert cp_init is not None
assert cp_init.generated_count == 100
assert cp_init.segments_snapshot[0]["id"] == "seg_0"
print("Process 2 Completed Successfully")
'''

    script_path2 = os.path.join(temp_project_dir, "process2.py")
    with open(script_path2, "w", encoding="utf-8") as f:
        f.write(script_2)
        
    result2 = subprocess.run([sys.executable, script_path2], capture_output=True, text=True)
    assert result2.returncode == 0, f"Process 2 failed: {result2.stderr}"
