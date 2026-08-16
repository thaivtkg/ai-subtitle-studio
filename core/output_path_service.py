import os

class OutputPathService:
    """
    Dịch vụ quản lý kiến trúc thư mục đầu ra.
    Mô hình:
    Output Root/
    ├── subtitles/
    └── hardsub/
    """
    
    @staticmethod
    def get_root_dir(configured_output_dir, video_path):
        """Xác định thư mục Root. Fallback về thư mục chứa video nếu chưa cấu hình."""
        if configured_output_dir and os.path.exists(configured_output_dir):
            return configured_output_dir
        return os.path.dirname(video_path)

    @classmethod
    def ensure_dir(cls, directory_path):
        """Đảm bảo thư mục tồn tại, nếu chưa có thì tạo mới."""
        os.makedirs(directory_path, exist_ok=True)
        return directory_path

    @classmethod
    def get_subtitle_dir(cls, configured_output_dir, video_path):
        root = cls.get_root_dir(configured_output_dir, video_path)
        sub_dir = os.path.join(root, "subtitles")
        return cls.ensure_dir(sub_dir)

    @classmethod
    def get_hardsub_dir(cls, configured_output_dir, video_path):
        root = cls.get_root_dir(configured_output_dir, video_path)
        hardsub_dir = os.path.join(root, "hardsub")
        return cls.ensure_dir(hardsub_dir)

    @classmethod
    def build_subtitle_path(cls, configured_output_dir, video_path, ext=".srt"):
        """Tạo đường dẫn file phụ đề an toàn."""
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        sub_dir = cls.get_subtitle_dir(configured_output_dir, video_path)
        path = os.path.join(sub_dir, f"{base_name}{ext}")
        return path.replace('\\', '/')

    @classmethod
    def build_hardsub_path(cls, configured_output_dir, video_path, ext=".mp4"):
        """Tạo đường dẫn file video hardsub an toàn."""
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        hardsub_dir = cls.get_hardsub_dir(configured_output_dir, video_path)
        # Bỏ tiền tố "hardsub_" vì file đã nằm trong thư mục "hardsub/" rồi
        path = os.path.join(hardsub_dir, f"{base_name}{ext}")
        return path.replace('\\', '/')