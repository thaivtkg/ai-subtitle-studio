import sys
import os
import json

def resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối tới tài nguyên, tương thích với PyInstaller """
    try:
        # PyInstaller tạo ra một thư mục tạm và lưu đường dẫn trong _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Nếu đang chạy code Python bình thường, dùng thư mục hiện tại
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'AISubtitleStudio')
os.makedirs(app_data_dir, exist_ok=True)
SETTINGS_FILE = os.path.join(app_data_dir, "settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {} # Trả về dictionary rỗng nếu chưa có file hoặc lỗi

def save_settings(data):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Lỗi khi lưu settings: {e}")