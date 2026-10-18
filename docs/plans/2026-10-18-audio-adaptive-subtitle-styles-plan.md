# Audio-Adaptive Subtitle Styles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated audio energy-adaptive subtitle styles (Normal, Loud, Whisper) based on speaker loudness and background audio, with manual overrides in SubEditor, dynamic video player preview, and multi-style ASS hardsub export.

**Architecture:**
- Signal Processing: `AudioEnergyAnalyzer` computes robust trimmed envelope energy from `WaveformService`'s 10ms `peaks_normalized` cache, evaluates global video percentiles ($P_{85}, P_{15}$) with flat-audio safeguards, and applies deterministic smoothing over an immutable snapshot.
- Presentation & Editing: `StylePresetResolver` dynamically maps presets relative to project `global_style` (Base Size, Base×1.2 Bold, Base×0.85 Italic). `SubEditor` renders visual badges (`⚡`, `🤫`) on table rows, provides `EditStyleCommand` undo/redo, and enables selective re-analysis.
- Rendering & Export: `SubtitleOverlay` draws per-segment fonts, colors, outlines, and faux-italic/bold on preview; `core/Backend.py` burns hardsubs via an intermediate `.ass` containing `[V4+ Styles]` for `Style_Normal`, `Style_Loud`, and `Style_Whisper`.

**Tech Stack:** Python 3.11, PySide6 (Qt6), NumPy, FFmpeg (`libass`), pytest.

**Spec:** [docs/specs/2026-10-18-audio-adaptive-subtitle-styles-design.md](file:///d:/ai-subtitle-studio/docs/specs/2026-10-18-audio-adaptive-subtitle-styles-design.md)

## Global Constraints
- Target 3 tiers: `normal` (~70%), `loud` ($\le 15\%$), `whisper` ($\le 15\%$).
- Coordinate positions (X, Y) and animations (Fade, Motion) must NEVER be altered by this feature.
- Softsub export (`.srt`) must remain clean standard text without styling garbage tags.
- Tier 3 (`whisper`) uses `Italic = -1` (never specific font names like `Segoe UI Light`) for 100% font compatibility in FFmpeg `libass`.
- Audio analysis must run in $< 0.05$s by leveraging `peaks_normalized` with zero added memory/disk cache.

## Review Focus
1. Monotone / flat audio input $\rightarrow$ $\text{StdDev} / \text{Median} < 0.15$ triggers flat safeguard, returning 100% `normal` without forcing `loud` or `whisper`.
2. Transient 1ms audio pop/click in short segment $\rightarrow$ Trimmed Mean drops top 10% peak frames, preventing misclassification as `loud`.
3. Selective segment re-analysis on 2 selected rows $\rightarrow$ Reference baseline ($\text{Median}, P_{85}, P_{15}$) is strictly calculated over all video segments ($E_{\text{all}}$), never over the selected subset alone.
4. Domino effect in smoothing $\rightarrow$ Neighbor preset equality check reads from immutable snapshot copy `original_presets`, preventing cascade reclassifications.
5. Cache miss when running in batch mode $\rightarrow$ Worker synchronously generates peaks via `WaveformService.extract_peaks` without failing or crashing.

---

### Task 1: Core Engine - `AudioEnergyAnalyzer` & Signal Processing

**Files:**
- Create: `core/subtitle_quality/audio_energy_analyzer.py`
- Test: `tests/core/test_audio_energy_analyzer.py`

**Interfaces:**
- Consumes: `WaveformService.get_cache_path(video_path)`, `WaveformService.extract_peaks(video_path)` from `core/waveform/waveform_service.py`
- Produces:
  ```python
  class AudioEnergyAnalyzer:
      @staticmethod
      def get_peaks_data(video_path: str) -> np.ndarray: ...
      @staticmethod
      def compute_segment_energy(peaks: np.ndarray, start_ms: int, end_ms: int) -> float: ...
      @staticmethod
      def analyze_segments(
          peaks: np.ndarray,
          segments: list[dict],
          target_indices: list[int] | None = None
      ) -> list[dict]: ...
  ```

- [ ] **Step 1: Write failing tests for `AudioEnergyAnalyzer`**
  Cover:
  - Energy calculation with Trimmed Mean on peak envelope (dropping top 10% peak frames when $K \ge 10$).
  - Transient click resistance: segment with 1 max peak frame amidst low audio is not classified as loud.
  - Flat audio safeguard: uniform audio array yields 100% `normal`.
  - Proper tier thresholding on dynamic range audio ($P_{85}$ and $P_{15}$).
  - Deterministic smoothing: 400ms segment between two `loud` segments with gap $< 500$ms becomes `loud`.
  - Selective re-analysis on `target_indices`: uses global video distribution as reference.

```python
# tests/core/test_audio_energy_analyzer.py
import numpy as np
import pytest
from core.subtitle_quality.audio_energy_analyzer import AudioEnergyAnalyzer

def test_flat_audio_returns_all_normal():
    peaks = np.full((1000, 2), 0.2, dtype=np.float32)
    segments = [
        {"id": f"s{i}", "start_ms": i * 1000, "end_ms": (i + 1) * 1000}
        for i in range(10)
    ]
    analyzed = AudioEnergyAnalyzer.analyze_segments(peaks, segments)
    assert all(s["style_preset"] == "normal" for s in analyzed)

def test_trimmed_mean_ignores_single_frame_click():
    peaks = np.full((100, 2), 0.1, dtype=np.float32)
    peaks[5] = [1.0, 1.0]  # Click spike
    energy = AudioEnergyAnalyzer.compute_segment_energy(peaks, 0, 1000)
    assert energy == pytest.approx(0.1, abs=0.01)

def test_smoothing_snapshot_prevents_domino():
    # s0: loud, s1: 400ms normal, s2: loud, s3: 400ms normal, s4: whisper
    ...
```

- [ ] **Step 2: Run test to verify failure**
  Run: `.venv\Scripts\pytest.exe tests/core/test_audio_energy_analyzer.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'core.subtitle_quality.audio_energy_analyzer'`

- [ ] **Step 3: Implement `AudioEnergyAnalyzer` in `core/subtitle_quality/audio_energy_analyzer.py`**
  Implement:
  - `compute_segment_energy` with Trimmed Mean ($K \ge 10 \rightarrow \text{mean}(sorted(A)[:\lfloor 0.9K \rfloor])$).
  - `get_peaks_data` checking `WaveformService` cache on disk, falling back to synchronous `extract_peaks`.
  - `analyze_segments`:
    - Calculate energy for all segments ($E_{\text{all}}$).
    - If $\text{StdDev} < 0.04$ or $\text{StdDev} / (\text{Median} + 1e-6) < 0.15 \rightarrow$ set all `normal`.
    - Else compute $\text{Thresh}_{loud} = \max(P_{85}, 1.30 \times \text{Median})$, $\text{Thresh}_{whisper} = \min(P_{15}, 0.75 \times \text{Median})$.
    - Initial classification for all segments.
    - Create snapshot copy `original_presets = [s["style_preset"] for s in segments]`.
    - Apply smoothing using `original_presets` (`duration < 800`, `gap_prev <= 500`, `gap_next <= 500`, `original_presets[i-1] == original_presets[i+1]`).
    - If `target_indices` provided, only mutate those indices in `segments`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv\Scripts\pytest.exe tests/core/test_audio_energy_analyzer.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add core/subtitle_quality/audio_energy_analyzer.py tests/core/test_audio_energy_analyzer.py
  git commit -m "feat(core): implement robust AudioEnergyAnalyzer with flat audio and click protections"
  ```

---

### Task 2: Preset Resolution Helper & Post-ASR Hook Integration

**Files:**
- Create: `core/subtitle_quality/style_preset_resolver.py`
- Modify: `ui/subtitle_generation_panel.py:1200-1280`
- Test: `tests/core/test_style_preset_resolver.py`

**Interfaces:**
- Consumes: `AudioEnergyAnalyzer.analyze_segments`
- Produces:
  ```python
  class StylePresetResolver:
      @staticmethod
      def resolve_style(preset: str, global_style: dict) -> dict: ...
  ```

- [ ] **Step 1: Write failing tests for `StylePresetResolver` and Post-ASR Hook**
```python
# tests/core/test_style_preset_resolver.py
from core.subtitle_quality.style_preset_resolver import StylePresetResolver

def test_resolve_normal():
    global_s = {"font_name": "Arial", "font_size": 20, "outline_width": 2}
    s = StylePresetResolver.resolve_style("normal", global_s)
    assert s["font_name"] == "Arial"
    assert s["font_size"] == 20
    assert s["font_color"] == "#FFFFFF"
    assert s["outline_width"] == 2.0
    assert not s.get("bold")
    assert not s.get("italic")

def test_resolve_loud():
    global_s = {"font_name": "Segoe UI", "font_size": 20, "outline_width": 2}
    s = StylePresetResolver.resolve_style("loud", global_s)
    assert s["font_size"] == 24
    assert s["font_color"] == "#FFE600"
    assert s["outline_width"] == 3.5
    assert s.get("bold") is True

def test_resolve_whisper():
    global_s = {"font_name": "Segoe UI", "font_size": 20, "outline_width": 2}
    s = StylePresetResolver.resolve_style("whisper", global_s)
    assert s["font_size"] == 17
    assert s["font_color"] == "#D0D0D0"
    assert s["outline_width"] == 1.5
    assert s.get("italic") is True
```

- [ ] **Step 2: Run test to verify failure**
  Run: `.venv\Scripts\pytest.exe tests/core/test_style_preset_resolver.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'core.subtitle_quality.style_preset_resolver'`

- [ ] **Step 3: Implement `StylePresetResolver` and wire Post-ASR Hook**
  - Implement `StylePresetResolver.resolve_style(preset, global_style)` in `core/subtitle_quality/style_preset_resolver.py`.
  - In `ui/subtitle_generation_panel.py`, when Whisper batch generation reaches 100%:
    - If `auto_audio_style_enabled` is True:
      - Call `AudioEnergyAnalyzer.get_peaks_data(video_path)`.
      - Call `AudioEnergyAnalyzer.analyze_segments(peaks, segments)`.
      - Notify via toast `"⚡ Đã tự động tối ưu Style phụ đề theo năng lượng âm thanh."`

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv\Scripts\pytest.exe tests/core/test_style_preset_resolver.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add core/subtitle_quality/style_preset_resolver.py tests/core/test_style_preset_resolver.py ui/subtitle_generation_panel.py
  git commit -m "feat(core): implement StylePresetResolver and connect post-ASR hook"
  ```

---

### Task 3: SubEditor UI, Row Badges, Context Menu & `EditStyleCommand`

**Files:**
- Create: `core/subtitle_editing/commands/edit_style_command.py`
- Modify: `ui/SubEditor.py:710-770, 830-900`
- Test: `tests/ui/test_adaptive_style_ui.py`

**Interfaces:**
- Consumes: `StylePresetResolver`, `AudioEnergyAnalyzer`, `GlobalUndoManager`
- Produces:
  ```python
  class EditStyleCommand(SubtitleCommand):
      def __init__(self, changes: list[dict], data_provider: list[dict]): ...
  ```

- [ ] **Step 1: Write failing tests for SubEditor styling and `EditStyleCommand`**
```python
# tests/ui/test_adaptive_style_ui.py
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_editing.commands.edit_style_command import EditStyleCommand
from ui.SubEditor import SubtitleEditorWidget

def test_stt_badge_rendering():
    editor = SubtitleEditorWidget()
    editor.all_segments = [
        {"stt": "1", "start": "00:00:01,000", "end": "00:00:03,000", "text": "A", "style_preset": "loud"},
        {"stt": "2", "start": "00:00:04,000", "end": "00:00:06,000", "text": "B", "style_preset": "whisper"},
        {"stt": "3", "start": "00:00:07,000", "end": "00:00:09,000", "text": "C", "style_preset": "normal"},
    ]
    editor.render_page()
    assert "⚡" in editor.table.item(0, 0).text()
    assert "🤫" in editor.table.item(1, 0).text()
    assert "⚡" not in editor.table.item(2, 0).text()
    assert "🤫" not in editor.table.item(2, 0).text()

def test_edit_style_command_undo_redo():
    undo_mgr = GlobalUndoManager()
    segs = [{"id": "s1", "style_preset": "normal"}]
    cmd = EditStyleCommand([{"index": 0, "old_preset": "normal", "new_preset": "loud"}], segs)
    undo_mgr.push(cmd)
    assert segs[0]["style_preset"] == "loud"
    undo_mgr.undo()
    assert segs[0]["style_preset"] == "normal"
    undo_mgr.redo()
    assert segs[0]["style_preset"] == "loud"
```

- [ ] **Step 2: Run test to verify failure**
  Run: `.venv\Scripts\pytest.exe tests/ui/test_adaptive_style_ui.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'core.subtitle_editing.commands.edit_style_command'`

- [ ] **Step 3: Implement `EditStyleCommand` and SubEditor table updates in `ui/SubEditor.py`**
  - Implement `EditStyleCommand` in `core/subtitle_editing/commands/edit_style_command.py`.
  - In `ui/SubEditor.py`:
    - In `render_page()`:
      - If `seg.get("style_preset") == "loud"`: prepend `⚡ ` to STT text, set item tooltip, apply background `QColor(255, 230, 0, 18)`.
      - If `seg.get("style_preset") == "whisper"`: prepend `🤫 ` to STT text, set item tooltip.
    - Add context menu action on table right-click:
      - `🏷️ Đặt Style -> Normal / Loud / Whisper`.
      - Pushes `EditStyleCommand` to `undo_manager`.
    - Add toolbar button `🔄 Quét lại âm lượng`:
      - Gathers selected row indices (or all if none selected).
      - Calls `AudioEnergyAnalyzer.analyze_segments(peaks, self.all_segments, target_indices=selected_indices)` using global baseline.
      - Pushes `EditStyleCommand` for modified segments so user can undo.

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv\Scripts\pytest.exe tests/ui/test_adaptive_style_ui.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add core/subtitle_editing/commands/edit_style_command.py ui/SubEditor.py tests/ui/test_adaptive_style_ui.py
  git commit -m "feat(ui): add SubEditor style badges, context menu, re-analyze button and EditStyleCommand"
  ```

---

### Task 4: Player Subtitle Overlay Preview with Per-Segment Dynamic Style

**Files:**
- Modify: `player/subtitle_overlay.py:40-70, 215-285`
- Modify: `player/video_player.py:405-425`
- Test: `tests/ui/test_adaptive_style_overlay.py`

**Interfaces:**
- Consumes: `StylePresetResolver.resolve_style`, `SubtitleRenderInput`
- Produces: Dynamic per-segment QPainter font, color, outline rendering on `SubtitleOverlay`

- [ ] **Step 1: Write failing tests for SubtitleOverlay per-segment styling**
```python
# tests/ui/test_adaptive_style_overlay.py
from PySide6.QtGui import QColor
from player.subtitle_overlay import SubtitleOverlay
from ui.animations.animation_types import SubtitleRenderInput

def test_overlay_renders_with_resolved_segment_style(qapp):
    overlay = SubtitleOverlay()
    overlay.font_family = "Segoe UI"
    overlay.font_size = 20
    
    # Input with loud preset
    render_input = SubtitleRenderInput(
        segment_id=1,
        start_ms=0,
        end_ms=2000,
        text="LOUD TEXT",
        style_preset="loud"
    )
    overlay.update_subtitle(render_input, 500)
    
    resolved = overlay.get_active_resolved_style()
    assert resolved["font_size"] == 24
    assert resolved["font_color"] == "#FFE600"
    assert resolved["outline_width"] == 3.5
    assert resolved["bold"] is True
```

- [ ] **Step 2: Run test to verify failure**
  Run: `.venv\Scripts\pytest.exe tests/ui/test_adaptive_style_overlay.py -v`
  Expected: FAIL with `AttributeError` or missing `style_preset` field.

- [ ] **Step 3: Implement dynamic styling in `SubtitleOverlay` and `VideoPlayerWidget`**
  - Update `SubtitleRenderInput` in `ui/animations/animation_types.py` to accept `style_preset: str | None = None`.
  - In `player/video_player.py:408`, pass `style_preset=current_seg.get("style_preset")` when constructing `SubtitleRenderInput`.
  - In `player/subtitle_overlay.py`:
    - Add `get_active_resolved_style()` helper using `StylePresetResolver`.
    - In `paintEvent`: apply active resolved font (`setBold`, `setItalic`, `setPixelSize`), text color, and outline width. Keep `placement_state` (X, Y) and animation effects untouched.

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv\Scripts\pytest.exe tests/ui/test_adaptive_style_overlay.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add player/subtitle_overlay.py player/video_player.py ui/animations/animation_types.py tests/ui/test_adaptive_style_overlay.py
  git commit -m "feat(player): support per-segment dynamic style rendering on SubtitleOverlay"
  ```

---

### Task 5: ASS Intermediate Bridge for Multi-Style Hardsub Burning

**Files:**
- Modify: `core/Backend.py:95-175`
- Test: `tests/export/test_hardsub_adaptive_ass.py`

**Interfaces:**
- Consumes: `StylePresetResolver`, `all_segments`
- Produces:
  ```python
  def _build_multistyle_ass(
      segments: list[dict],
      width: int,
      height: int,
      placement_state: SubtitlePlacementState,
      global_style: dict
  ) -> str: ...
  ```

- [ ] **Step 1: Write failing tests for multi-style ASS generation**
```python
# tests/export/test_hardsub_adaptive_ass.py
from core.Backend import _build_multistyle_ass
from player.subtitle_overlay import SubtitlePlacementState

def test_build_multistyle_ass_contains_all_three_styles():
    segments = [
        {"start": "00:00:01,000", "end": "00:00:03,000", "text": "Hello", "style_preset": "normal"},
        {"start": "00:00:04,000", "end": "00:00:06,000", "text": "SHOUT!", "style_preset": "loud"},
        {"start": "00:00:07,000", "end": "00:00:09,000", "text": "psst...", "style_preset": "whisper"},
    ]
    global_style = {"font_name": "Segoe UI", "font_size": 20, "outline_width": 2}
    placement = SubtitlePlacementState(mode="bottom", x=50.0, y=85.0)
    
    ass_text = _build_multistyle_ass(segments, 1920, 1080, placement, global_style)
    
    # Check Styles defined with correct ASS BGR colors and flags
    assert "Style: Style_Normal,Segoe UI,20,&H00FFFFFF" in ass_text
    assert "Style: Style_Loud,Segoe UI,24,&H0000E6FF" in ass_text  # ASS BGR for #FFE600
    assert "Style: Style_Whisper,Segoe UI,17,&H00D0D0D0" in ass_text
    # Check Dialogues use corresponding style names
    assert "Dialogue: 0,0:00:01.00,0:00:03.00,Style_Normal" in ass_text
    assert "Dialogue: 0,0:00:04.00,0:00:06.00,Style_Loud" in ass_text
    assert "Dialogue: 0,0:00:07.00,0:00:09.00,Style_Whisper" in ass_text
```

- [ ] **Step 2: Run test to verify failure**
  Run: `.venv\Scripts\pytest.exe tests/export/test_hardsub_adaptive_ass.py -v`
  Expected: FAIL with `ImportError: cannot import name '_build_multistyle_ass'`

- [ ] **Step 3: Implement `_build_multistyle_ass` and update `burn_hardsub` in `core/Backend.py`**
  - Implement `_build_multistyle_ass(segments, width, height, placement_state, global_style)`.
  - Converts RGB to ASS hex `&H00BBGGRR&`.
  - Sets `Bold = -1` for `Style_Loud`, `Italic = -1` for `Style_Whisper`.
  - Updates `burn_hardsub` to accept optional `segments=None`. If `segments` is provided, writes `_build_multistyle_ass` to a temp `.ass` file and passes `-vf subtitles='temp.ass'` to FFmpeg.
  - Updates `HardsubWorker` to pass `self.all_segments` into `burn_hardsub`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv\Scripts\pytest.exe tests/export/test_hardsub_adaptive_ass.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add core/Backend.py tests/export/test_hardsub_adaptive_ass.py
  git commit -m "feat(export): implement multi-style ASS generation and hardsub burning bridge"
  ```

---

### Task 6: Settings Toggle & Project Serialization Integration

**Files:**
- Modify: `ui/pages/settings_page.py:270-320`
- Modify: `core/project/project_service.py:100-150`
- Test: `tests/ui/test_adaptive_style_settings_and_draft.py`

**Interfaces:**
- Consumes: `SettingsCenterPage`, `ProjectService`
- Produces: Persisted `auto_audio_style_enabled` setting and draft serialization of `style_preset`.

- [ ] **Step 1: Write failing tests for settings toggle and draft persistence**
```python
# tests/ui/test_adaptive_style_settings_and_draft.py
from ui.pages.settings_page import SettingsCenterPage
from core.project.project_service import ProjectService
import tempfile
import os

def test_settings_has_adaptive_style_checkbox(qapp):
    page = SettingsCenterPage()
    assert hasattr(page, "chk_auto_audio_style")
    assert not page.chk_auto_audio_style.isChecked()  # default off

def test_draft_preserves_style_preset():
    service = ProjectService()
    segs = [{"id": "s1", "start": "00:00:01,000", "end": "00:00:03,000", "text": "Hi", "style_preset": "loud"}]
    with tempfile.NamedTemporaryFile(suffix=".ai-subtitle-draft", delete=False) as f:
        tmp_path = f.name
    try:
        service.save_draft(tmp_path, segs)
        loaded = service.load_draft(tmp_path)
        assert loaded["segments"][0]["style_preset"] == "loud"
    finally:
        os.remove(tmp_path)
```

- [ ] **Step 2: Run test to verify failure**
  Run: `.venv\Scripts\pytest.exe tests/ui/test_adaptive_style_settings_and_draft.py -v`
  Expected: FAIL with `AssertionError: assert hasattr(page, 'chk_auto_audio_style')`

- [ ] **Step 3: Implement settings checkbox and draft persistence**
  - In `ui/pages/settings_page.py`: Add `self.chk_auto_audio_style = QCheckBox("Tự động gán Style theo âm lượng sau khi gen sub")` in tab `🎨 Kiểu phụ đề`.
  - In `core/project/project_service.py`: Ensure `save_draft` and `load_draft` serialize and deserialize `style_preset` for each segment.

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv\Scripts\pytest.exe tests/ui/test_adaptive_style_settings_and_draft.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add ui/pages/settings_page.py core/project/project_service.py tests/ui/test_adaptive_style_settings_and_draft.py
  git commit -m "feat(settings): add auto audio style toggle and draft persistence"
  ```

---

### Task 7: Full System Verification & Regression Suite

**Files:**
- Test: `tests/` (full test suite)

- [ ] **Step 1: Run comprehensive tests across all modified modules**
  Run: `.venv\Scripts\pytest.exe -o pythonpath=. tests/core/test_audio_energy_analyzer.py tests/core/test_style_preset_resolver.py tests/ui/test_adaptive_style_ui.py tests/ui/test_adaptive_style_overlay.py tests/export/test_hardsub_adaptive_ass.py tests/ui/test_adaptive_style_settings_and_draft.py -v`
  Expected: ALL PASS

- [ ] **Step 2: Run existing UI and UAT regression suite**
  Run: `.venv\Scripts\pytest.exe -o pythonpath=. tests/ui/ tests/uat/test_subtitle_range_view_uat.py -q`
  Expected: ALL 26 PASS

- [ ] **Step 3: Final branch verification commit**
  ```bash
  git status
  ```
