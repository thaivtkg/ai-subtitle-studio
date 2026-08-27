import json
import os
from core.runtime.runtime_paths import RuntimePaths

def load_settings():
    settings_file = RuntimePaths.get_settings_file()
    if not os.path.exists(settings_file):
        return {}
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(data):
    settings_file = RuntimePaths.get_settings_file()
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Lỗi lưu settings: {e}")