import os
import re
import subprocess
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
        
        _cached_model = WhisperModel(
            safe_model_path, # <--- TRUYỀN ĐƯỜNG DẪN QUYẾT ĐỊNH VÀO ĐÂY
            device=device, 
            compute_type=compute_type,
            download_root=str(RuntimePaths.get_models_dir())
        )
        _cached_model_size = model_size
    return _cached_model

# =================================================================================
# FULL SUBTITLE GENERATOR (Chế độ Cũ: Trích xuất Đầy đủ Chữ + Thời gian)
# =================================================================================
def generate_srt(video_path, output_dir=None, initial_prompt=None, time_offset=0.0, 
                 model_size="large-v3", compute_type="float16", 
                 use_vad=True, min_silence_ms=500, progress_callback=None,
                 cancel_check=None, video_duration=0.0):
    from faster_whisper import WhisperModel  
    model = get_whisper_model(model_size, compute_type)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Not found: {video_path}")

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    
    if progress_callback:
        progress_callback(10, f"Đang khởi tạo mô hình Faster-Whisper ({model_size}) trên GPU...")

    if progress_callback:
        progress_callback(25, f"Bắt đầu nhận diện âm thanh (VAD: {'Bật' if use_vad else 'Tắt'})... Vui lòng đợi...")

    transcribe_kwargs = {
        "beam_size": 5,
        "word_timestamps": True,
        "vad_filter": use_vad,
        "condition_on_previous_text": False,
        "repetition_penalty": 1.25,
        "no_speech_threshold": 0.6,
        "temperature": 0.0,
    }
    
    if use_vad:
        transcribe_kwargs["vad_parameters"] = dict(
            min_silence_duration_ms=min_silence_ms,
            max_speech_duration_s=10.0,      
            speech_pad_ms=200
        )

    if initial_prompt and initial_prompt.strip():
        transcribe_kwargs["initial_prompt"] = initial_prompt.strip()
    else:
        transcribe_kwargs["initial_prompt"] = (
            "これは日本の特撮・アダルト作品です。"
            "明確なセリフのみを正確に書き起こしてください。"
            "喘ぎ声は適度に残してください。"
        )

    segments, info = model.transcribe(video_path, **transcribe_kwargs)

    detected_lang = info.language
    audio_duration = getattr(info, 'duration', 0.0) or video_duration

    if output_dir and os.path.exists(output_dir):
        output_srt_path = os.path.join(output_dir, f"{base_name}_{detected_lang}.srt")
    else:
        dir_name = os.path.dirname(video_path)
        output_srt_path = os.path.join(dir_name, f"{base_name}_{detected_lang}.srt")

    if progress_callback:
        progress_callback(40, f"Phát hiện ngôn ngữ: [{detected_lang}]. Đang tiến hành trích xuất phụ đề chi tiết...")

    srt_content = []
    srt_index = 1
    prev_text = ""

    if use_vad:
        MAX_WORDS_PER_SUB = 14
        MAX_DURATION_PER_SUB = 6.5
    else:
        MAX_WORDS_PER_SUB = 18
        MAX_DURATION_PER_SUB = 8.0

    for segment in segments:
        if cancel_check and cancel_check():
            raise InterruptedError("Tiến trình tạo Subtitle đã bị hủy.")

        if segment.words:
            current_chunk = []
            
            for word in segment.words:
                current_chunk.append(word)
                chunk_duration = current_chunk[-1].end - current_chunk[0].start
                last_word = word.word.strip()

                should_cut = (
                    len(current_chunk) >= MAX_WORDS_PER_SUB or 
                    chunk_duration >= MAX_DURATION_PER_SUB or
                    last_word in ("。", "！", "？", "…", "」")
                )

                if should_cut:
                    sub_text = "".join([w.word for w in current_chunk]).strip()
                    if sub_text and not is_garbage(sub_text) and sub_text != prev_text:
                        start_sec = max(0.0, current_chunk[0].start + time_offset)
                        end_sec = max(0.0, current_chunk[-1].end + time_offset)
                        
                        srt_block = f"{srt_index}\n{format_time(start_sec)} --> {format_time(end_sec)}\n{sub_text}\n\n"
                        srt_content.append(srt_block)
                        srt_index += 1
                        prev_text = sub_text
                    current_chunk = []

            if current_chunk:
                sub_text = "".join([w.word for w in current_chunk]).strip()
                if sub_text and not is_garbage(sub_text) and sub_text != prev_text:
                    start_sec = max(0.0, current_chunk[0].start + time_offset)
                    end_sec = max(0.0, current_chunk[-1].end + time_offset)
                    
                    srt_block = f"{srt_index}\n{format_time(start_sec)} --> {format_time(end_sec)}\n{sub_text}\n\n"
                    srt_content.append(srt_block)
                    srt_index += 1
                    prev_text = sub_text

        else:
            text = segment.text.strip()
            if text and not is_garbage(text) and text != prev_text:
                start_sec = max(0.0, segment.start + time_offset)
                end_sec = max(0.0, segment.end + time_offset)
                srt_block = f"{srt_index}\n{format_time(start_sec)} --> {format_time(end_sec)}\n{text}\n\n"
                srt_content.append(srt_block)
                srt_index += 1
                prev_text = text

        if progress_callback and audio_duration > 0:
            percent_done = min(100.0, (segment.end / audio_duration) * 100.0)
            ai_progress = min(99, 40 + int(0.59 * percent_done))
            progress_callback(ai_progress, f"[{format_time(segment.start)}] {segment.text.strip()[:50]}")

    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.writelines(srt_content)

    if progress_callback:
        progress_callback(100, f"Đã hoàn tất xuất file SRT tại: {output_srt_path}")

    return output_srt_path


# =================================================================================
# TIMING DRAFT GENERATOR (P2-T2: Trích xuất độc lập Khung thời gian rỗng)
# =================================================================================
def generate_timing_draft(video_path, output_dir=None, time_offset=0.0, 
                 model_size="large-v3-turbo", compute_type="float16", 
                 use_vad=True, min_silence_ms=500, progress_callback=None,
                 cancel_check=None, video_duration=0.0):
    """
    Sản xuất Artifact Timing: Tối ưu hóa cực độ tốc độ và VRAM bằng Greedy Search (beam_size=1) 
    và bỏ qua Căn chỉnh từng từ (word_timestamps=False).
    """
    from faster_whisper import WhisperModel  
    model = get_whisper_model(model_size, compute_type)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Not found: {video_path}")

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    
    if progress_callback:
        progress_callback(10, f"Đang khởi tạo Engine cho Timing Draft...")

    # [OPTIMIZATION] Cấu hình ép xung: Tốc độ tối đa, bỏ qua độ chính xác Text
    transcribe_kwargs = {
        "beam_size": 1,              # Greedy decoding: Tiết kiệm tối đa VRAM và Tính toán
        "word_timestamps": False,    # Chỉ lấy thời gian cả câu, bỏ bóc tách từng chữ
        "vad_filter": use_vad,
        "condition_on_previous_text": False,
        "temperature": 0.0,
    }
    
    if use_vad:
        transcribe_kwargs["vad_parameters"] = dict(
            min_silence_duration_ms=min_silence_ms,
            max_speech_duration_s=10.0,      
            speech_pad_ms=200
        )

    segments, info = model.transcribe(video_path, **transcribe_kwargs)
    audio_duration = getattr(info, 'duration', 0.0) or video_duration

    # Đặt tên file phân biệt rõ Artifact
    if output_dir and os.path.exists(output_dir):
        output_srt_path = os.path.join(output_dir, f"{base_name}_timing.srt")
    else:
        dir_name = os.path.dirname(video_path)
        output_srt_path = os.path.join(dir_name, f"{base_name}_timing.srt")

    srt_content = []
    srt_index = 1

    for segment in segments:
        if cancel_check and cancel_check():
            raise InterruptedError("Tiến trình tạo Timing Draft đã bị hủy.")

        start_sec = max(0.0, segment.start + time_offset)
        end_sec = max(0.0, segment.end + time_offset)
        
        # [CORE] Xuất cấu trúc Artifact Rỗng Text (Empty Text)
        srt_block = f"{srt_index}\n{format_time(start_sec)} --> {format_time(end_sec)}\n\n"
        srt_content.append(srt_block)
        srt_index += 1

        if progress_callback and audio_duration > 0:
            percent_done = min(100.0, (segment.end / audio_duration) * 100.0)
            ai_progress = min(99, 10 + int(0.89 * percent_done))
            progress_callback(ai_progress, f"Đang dò tìm Timestamp: [{format_time(segment.start)} -> {format_time(segment.end)}]")

    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.writelines(srt_content)

    if progress_callback:
        progress_callback(100, f"Đã hoàn tất xuất file Timing Draft tại: {output_srt_path}")

    return output_srt_path


def burn_hardsub(video_path, srt_path, output_path, font_size=42, font_color="white", font_name="Arial", progress_callback=None, log_callback=None, process_callback=None):
    base_name, _ = os.path.splitext(output_path)
    final_output_path = f"{base_name}.mp4"

    if log_callback:
        log_callback(f"[FFmpeg] Bắt đầu render hardsub cho: {os.path.basename(video_path)}")

    output_dir = os.path.dirname(final_output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    from core.runtime.runtime_paths import RuntimePaths
    ffmpeg_path = RuntimePaths.get_ffmpeg_exe()
    
    formatted_srt_path = srt_path.replace('\\', '/').replace(':', '\\:')
    formatted_srt_path = formatted_srt_path.replace("'", r"\'")

    cmd = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-vf", f"subtitles='{formatted_srt_path}':force_style='FontSize={font_size},FontName={font_name},PrimaryColour=&H00FFFFFF&'",
        "-c:a", "aac", 
        "-async", "1",
        "-ignore_unknown",
        final_output_path
    ]

    creation_flags = 0
    if os.name == 'nt':
        creation_flags = subprocess.CREATE_NO_WINDOW

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
    
    if process.returncode != 0 and process.returncode != -9 and process.returncode != -15:
        raise Exception(f"FFmpeg gặp lỗi khi render hardsub (Mã lỗi: {process.returncode})")

    if log_callback:
        log_callback(f"[FFmpeg] Hoàn tất: {os.path.basename(final_output_path)}")

    if progress_callback:
        progress_callback(100, f"Hoàn tất chèn hardsub: {os.path.basename(final_output_path)}")
