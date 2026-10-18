import numpy as np
import pytest
from core.subtitle_quality.audio_energy_analyzer import AudioEnergyAnalyzer


def test_flat_audio_returns_all_normal():
    # Audio with very little variance (monotone / ASMR / heavily compressed)
    peaks = np.full((1000, 2), 0.2, dtype=np.float32)
    segments = [
        {"id": f"s{i}", "start_ms": i * 1000, "end_ms": (i + 1) * 1000}
        for i in range(10)
    ]
    analyzed = AudioEnergyAnalyzer.analyze_segments(peaks, segments)
    assert all(s["style_preset"] == "normal" for s in analyzed)


def test_trimmed_mean_ignores_single_frame_click():
    # 100 frames = 1000ms. All frames are 0.1 except 1 spike frame of 1.0 (click/pop)
    peaks = np.zeros((100, 2), dtype=np.float32)
    peaks[:, 0] = -0.1
    peaks[:, 1] = 0.1
    # Spike at index 5
    peaks[5, 0] = -1.0
    peaks[5, 1] = 1.0
    
    # 100 frames >= 10, trimmed mean drops top 10% (10 frames)
    energy = AudioEnergyAnalyzer.compute_segment_energy(peaks, 0, 1000)
    assert energy == pytest.approx(0.1, abs=0.01)


def test_dynamic_audio_classifies_loud_whisper_normal():
    # Generate 100 segments with clear variance
    # Segment 0..14 low (0.05), Segment 15..84 mid (0.3), Segment 85..99 loud (0.8)
    peaks = np.zeros((10000, 2), dtype=np.float32)
    segments = []
    for i in range(100):
        start_ms = i * 1000
        end_ms = (i + 1) * 1000
        idx_s = i * 100
        idx_e = (i + 1) * 100
        if i < 15:
            amp = 0.05
        elif i >= 85:
            amp = 0.8
        else:
            amp = 0.3
        peaks[idx_s:idx_e, 0] = -amp
        peaks[idx_s:idx_e, 1] = amp
        segments.append({"id": f"s{i}", "start_ms": start_ms, "end_ms": end_ms})

    analyzed = AudioEnergyAnalyzer.analyze_segments(peaks, segments)
    
    # First 15 should be whisper
    for i in range(15):
        assert analyzed[i]["style_preset"] == "whisper", f"Segment {i} failed"
    # Middle segments should be normal
    for i in range(15, 85):
        assert analyzed[i]["style_preset"] == "normal", f"Segment {i} failed"
    # Top 15 should be loud
    for i in range(85, 100):
        assert analyzed[i]["style_preset"] == "loud", f"Segment {i} failed"


def test_smoothing_snapshot_prevents_domino():
    # s0: loud (1500ms)
    # s1: short normal (400ms, gap <= 500ms)
    # s2: loud (1500ms)
    # s3: short normal (400ms, gap <= 500ms)
    # s4: whisper (1500ms)
    # With snapshot:
    # s1 sees s0(loud) and s2(loud) -> becomes loud
    # s3 sees s2(loud) and s4(whisper) in original_presets -> does NOT become loud!
    peaks = np.zeros((6000, 2), dtype=np.float32)
    segments = [
        {"id": "s0", "start_ms": 0, "end_ms": 1500, "style_preset": "loud"},
        {"id": "s1", "start_ms": 1600, "end_ms": 2000, "style_preset": "normal"},
        {"id": "s2", "start_ms": 2100, "end_ms": 3600, "style_preset": "loud"},
        {"id": "s3", "start_ms": 3700, "end_ms": 4100, "style_preset": "normal"},
        {"id": "s4", "start_ms": 4200, "end_ms": 5700, "style_preset": "whisper"},
    ]
    # Set peak values to match initial presets so raw analysis yields initial presets
    # s0: amp 0.9, s1: amp 0.4, s2: amp 0.9, s3: amp 0.4, s4: amp 0.05
    for s, amp in zip(segments, [0.9, 0.4, 0.9, 0.4, 0.05]):
        idx_s = int(s["start_ms"] / 10)
        idx_e = int(s["end_ms"] / 10)
        peaks[idx_s:idx_e, 0] = -amp
        peaks[idx_s:idx_e, 1] = amp
    
    # We add 20 dummy segments to provide a normal baseline with high std
    dummy_segs = []
    for i in range(20):
        start = 6000 + i * 1000
        end = start + 800
        dummy_segs.append({"id": f"d{i}", "start_ms": start, "end_ms": end})
    peaks_ext = np.zeros((30000, 2), dtype=np.float32)
    peaks_ext[:6000] = peaks
    # Add dummy peaks with 0.4 amp
    peaks_ext[600:3000, 0] = -0.4
    peaks_ext[600:3000, 1] = 0.4

    all_segs = segments + dummy_segs
    analyzed = AudioEnergyAnalyzer.analyze_segments(peaks_ext, all_segs)
    
    # s1 bridged between loud & loud -> loud
    assert analyzed[1]["style_preset"] == "loud"
    # s3 bridged between loud & whisper -> stays normal (no domino effect from s1!)
    assert analyzed[3]["style_preset"] == "normal"


def test_selective_reanalysis_preserves_unselected():
    # 3 segments
    peaks = np.zeros((3000, 2), dtype=np.float32)
    # s0: whisper, s1: loud, s2: whisper
    peaks[0:100, 1] = 0.05
    peaks[100:200, 1] = 0.9
    peaks[200:300, 1] = 0.05
    
    segments = [
        {"id": "s0", "start_ms": 0, "end_ms": 1000, "style_preset": "manual_custom"},
        {"id": "s1", "start_ms": 1000, "end_ms": 2000, "style_preset": "manual_custom"},
        {"id": "s2", "start_ms": 2000, "end_ms": 3000, "style_preset": "manual_custom"},
    ]
    # Re-analyze ONLY index 1
    analyzed = AudioEnergyAnalyzer.analyze_segments(peaks, segments, target_indices=[1])
    assert analyzed[0]["style_preset"] == "manual_custom"
    assert analyzed[1]["style_preset"] == "loud"
    assert analyzed[2]["style_preset"] == "manual_custom"


def test_string_timestamps_support():
    peaks = np.zeros((1000, 2), dtype=np.float32)
    peaks[0:50, 1] = 0.2
    segments = [
        {"id": "s0", "start": "00:00:00,000", "end": "00:00:00,500"}
    ]
    analyzed = AudioEnergyAnalyzer.analyze_segments(peaks, segments)
    assert analyzed[0]["style_preset"] == "normal"
