import os
import subprocess
import json

class VideoMetadataExtractor:
    @staticmethod
    def get_metadata(video_path):
        """
        Trích xuất thông tin video sử dụng ffprobe.
        Trả về dict chứa: size, duration_str, resolution, fps, audio_codec, format.
        """
        if not video_path or not os.path.exists(video_path):
            return VideoMetadataExtractor.get_empty_metadata()

        try:
            # Lệnh ffprobe lấy metadata định dạng JSON
            cmd = [
                "ffprobe", 
                "-v", "quiet", 
                "-print_format", "json", 
                "-show_format", 
                "-show_streams", 
                video_path
            ]
            
            # [Safety] Bắt timeout và ẩn cửa sổ cmd trên Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                    text=True, startupinfo=startupinfo, timeout=5)
            
            if result.returncode != 0:
                return VideoMetadataExtractor.get_empty_metadata()

            data = json.loads(result.stdout)
            return VideoMetadataExtractor._parse_ffprobe_data(video_path, data)

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, Exception) as e:
            # Ghi log lỗi ngầm, trả về data rỗng an toàn
            print(f"[Metadata Error] {e}")
            return VideoMetadataExtractor.get_empty_metadata()

    @staticmethod
    def _parse_ffprobe_data(file_path, data):
        # 1. File size
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_mb >= 1024:
            size_str = f"{size_mb / 1024:.2f} GB"
        else:
            size_str = f"{size_mb:.2f} MB"

        # 2. Format
        fmt = data.get("format", {})
        format_name = fmt.get("format_name", "Unknown").split(',')[0].upper()
        
        # 3. Duration
        duration_sec = float(fmt.get("duration", 0))
        h, rem = divmod(int(duration_sec), 3600)
        m, s = divmod(rem, 60)
        duration_str = f"{h:02d}:{m:02d}:{s:02d}"

        # 4. Stream Audio/Video Info
        resolution = "Unknown"
        fps = "Unknown"
        audio_codec = "Unknown"

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                w = stream.get("width", 0)
                h_res = stream.get("height", 0)
                if w and h_res:
                    resolution = f"{w} × {h_res}"
                
                # FPS (avg_frame_rate format is "num/den")
                fps_raw = stream.get("avg_frame_rate", "0/0")
                if '/' in fps_raw:
                    num, den = fps_raw.split('/')
                    if den != '0':
                        fps = f"{int(num) / int(den):.2f}"
            
            elif stream.get("codec_type") == "audio":
                audio_codec = stream.get("codec_name", "Unknown").upper()

        return {
            "size": size_str,
            "duration": duration_str,
            "resolution": resolution,
            "fps": fps,
            "audio": audio_codec,
            "format": format_name
        }

    @staticmethod
    def get_empty_metadata():
        return {
            "size": "--", "duration": "--:--:--", 
            "resolution": "--", "fps": "--", 
            "audio": "--", "format": "--"
        }