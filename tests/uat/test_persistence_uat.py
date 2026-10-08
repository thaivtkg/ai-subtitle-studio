import os
import json
import pytest
import subprocess
import sys
from tests.uat.conftest import MockProjectService, generate_fake_segments
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest

def test_persistence_reopen(temp_project_dir):
    """
    Test Phase 3: Checkpoint Persistence across Application Restart.
    """
    # Use a separate script to simulate the first process
    script_content = f'''
import sys
import os
sys.path.insert(0, r"{os.getcwd()}")
from tests.uat.conftest import MockProjectService, generate_fake_segments
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest

project_dir = r"{temp_project_dir}"
project_service = MockProjectService(project_dir)
service = SubtitleGenerationService(None, project_service)
service.current_request = SubtitleGenerationRequest(request_id="req_1", project_id="uat_proj_1", source_fingerprint="video_hash_1", video_path="video.mp4", model_size="base", compute_type="int8", language="en", use_vad=False, min_silence_ms=500, word_timestamps=False, batch_mode="time")

# Generate 100
service.create_history_checkpoint(generate_fake_segments(100), is_initial=True)
# Generate 60
service.create_history_checkpoint(generate_fake_segments(60))
# Generate 30
service.create_history_checkpoint(generate_fake_segments(30))

print("Created 3 checkpoints")
'''
    script_path = os.path.join(temp_project_dir, "process1.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
        
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    assert result.returncode == 0, f"Process 1 failed: {result.stderr}"
    
    # Process 2: We simulate reopening the project, doing a generation immediately BEFORE opening history
    project_service = MockProjectService(temp_project_dir)
    service = SubtitleGenerationService(None, project_service)
    service.current_request = SubtitleGenerationRequest(request_id="req_1", project_id="uat_proj_1", source_fingerprint="video_hash_1", video_path="video.mp4", model_size="base", compute_type="int8", language="en", use_vad=False, min_silence_ms=500, word_timestamps=False, batch_mode="time")
    
    # Crucially, DO NOT call load_history or _ensure_history_loaded explicitly here
    # The new batch should trigger it automatically via create_history_checkpoint
    service.create_history_checkpoint(generate_fake_segments(10))
    
    # Now verify the history is NOT just [10], but [60, 30, 10]
    service._ensure_history_loaded()
    assert service.initial_state is not None
    assert service.initial_state.generated_count == 100
    assert len(service.checkpoint_history) == 3
    assert service.checkpoint_history[0].generated_count == 60
    assert service.checkpoint_history[1].generated_count == 30
    assert service.checkpoint_history[2].generated_count == 10
