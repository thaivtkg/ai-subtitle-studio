import os
import re
import subprocess
import json
import torch
from datetime import timedelta
# from faster_whisper import WhisperModel

_cached_model = None
_cached_model_size = None

def format_time(seconds):
    """Chuyển đổi giây thành định dạng thời gian SRT (HH:MM:SS,mmm)"""
    td = timedelta(seconds=seconds)
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    secs = int(td.total_seconds() % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def is_garbage(text: str) -> bool:
    """Lọc rác nhưng vẫn giữ tiếng rên vừa phải"""
    text = text.strip()
    if not text:
        return True

    hard_garbage = {
        "次回予告", "ご視聴ありがとうございました", "よいしょ",
        "Teksting av Nicolai", "Winther", "me", "早送り"
    }
    if text in hard_garbage:
        return True

    # Cho phép tiếng rên, chỉ bỏ nếu quá dài
    if re.fullmatch(r"[あアあぁー～んっはぁふぅ…。.！!？?\s、]+", text):
        return len(text) > 28

    return False


def get_whisper_model(model_size, compute_type):
    global _cached_model, _cached_model_size
    import torch  
    from faster_whisper import WhisperModel  
    from core.runtime.runtime_paths import RuntimePaths
    from core.services.model_manager import ModelManager # <--- THÊM DÒNG NÀY

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu" and "float16" in compute_type:
        compute_type = "int8"

    if _cached_model is None or _cached_model_size != model_size:
        print(f"[AI] Đang nạp model {model_size} vào {device.upper()}...")
        
        # [S7.2-T14] Ép Model Manager quyết định đường dẫn tải
        safe_model_path = ModelManager.get_model_path_for_inference(model_size)
        models_dir = RuntimePaths.get_models_dir()
        if safe_model_path == model_size:
            models_dir = ModelManager.prepare_models_storage("load model")
        
        _cached_model = WhisperModel(
            safe_model_path, # <--- TRUYỀN ĐƯỜNG DẪN QUYẾT ĐỊNH VÀO ĐÂY
            device=device, 
            compute_type=compute_type,
            download_root=str(models_dir)
        )
        _cached_model_size = model_size
    return _cached_model





def _probe_video_resolution(video_path):
    from core.runtime.runtime_paths import RuntimePaths

    result = subprocess.run(
        [
            RuntimePaths.get_ffprobe_exe(), "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    streams = json.loads(result.stdout).get("streams", [])
    if not streams or not streams[0].get("width") or not streams[0].get("height"):
        raise ValueError("Không đọc được độ phân giải video để render hardsub.")
    return int(streams[0]["width"]), int(streams[0]["height"])


def _format_ass_timestamp(val) -> str:
    if isinstance(val, (int, float)):
        ms = int(val)
    else:
        from core.subtitle_quality.audio_energy_analyzer import AudioEnergyAnalyzer
        ms = AudioEnergyAnalyzer.parse_time_to_ms(val)
    total_cs = max(0, ms) // 10
    hours, remainder = divmod(total_cs, 360000)
    minutes, centiseconds = divmod(remainder, 6000)
    seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _build_multistyle_ass(segments, width, height, placement_state, global_style):
    from core import subtitle_ass
    from core.subtitle_quality.style_preset_resolver import StylePresetResolver

    global_s = dict(global_style or {})
    font_name = global_s.get("font_name", "Segoe UI")
    base_size = int(global_s.get("font_size", 20) or 20)
    outline_normal = float(global_s.get("outline_width", 2.0) or 2.0)

    loud_s = StylePresetResolver.resolve_style("loud", global_s)
    whisper_s = StylePresetResolver.resolve_style("whisper", global_s)

    def hex_to_ass_color(hex_str: str) -> str:
        hex_clean = str(hex_str).lstrip("#")
        if len(hex_clean) == 6:
            r, g, b = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6]
            return f"&H00{b}{g}{r}".upper()
        return "&H00FFFFFF"

    color_normal = hex_to_ass_color(global_s.get("font_color", "#FFFFFF"))
    color_loud = hex_to_ass_color(loud_s.get("font_color", "#FFE600"))
    color_whisper = hex_to_ass_color(whisper_s.get("font_color", "#D0D0D0"))

    loud_size = loud_s.get("font_size", int(round(base_size * 1.20)))
    whisper_size = whisper_s.get("font_size", int(round(base_size * 0.85)))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Style_Normal,{font_name},{base_size},{color_normal},{color_normal},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{outline_normal},0,5,10,10,10,1
Style: Style_Loud,{font_name},{loud_size},{color_loud},{color_loud},&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3.5,0,5,10,10,10,1
Style: Style_Whisper,{font_name},{whisper_size},{color_whisper},{color_whisper},&H00000000,&H00000000,0,-1,0,0,100,100,0,0,1,1.5,0,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogues = []
    x = getattr(placement_state, "x", 50.0) if placement_state else 50.0
    y = getattr(placement_state, "y", 85.0) if placement_state else 85.0

    for seg in segments:
        preset = (seg.get("style_preset") or "normal").lower().strip()
        if preset == "loud":
            style_name = "Style_Loud"
        elif preset == "whisper":
            style_name = "Style_Whisper"
        else:
            style_name = "Style_Normal"

        start_val = seg.get("start_ms") if seg.get("start_ms") is not None else seg.get("start", 0)
        end_val = seg.get("end_ms") if seg.get("end_ms") is not None else seg.get("end", 0)

        text = subtitle_ass.build_ass_dialogue(
            seg.get("text", ""),
            width,
            height,
            x,
            y,
        )
        dialogues.append(
            f"Dialogue: 0,{_format_ass_timestamp(start_val)},{_format_ass_timestamp(end_val)},{style_name},,0,0,0,,{text}"
        )

    return header + "\n".join(dialogues) + "\n"


def _build_positioned_ass(srt_path, width, height, placement_state, font_size, font_name):
    from core import subtitle_ass
    from core.export.subtitle_parser import parse_srt_content

    with open(srt_path, "r", encoding="utf-8", errors="ignore") as handle:
        segments = parse_srt_content(handle.read())

    def ass_time(milliseconds):
        total_cs = max(0, int(milliseconds)) // 10
        hours, remainder = divmod(total_cs, 360000)
        minutes, centiseconds = divmod(remainder, 6000)
        seconds, centiseconds = divmod(centiseconds, 100)
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(width=width, height=height, font_name=font_name, font_size=font_size)

    dialogues = []
    for segment in segments:
        text = subtitle_ass.build_ass_dialogue(
            segment.get("text", ""),
            width,
            height,
            placement_state.x,
            placement_state.y,
        )
        dialogues.append(
            f"Dialogue: 0,{ass_time(segment['start'])},{ass_time(segment['end'])},Default,,0,0,0,,{text}"
        )
    return header + "\n".join(dialogues) + "\n"


def burn_hardsub(video_path, srt_path, output_path, font_size=42, font_color="white", font_name="Arial", progress_callback=None, log_callback=None, process_callback=None, placement_state=None, video_resolution=None, segments=None, outline_width=2.0):
    base_name, _ = os.path.splitext(output_path)
    final_output_path = f"{base_name}.mp4"

    if log_callback:
        log_callback(f"[FFmpeg] Bắt đầu render hardsub cho: {os.path.basename(video_path)}")

    output_dir = os.path.dirname(final_output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    from core.runtime.runtime_paths import RuntimePaths
    ffmpeg_path = RuntimePaths.get_ffmpeg_exe()
    
    temp_ass = None
    subtitle_path = srt_path
    is_custom = getattr(placement_state, "mode", "bottom") == "custom"
    has_multistyle = bool(segments and any(s.get("style_preset") in ("loud", "whisper") for s in segments))

    if segments and (is_custom or has_multistyle):
        width, height = video_resolution or _probe_video_resolution(video_path)
        global_style = {
            "font_name": font_name,
            "font_size": font_size,
            "font_color": font_color,
            "outline_width": outline_width,
        }
        ass_content = _build_multistyle_ass(
            segments, width, height, placement_state, global_style
        )
        from core import subtitle_ass
        temp_ass = subtitle_ass.temporary_ass_file(ass_content)
        subtitle_path = temp_ass.path
    elif is_custom:
        width, height = video_resolution or _probe_video_resolution(video_path)
        ass_content = _build_positioned_ass(
            srt_path, width, height, placement_state, font_size, font_name
        )
        from core import subtitle_ass
        temp_ass = subtitle_ass.temporary_ass_file(ass_content)
        subtitle_path = temp_ass.path

    formatted_subtitle_path = subtitle_path.replace('\\', '/').replace(':', '\\:')
    formatted_subtitle_path = formatted_subtitle_path.replace("'", r"\'")

    use_temp_ass = (temp_ass is not None)
    cmd = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-vf", f"subtitles='{formatted_subtitle_path}'" if use_temp_ass else f"subtitles='{formatted_subtitle_path}':force_style='FontSize={font_size},FontName={font_name},PrimaryColour=&H00FFFFFF&'",
        "-c:a", "aac", 
        "-async", "1",
        "-ignore_unknown",
        final_output_path
    ]

    creation_flags = 0
    if os.name == 'nt':
        creation_flags = subprocess.CREATE_NO_WINDOW

    outcome = "failure"
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='ignore',
            creationflags=creation_flags
        )

        if process_callback:
            process_callback(process)

        try:
            for line in process.stdout:
                cleaned_line = line.strip()
                if cleaned_line:
                    if log_callback and any(k in cleaned_line for k in ["frame=", "time=", "size=", "bitrate=", "Stream #", "Error"]):
                        log_callback(f"[FFmpeg] {cleaned_line}")
        finally:
            if process.stdout:
                process.stdout.close()

            if process.poll() is None:
                try:
                    process.terminate()
                    process.kill()
                except Exception:
                    pass
            process.wait()

        if process.returncode not in (0, -9, -15):
            raise Exception(f"FFmpeg gặp lỗi khi render hardsub (Mã lỗi: {process.returncode})")
        outcome = "success" if process.returncode == 0 else "cancel"

        if log_callback:
            log_callback(f"[FFmpeg] Hoàn tất: {os.path.basename(final_output_path)}")

        if progress_callback:
            progress_callback(100, f"Hoàn tất chèn hardsub: {os.path.basename(final_output_path)}")
    finally:
        if temp_ass:
            temp_ass.finish(outcome)
