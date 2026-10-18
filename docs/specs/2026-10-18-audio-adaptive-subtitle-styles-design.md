# Thiết kế Kỹ thuật (V2): Tự động chọn Style Subtitle theo Âm lượng & Âm thanh nền (Audio-Adaptive Subtitle Styles)

- **Ngày cập nhật:** 18-10-2026 (Phiên bản V2 - Đã khắc phục 8 điểm phản biện kỹ thuật)
- **Tác giả:** AI Subtitle Studio Team
- **Trạng thái:** Sẵn sàng phê duyệt (Ready for Sign-off)

---

## 1. Bối cảnh & Mục đích (Context & Intent)

Trong quá trình sản xuất video (Vlog, Shorts, TikTok, Podcast, Phim), phụ đề truyền tải năng lượng và nhịp điệu của lời thoại:
- Khi người nói **hét lên, cười lớn, nói to, hào hứng hoặc âm thanh cao trào**, chữ phụ đề cần nổi bật, đậm đà, cỡ chữ lớn hơn để tạo điểm nhấn thị giác (punchy accent).
- Khi người nói **thì thầm, tâm sự, nói nhỏ**, chữ phụ đề cần thanh thoát, in nghiêng, mềm mại để phù hợp với sắc thái yên tĩnh.
- Khi người nói trò chuyện bình thường, phụ đề giữ phong cách chuẩn mực, dễ đọc.

**Phạm vi can thiệp:** Chỉ tự động chọn **Font chữ, Cỡ chữ, Màu chữ, Độ dày viền, Màu viền, Thuộc tính Bold / Italic**. Hoàn toàn **giữ nguyên vị trí (X, Y) và các hiệu ứng chuyển động (Fade, Motion...)**.

---

## 2. Mục tiêu & Giới hạn (Goals, Non-Goals, Anti-Goals)

### 2.1. Mục tiêu (Goals)
1. **Hệ thống 3 cấp độ Style chuẩn (70% Normal - 15% Loud - 15% Whisper):**
   - **Tier 1 - Tiêu chuẩn (Normal):** Chiếm ~70%, dành cho đối thoại thông thường.
   - **Tier 2 - Nhấn mạnh (Loud / High Energy):** Chiếm tối đa ~15%, dành cho đoạn âm lượng thực sự lớn.
   - **Tier 3 - Thì thầm (Whisper / Quiet):** Chiếm tối đa ~15%, dành cho đoạn nói nhỏ, thì thầm.
2. **Thuật toán Ngưỡng Thích ứng & Chống bẫy âm lượng phẳng (Anti-Flat Audio Trap):**
   - Đánh giá năng lượng bằng **Trimmed Envelope Energy** (loại trừ tiếng nổ/click mic 1ms).
   - Kiểm tra dải động (Dynamic Range): Nếu video thu âm quá phẳng (Monotone Lecture, ASMR, âm thanh đã nén compressor), tự động trả về `100% Normal` thay vì ép gán cưỡng bức.
   - Chỉ gán `Loud` nếu vừa thuộc Top 15% năng lượng **VỪA** vượt tối thiểu $1.3 \times \text{Median RMS}$ (~2.5 dB).
   - Chỉ gán `Whisper` nếu thuộc Bottom 15% năng lượng **VỪA** thấp hơn tối đa $0.75 \times \text{Median RMS}$.
3. **Quy tắc làm mịn (Smoothing Logic) tất định, viết được Unit Test:**
   - Triệt tiêu hiện tượng nhấp nháy (flicker) trên các câu thoại quá ngắn kề nhau.
4. **Cơ chế Bật / Tắt & Tái phân tích an toàn:**
   - Cung cấp checkbox `[x] Tự động gán Style theo âm lượng sau khi gen sub` trong phần Cài đặt phụ đề / Gen sub (mặc định: tắt).
   - Kéo dãn / co timing trên Timeline **bảo lưu 100% style hiện tại**, không tự chạy lại ngầm để tránh phá hỏng Manual Override.
   - Cung cấp nút `🔄 Phân tích lại Style theo âm lượng` trên thanh công cụ để người dùng chủ động kích hoạt khi cần.
5. **Chỉ báo trực quan trên bảng SubEditor:**
   - Cột STT hiển thị icon huy hiệu (`⚡` cho Loud, `🤫` cho Whisper).
   - Nền dòng Loud ánh vàng nhạt nhẹ để người dùng nhìn lướt qua 500 dòng là kiểm soát được ngay.
6. **Đồng bộ toàn diện Preview & Hardsub:**
   - Preview Overlay vẽ đúng style từng dòng bằng PySide6 QPainter.
   - Hardsub xuất file trung gian `.ass` (tương thích 100% với FFmpeg `libass` mà không bị lỗi thiếu font weight).

### 2.2. Phi mục tiêu (Non-Goals)
- Không can thiệp hoặc thay đổi tọa độ vị trí X, Y (Position).
- Không can thiệp hoặc thay đổi hiệu ứng chuyển động/hoạt ảnh (Fade/Motion).
- Không sửa đổi timestamp `start` / `end` hay nội dung chữ của phụ đề.
- **Không ép kiểu styling vào Softsub (`.srt`, `.vtt`, `.txt`):** Các file `.srt` xuất ra luôn là chuẩn text sạch để đảm bảo tương thích 100% mọi trình phát. Đa style chỉ hiển thị trên Preview Overlay, Hardsub MP4 và file `.ass`.

### 2.3. Anti-Goals (Điều tối kỵ)
- **Style Flickering (Nhấp nháy style):** Không đổi style giật cục trên các câu quá ngắn.
- **Faux-font fallback crash trên FFmpeg:** Không gọi font family dạng `"Segoe UI Light"`, dùng `Regular + Italic` tương thích 100% mọi font.

---

## 3. Quy chuẩn 3 Cấp độ Preset (Style Presets Specification)

Mọi Preset đều tính toán tương đối dựa trên **Global Style** (Font chữ và Cỡ chữ cơ sở `Base Size`) do người dùng cấu hình trong Settings:

| Thông số | Mức 1: Tiêu chuẩn (Normal) | Mức 2: Nhấn mạnh (Loud) | Mức 3: Thì thầm (Whisper) |
| :--- | :--- | :--- | :--- |
| **Tỷ lệ mục tiêu** | ~70% thời lượng | Top $\le$ 15% năng lượng cao | Bottom $\le$ 15% năng lượng thấp |
| **Font chữ** | `Font Family` gốc | `Font Family` gốc | `Font Family` gốc |
| **Kiểu chữ (Weight / Posture)** | Regular | **Bold** (Đậm nét) | *Italic* (In nghiêng) |
| **Cỡ chữ (Font Size)** | `Base Size` (mặc định 20pt) | `Base Size × 1.20` (+20%) | `Base Size × 0.85` (-15%) |
| **Màu chữ** | Trắng (`#FFFFFF`) | Vàng chanh (`#FFE600`) | Bạc xám sáng (`#D0D0D0`) |
| **Độ dày viền (Outline)** | `2.0` | `3.5` (Dày dặn, uy lực) | `1.5` (Mảnh mai, tinh tế) |
| **Màu viền** | Đen (`#000000`) | Đen (`#000000`) | Đen (`#000000`) |
| **Huy hiệu trên Bảng** | Không có (Text chuẩn) | `⚡ [STT]` + Nền vàng nhạt 10% | `🤫 [STT]` |

*(Lưu ý: Nếu bật Auto-scale theo độ phân giải video, `Base Size` sẽ tự động nhân với hệ số phân giải trước khi áp dụng tỷ lệ của 3 Preset trên).*

---

## 4. Thiết kế Kỹ thuật Chi tiết (Detailed Technical Architecture)

### 4.1. Mô hình Dữ liệu Động (Dynamic Data Model)
Mỗi phần tử trong danh sách `all_segments` lưu trữ:
```python
{
    "id": "seg_01",
    "stt": 1,
    "start": "00:00:01,000",
    "end": "00:00:03,500",
    "text": "Xin chào các bạn!",
    "style_preset": "normal",  # "normal" | "loud" | "whisper" | "custom"
    "custom_style": None       # Chỉ gán dict nếu người dùng can thiệp chỉnh tay sâu từng thông số
}
```

### 4.2. Thuật toán Phân tích Năng lượng Âm thanh (`AudioEnergyAnalyzer`)
Vị trí: `core/subtitle_quality/audio_energy_analyzer.py`

#### A. Tránh Race Condition & Cơ chế Fallback Cache
```python
def get_peaks_data(video_path: str) -> np.ndarray:
    # 1. Kiểm tra cache có sẵn từ WaveformService
    peaks = WaveformService.load_cached_peaks(video_path)
    if peaks is not None:
        return peaks
    # 2. Cache miss (Batch Queue hoặc mở video lần đầu chưa dựng waveform)
    # Chủ động gọi trích xuất đồng bộ ngay trong worker thread
    return WaveformService.extract_peaks(video_path)
```

#### B. Công thức Tính Năng lượng Robust (Trimmed Envelope Energy)
Mảng `peaks_normalized` có shape `[N, 2]` lưu `[min, max]` mỗi khung 10ms:
1. Với mỗi segment $s$ có khoảng thời gian $[start\_ms, end\_ms]$, xác định các chỉ số khung:
   $i_{start} = \lfloor start\_ms / 10 \rfloor$, $i_{end} = \lceil end\_ms / 10 \rceil$.
2. Lấy mảng biên độ đỉnh: $A[k] = \max(|min\_k|, |max\_k|)$ với $k \in [i_{start}, i_{end}]$.
3. Nếu segment có $K$ khung:
   - Nếu $K \ge 10$: Sắp xếp tăng dần và lấy **Trimmed Mean (loại bỏ 10% khung đỉnh cao nhất)** để triệt tiêu tiếng click/nổ mic 1ms:
     $$\text{Energy}(s) = \frac{1}{\lfloor 0.9 K \rfloor} \sum_{j=0}^{\lfloor 0.9 K \rfloor - 1} A_{sorted}[j]$$
   - Nếu $K < 10$: Lấy trung bình cộng đơn thuần.

#### C. Chống Bẫy Âm lượng Phẳng & Phân vị Thích ứng
1. Thu thập danh sách năng lượng của toàn bộ video: $E = [\text{Energy}(s_1), \text{Energy}(s_2), \dots]$.
2. Tính $\text{Median} = \text{median}(E)$ và $\text{StdDev} = \text{std}(E)$.
3. **Kiểm tra độ phẳng (Flat Check):**
   Nếu $\text{StdDev} < 0.04$ hoặc $\frac{\text{StdDev}}{\text{Median} + 10^{-6}} < 0.15$:
   $\rightarrow$ Dải động âm thanh quá hẹp (podcast đã nén limiter hoặc bài giảng đều đều). Gán **100% segments là `normal`** và kết thúc sớm.
4. **Phân vị động (Dynamic Percentile):**
   - $P_{85} = \text{percentile}(E, 85)$
   - $P_{15} = \text{percentile}(E, 15)$
   - Ngưỡng Loud: $\text{Thresh}_{loud} = \max(P_{85}, 1.30 \times \text{Median})$
   - Ngưỡng Whisper: $\text{Thresh}_{whisper} = \min(P_{15}, 0.75 \times \text{Median})$
5. Gán ban đầu:
   - Nếu $\text{Energy}(s) \ge \text{Thresh}_{loud} \rightarrow \text{loud}$.
   - Nếu $\text{Energy}(s) \le \text{Thresh}_{whisper} \rightarrow \text{whisper}$.
   - Còn lại $\rightarrow \text{normal}$.

#### D. Thuật toán Làm mịn Tất định (Deterministic Smoothing Rule)
Hằng số:
- `MIN_SMOOTH_DURATION_MS = 800`
- `MAX_SMOOTH_GAP_MS = 500`

Quy tắc:
Với mỗi segment $i \in [1, N-2]$:
1. Nếu $\text{duration}(s_i) < \text{MIN\_SMOOTH\_DURATION\_MS}$:
2. Kiểm tra khoảng nghỉ:
   $\text{gap}_{prev} = s_i.start\_ms - s_{i-1}.end\_ms \le \text{MAX\_SMOOTH\_GAP\_MS}$
   VÀ $\text{gap}_{next} = s_{i+1}.start\_ms - s_i.end\_ms \le \text{MAX\_SMOOTH\_GAP\_MS}$.
3. Nếu cả 2 khoảng nghỉ đều thỏa mãn VÀ $s_{i-1}.style\_preset == s_{i+1}.style\_preset$:
   $\rightarrow$ Gán $s_i.style\_preset = s_{i-1}.style\_preset$.
*(Nếu 3 câu kề nhau mang 3 preset khác nhau, giữ nguyên giá trị gốc đã tính toán, không làm mịn cưỡng bức).*

---

### 4.3. Tích hợp sau khi Whisper hoàn thành (Post-ASR Hook)
Vị trí: `ui/subtitle_generation_panel.py` / `core/subtitle_generation/`
- Khi tiến trình sinh phụ đề đạt 100%:
  - Kiểm tra cài đặt `auto_audio_style_enabled`.
  - Nếu `True`: Worker gọi `AudioEnergyAnalyzer.apply_adaptive_styles(video_path, segments)` trước khi gửi tín hiệu cập nhật lên UI.
  - Hiển thị Toast thông báo: `"⚡ Đã tối ưu Style phụ đề theo năng lượng âm thanh."`

---

### 4.4. Trực quan hóa trên Bảng SubEditor (`ui/SubEditor.py`)
- **Cột STT (Số thứ tự):**
  - Segment `loud`: Hiển thị `⚡ 1`, `⚡ 2`. Tooltip: `"Style: Nhấn mạnh (Loud)"`.
  - Segment `whisper`: Hiển thị `🤫 3`, `🤫 4`. Tooltip: `"Style: Thì thầm (Whisper)"`.
  - Segment `normal`: Hiển thị số STT bình thường.
- **Tô màu phân biệt nhẹ (Row Tinting):**
  - Dòng `loud`: Nền bảng tô nhẹ ánh vàng nhạt `QColor(255, 230, 0, 18)`.
  - Dòng `whisper`: Text hiển thị chữ nghiêng nhẹ màu xám bạc.
- **Menu chuột phải & Phím tắt:**
  - Chuột phải trên các dòng được chọn:
    - `🏷️ Đặt Style -> [ Normal (Tiêu chuẩn) | ⚡ Loud (Nhấn mạnh) | 🤫 Whisper (Thì thầm) ]`.
  - Hỗ trợ hoàn tác `Ctrl+Z` và làm lại `Ctrl+Y` qua `EditStyleCommand`.
- **Nút phân tích lại:**
  - Trên thanh công cụ Timeline/SubEditor bổ sung nút `🔄 Quét lại âm lượng`. Người dùng có thể quét lại toàn bộ hoặc chỉ quét lại các dòng đang chọn sau khi cắt gọt timing.

---

### 4.5. Hiển thị Preview (`player/subtitle_overlay.py`)
Hàm `paintEvent` phân giải style theo `render_input.style_preset`:
- Lấy font gốc của dự án: `font = QFont(global_font_family)`.
- Nếu `preset == "loud"`:
  - `font.setBold(True)`
  - `font.setPixelSize(int(base_size * 1.20))`
  - `text_color = QColor("#FFE600")`, `outline_width = 3.5`.
- Nếu `preset == "whisper"`:
  - `font.setItalic(True)` (Faux-italic an toàn trên mọi font)
  - `font.setPixelSize(int(base_size * 0.85))`
  - `text_color = QColor("#D0D0D0")`, `outline_width = 1.5`.
- Nếu `preset == "normal"`:
  - Font Regular chuẩn, `base_size`, `text_color = QColor("#FFFFFF")`, `outline_width = 2.0`.
- Tọa độ X, Y và Animation Controller giữ nguyên 100%.

---

### 4.6. Xuất Hardsub Chuẩn Xác qua ASS (`core/Backend.py`)
Khi gọi `burn_hardsub`:
1. Sinh file tạm `.ass` chứa header 3 Style tương thích `libass`:
   ```ini
   [V4+ Styles]
   Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
   Style: Style_Normal,Segoe UI,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2.0,0,5,10,10,10,1
   Style: Style_Loud,Segoe UI,24,&H0000E6FF,&H0000E6FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3.5,0,5,10,10,10,1
   Style: Style_Whisper,Segoe UI,17,&H00D0D0D0,&H00D0D0D0,&H00000000,&H00000000,0,-1,0,0,100,100,0,0,1,1.5,0,5,10,10,10,1
   ```
2. Mỗi dòng thoại `Dialogue` chỉ định trực tiếp tên Style:
   ```ini
   Dialogue: 0,0:00:01.00,0:00:03.50,Style_Normal,,0,0,0,,Xin chào các bạn!
   Dialogue: 0,0:00:03.50,0:00:05.00,Style_Loud,,0,0,0,,ĐÂY LÀ ĐOẠN CAO TRÀO!
   Dialogue: 0,0:00:05.20,0:00:06.80,Style_Whisper,,0,0,0,,hãy giữ im lặng nhé...
   ```
3. Truyền file `.ass` vào tham số `-vf subtitles=temp.ass` của FFmpeg.

---

## 5. Kế hoạch Kiểm thử Toàn diện (Testing Matrix)

1. **Unit Test Thuật toán (`tests/core/test_audio_energy_analyzer.py`):**
   - *Test Case 1 (Flat Audio):* Mảng âm thanh đều đều $\rightarrow$ Xác nhận trả về 100% `normal`.
   - *Test Case 2 (Trimmed Mean vs Click):* Segment có 1 xung đột biến cực đại 1ms $\rightarrow$ Xác nhận không bị phân loại nhầm thành `loud`.
   - *Test Case 3 (Smoothing Gap):* Đoạn ngắn 400ms kẹp giữa 2 câu `loud` cách nhau 300ms $\rightarrow$ Xác nhận được làm mịn thành `loud`.
   - *Test Case 4 (Smoothing Isolation):* Đoạn ngắn 400ms nhưng cách câu trước 5 giây $\rightarrow$ Xác nhận giữ nguyên, không bị gộp bừa bãi.
2. **UI & Command Tests (`tests/ui/test_adaptive_style_ui.py`):**
   - Xác nhận icon `⚡` và `🤫` render đúng cột STT trên bảng `SubEditor`.
   - Test lệnh `EditStyleCommand`: Áp dụng preset cho 5 dòng, nhấn `Ctrl+Z` hoàn tác về trạng thái cũ.
   - Test kéo resize trên Timeline: Xác nhận `style_preset` của segment không bị mất hoặc ghi đè ngầm.
3. **Export Integration Tests (`tests/export/test_hardsub_adaptive_ass.py`):**
   - Xác nhận file `.ass` sinh ra có đủ 3 Styles và từng dòng trỏ đúng tên style.

---

## 6. Cam kết Đóng gói & Tương thích (Sign-off Summary)

- **Độ nhạy & Dải động:** Hoàn toàn miễn nhiễm với lỗi ép preset trên video âm thanh phẳng.
- **Tương thích Font 100%:** Dùng `Italic` (-1) thay vì phụ thuộc font file `Light`, đảm bảo FFmpeg render không lỗi.
- **Minh bạch UX:** Có huy hiệu trực quan trên từng dòng, có quyền kiểm soát và nút quét lại thủ công.
- **Tốc độ:** Tận dụng cache `WaveformService` có sẵn, fallback an toàn khi cache miss.
