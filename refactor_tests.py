import os
import shutil

tests_dir = "tests"

mapping = {
    "test_media_import": "media_import",
    "test_recovery": "recovery",
    "test_tour": "tutorial",
    "test_ui_tutorial": "tutorial",
    "test_tutorial": "tutorial",
    "test_project": "project",
    "test_timeline": "timeline",
    "test_batch": "batch",
    "test_tm_": "database",
    "test_glossary": "database",
    "test_llm_service": "translation",
    "test_batch_translator": "translation",
    "test_agentic_prompt": "translation",
    "test_prompt_context": "translation",
    "test_auto_qc": "translation",
    "test_subtitle_generation": "subtitle_generation",
    "test_faster_whisper": "subtitle_generation",
    "test_export": "export",
    "test_ui": "ui",
    "test_theme": "ui"
}

for filename in os.listdir(tests_dir):
    if not filename.endswith(".py") or filename == "conftest.py" or filename == "__init__.py":
        continue
        
    source_path = os.path.join(tests_dir, filename)
    
    # Ignore if it's already a directory
    if os.path.isdir(source_path):
        continue
        
    target_subdir = "core" # Default fallback
    
    for prefix, subdir in mapping.items():
        if filename.startswith(prefix):
            target_subdir = subdir
            break
            
    # Also handle some specific ones
    if "export" in filename or "ass" in filename:
        target_subdir = "export"
    if "subtitle" in filename and target_subdir == "core" and "generation" not in filename:
        target_subdir = "core"
        
    target_path = os.path.join(tests_dir, target_subdir, filename)
    shutil.move(source_path, target_path)

print("Files moved successfully.")
