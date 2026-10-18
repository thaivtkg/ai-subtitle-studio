import re
from typing import List, Optional, Dict, Any, Tuple
import numpy as np


class AudioEnergyAnalyzer:
    """
    Phân tích năng lượng âm thanh từ mảng đỉnh sóng (peaks) của WaveformService
    để tự động phân loại Style Preset (Loud, Whisper, Normal) cho từng dòng phụ đề.
    """

    @staticmethod
    def parse_time_to_ms(val: Any) -> int:
        """Chuyển đổi mili-giây dạng số hoặc chuỗi thời gian SRT/VTT (HH:MM:SS,mmm) thành ms."""
        if val is None:
            return 0
        if isinstance(val, float):
            return int(round(val * 1000)) if val < 100000 else int(round(val))
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            val = val.strip()
            # Match 00:00:01,000 or 00:00:01.000 or 00:01.000
            m = re.match(r"^(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{3})$", val)
            if m:
                h, mi, s, ms = m.groups()
                h_val = int(h) if h is not None else 0
                return h_val * 3600000 + int(mi) * 60000 + int(s) * 1000 + int(ms)
            # Fallback numeric string (seconds or ms)
            try:
                f = float(val)
                if "." in val and f < 100000:
                    return int(round(f * 1000))
                return int(round(f))
            except ValueError:
                return 0
        return 0

    @staticmethod
    def get_peaks_data(video_path: str) -> np.ndarray:
        """Tái sử dụng cache từ WaveformService hoặc trích xuất đồng bộ nếu chưa có."""
        from core.waveform.waveform_service import WaveformService
        return WaveformService.generate_waveform_peaks(video_path)

    @staticmethod
    def compute_segment_energy(peaks: np.ndarray, start_ms: int, end_ms: int) -> float:
        """
        Tính năng lượng trung bình cắt tỉa (Trimmed Mean) cho khoảng thời gian [start_ms, end_ms].
        Bỏ 10% đỉnh cao nhất khi số frame K >= 10 để chống nhiễu click/pop ngắn hạn.
        """
        if peaks is None or len(peaks) == 0:
            return 0.0

        idx_start = max(0, int(start_ms / 10))
        idx_end = min(len(peaks), int(end_ms / 10))
        if idx_start >= idx_end:
            return 0.0

        slice_peaks = peaks[idx_start:idx_end]
        if len(slice_peaks) == 0:
            return 0.0

        if slice_peaks.ndim == 2:
            slice_a = (slice_peaks[:, 1] - slice_peaks[:, 0]) / 2.0
        else:
            slice_a = np.abs(slice_peaks)

        k = len(slice_a)
        if k >= 10:
            cutoff = int(np.floor(0.9 * k))
            sorted_a = np.sort(slice_a)
            return float(np.mean(sorted_a[:cutoff]))
        return float(np.mean(slice_a))

    @classmethod
    def analyze_segments(
        cls,
        peaks: np.ndarray,
        segments: List[Dict[str, Any]],
        target_indices: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Phân loại toàn bộ hoặc nhóm phụ đề mục tiêu theo phân vị năng lượng âm thanh.
        Tự động bảo vệ video dải động hẹp (Monotone/ASMR) và làm mịn bất biến.
        """
        if not segments:
            return segments

        n = len(segments)
        seg_times: List[Tuple[int, int]] = []
        for s in segments:
            s_ms = s.get("start_ms")
            if s_ms is None:
                s_ms = cls.parse_time_to_ms(s.get("start"))
            else:
                s_ms = int(s_ms)

            e_ms = s.get("end_ms")
            if e_ms is None:
                e_ms = cls.parse_time_to_ms(s.get("end"))
            else:
                e_ms = int(e_ms)
            seg_times.append((s_ms, e_ms))

        # 1. Tính toán năng lượng cho toàn bộ video (Baseline đồng nhất)
        energies = np.array(
            [cls.compute_segment_energy(peaks, st, et) for st, et in seg_times],
            dtype=np.float32,
        )

        std_dev = float(np.std(energies))
        median_val = float(np.median(energies))

        provisional_presets: List[str] = ["normal"] * n

        # 2. Kiểm tra Flat Audio Trap (Dải động hẹp)
        if std_dev < 0.04 or (std_dev / (median_val + 1e-6)) < 0.15:
            # Video giọng đều / monotone -> 100% normal
            provisional_presets = ["normal"] * n
        else:
            p85 = float(np.percentile(energies, 85))
            p15 = float(np.percentile(energies, 15))
            thresh_loud = max(p85, 1.30 * median_val)
            thresh_whisper = min(p15, 0.75 * median_val)

            for i in range(n):
                e = energies[i]
                if e >= thresh_loud:
                    provisional_presets[i] = "loud"
                elif e <= thresh_whisper:
                    provisional_presets[i] = "whisper"
                else:
                    provisional_presets[i] = "normal"

        # 3. Làm mịn bất biến (Smoothing qua snapshot copy để chống domino cascade)
        original_presets = list(provisional_presets)
        for i in range(1, n - 1):
            dur = seg_times[i][1] - seg_times[i][0]
            gap_prev = seg_times[i][0] - seg_times[i - 1][1]
            gap_next = seg_times[i + 1][0] - seg_times[i][1]

            if dur < 800 and gap_prev <= 500 and gap_next <= 500:
                prev_p = original_presets[i - 1]
                next_p = original_presets[i + 1]
                if prev_p == next_p and prev_p in ("loud", "whisper"):
                    provisional_presets[i] = prev_p

        # 4. Gán preset cho segments
        indices_set = set(target_indices) if target_indices is not None else None
        for i in range(n):
            if indices_set is None or i in indices_set:
                segments[i]["style_preset"] = provisional_presets[i]

        return segments
