import os
import json
import tempfile

def atomic_save_json(filepath: str, data: dict) -> None:
    """
    Lưu JSON nguyên tử (Atomic Save):
    1. Ghi dữ liệu vào một file tạm (Temporary File).
    2. Ép (Flush) dữ liệu từ RAM xuống vật lý (Ổ cứng).
    3. Đổi tên file tạm đè lên file gốc.
    Đảm bảo file gốc không bao giờ bị hỏng nếu crash giữa chừng.
    """
    dir_name = os.path.dirname(filepath)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    
    # Tạo file temp cùng thư mục để đảm bảo os.replace không bị lỗi cross-device link
    fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix="tmp_save_", suffix=".json")
    
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ép HĐH ghi chép vật lý xuống ổ đĩa
            
        # os.replace là hành động nguyên tử trên hầu hết các HĐH (Windows/Linux/macOS)
        os.replace(temp_path, filepath)
        
    except Exception as e:
        # Nếu có lỗi (VD: thiếu RAM, lỗi parse dict), xóa file temp rác và giữ nguyên file gốc
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e