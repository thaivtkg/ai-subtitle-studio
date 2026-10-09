import pytest
import os
import uuid
import sys
import subprocess
from unittest.mock import MagicMock
from core.subtitle_generation.generation_service import SubtitleGenerationService
from tests.uat.conftest import MockProjectService, generate_fake_segments

def test_external_srt_workflow_lifecycle(temp_project_dir):
    # 1. Setup project
    project_service = MockProjectService(temp_project_dir)
    os.makedirs(os.path.join(temp_project_dir, "artifacts", "timing"), exist_ok=True)
    service = SubtitleGenerationService(None, project_service)
    
    # 2. Simulate Import External SRT
    source_id = f"ext_srt_{uuid.uuid4().hex[:8]}"
    project_service.current_project.state.active_subtitle_source_id = source_id
    project_service.current_project.state.subtitle_sources = [
        {"id": source_id, "name": "external.srt", "original_path": "/fake/path/external.srt"}
    ]
    
    # Generate 100 segments (simulating parse)
    segments = generate_fake_segments(100)
    service.create_history_checkpoint(segments, is_initial=True)
    
    assert service.initial_state is not None
    assert service.initial_state.source_id == source_id
    assert len(service.initial_state.segments_snapshot) == 100
    
    # 3. Simulate "Auto-fix" / "Generate Range" (new checkpoint)
    # Modify segments 10 to 20
    segments_modified = generate_fake_segments(100)
    for i in range(10, 20):
        segments_modified[i]["text"] = f"Range Generated {i}"
        
    service.create_history_checkpoint(
        segments_modified, 
        is_initial=False, 
        is_range=True
    )
    
    assert len(service.checkpoint_history) == 1
    assert service.checkpoint_history[0].source_id == source_id
    
    # 4. Check persistence (Reopen project in new process)
    normalized_proj_dir = temp_project_dir.replace('\\', '/')
    code = f"""
import sys
import os
sys.path.append('.')
from core.subtitle_generation.generation_service import SubtitleGenerationService
from tests.uat.conftest import MockProjectService

project_service = MockProjectService("{normalized_proj_dir}")
project_service.current_project.state.active_subtitle_source_id = "{source_id}"
project_service.current_project.state.subtitle_sources = [
    {{"id": "{source_id}", "name": "external.srt"}}
]

service = SubtitleGenerationService(None, project_service)
service._ensure_history_loaded()

assert service.initial_state is not None, "Initial state should persist for source"
assert service.initial_state.source_id == "{source_id}"
assert len(service.checkpoint_history) == 1, "Checkpoint history should have 1 item"
assert service.checkpoint_history[0].source_id == "{source_id}"
print("OK")
"""
    
    script_path = os.path.join(os.environ['TEMP'], "check_ext_srt.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code)
        
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    assert result.returncode == 0, f"Subprocess failed: {result.stderr}"
    assert "OK" in result.stdout
