# 🎬 AI Subtitle Studio

> **Hệ thống Tạo Phụ đề Tự động, Biên tập Dạng sóng âm (Waveform/Timeline) & Render Hardsub Video chuẩn NLE Chuyên nghiệp.**

---

## 📌 Mục lục

1. [Giới thiệu](#-giới-thiệu)
2. [Tính năng cốt lõi](#-tính-năng-cốt-lõi)
3. [Bảng Phím tắt Toàn cục (Shortcuts)](#-bảng-phím-tắt-toàn-cục-shortcuts)
4. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
5. [Hướng dẫn cài đặt & Chạy mã nguồn](#-hướng-dẫn-cài-đặt--chạy-mã-nguồn)
6. [Đóng gói & Tạo bộ cài đặt Windows (Installer)](#dong-goi-installer)
7. [Xử lý sự cố thường gặp (Troubleshooting)](#troubleshooting)
8. [Tài liệu thiết kế và lịch sử dự án](docs/README.md)

---

## 📖 Giới thiệu

**AI Subtitle Studio** là phần mềm biên tập phụ đề video chuyên dụng chạy trực tiếp trên máy tính cá nhân. Ứng dụng kết hợp sức mạnh nhận diện giọng nói cục bộ của **Faster-Whisper (Large-v3-Turbo)**, thuật toán phân tách giọng nói Silero VAD, công cụ trích xuất/kết xuất **FFmpeg**, cùng giao diện điều khiển phi tuyến tính (NLE) hiện đại được xây dựng hoàn toàn trên nền tảng **PySide6 (Qt6)**.

Phần mềm được thiết kế theo tư duy **Timestamp-First (Timing Draft)** và kiến trúc **Dự án Độc lập (`.ai-subtitle`)**, cho phép bóc tách – nắn chỉnh thời gian trên trục sóng âm trước khi sinh nội dung chữ bằng AI, đảm bảo độ chính xác tuyệt đối từng mili-giây.

---

## 🚀 Tính năng cốt lõi

* 🎚️ **Trục thời gian & Dải sóng âm Tương tác (Interactive Waveform Timeline)**
  * Tự động trích xuất đỉnh sóng âm thanh (Audio Peaks) chạy trên luồng ngầm không gây đơ giao diện.
  * Khối phụ đề hiển thị trực tiếp số thứ tự và nội dung text (`#1 Nội dung...`).
  * Hỗ trợ thao tác chuột trực quan: Kéo di chuyển (`Move`), Kéo giãn 2 đầu (`Resize Left/Right`), Bôi đen đa khối.
  * Đồng bộ vị trí phát tức thì giữa Kim thời gian (Playhead), Video Player và Bảng phụ đề.

* ⚡ **Hệ thống Lệnh Cấu trúc & Snapshot Undo/Redo Tuyệt đối**
  * Hỗ trợ đầy đủ các thao tác cắt (`Split`), gộp câu liền kề (`Merge`), xóa (`Delete`).
  * Áp dụng mẫu thiết kế **Snapshot Pattern**: Chụp toàn bộ trạng thái dữ liệu trước/sau thao tác, đảm bảo hoàn tác (`Ctrl+Z`) và làm lại (`Ctrl+Shift+Z`) chính xác 100%.
  * Cơ chế **Transactional Integrity**: Tự động rollback và khóa lệnh nếu phát hiện sai lệch mốc thời gian hoặc lỗi tham chiếu Artifact.

* 📁 **Quản lý Dự án Độc lập (`.ai-subtitle`) & Checkpoint/Resume**
  * Đóng gói toàn bộ Artifacts (SRT, Draft JSON, Checkpoint) vào một thư mục dự án duy nhất.
  * Cơ chế **Checkpoint & Resume** tự động ghi nhận tiến độ theo từng Batch (Hỗ trợ băm theo thời gian hoặc số câu), cho phép tiếp tục chạy ngay cả khi sập nguồn hoặc hủy ngang.
  * Tự động đồng bộ và ghi đè dữ liệu Timeline xuống chính xác tập tin đang mở khi nhấn `Ctrl+S`.

* ⏱️ **Timing Draft (VAD Only)**
  * Cho phép chọn **Model Size** và **Compute Type** riêng cho Timing Draft; VAD luôn bắt buộc trong chế độ này.
  * **Fix Subtitle Overlap** là tùy chọn theo dự án, với khoảng cách cấu hình được từ `1–500 ms`.
  * Checkpoint Timing lưu các thiết lập ảnh hưởng đến kết quả. Resume và Retry dùng thiết lập của checkpoint, trong khi tùy chọn hiện tại của dự án vẫn độc lập.
  * Checkpoint cũ thiếu đủ thiết lập sẽ bị chặn Resume/Retry thay vì tự đoán cấu hình.

* 🎨 **Hiệu ứng Chữ & Trình phát Video Tối ưu**
  * Xem trước phụ đề nổi thời gian thực trên khung hình chuẩn tỉ lệ (Aspect Ratio Locked).
  * Tích hợp bộ điều khiển hoạt ảnh (Fade, Rise, Drop, Highlight Reveal).
  * Tùy biến đầy đủ Font, Cỡ chữ, Màu sắc, Viền chữ (Outline) và preset vị trí (Top, Center, Bottom).
  * Có thể kéo phụ đề trực tiếp trong khung preview để tạo vị trí Custom; vị trí chuẩn hóa được lưu theo dự án và được giữ khi export.

* 🧭 **Help Center & Getting Started**
  * Help Center hỗ trợ tìm kiếm hướng dẫn và phím tắt.
  * Getting Started guided tour có thể mở lại từ Help Center, kèm nội dung hướng dẫn và media tutorial nội bộ.

* 💎 **Giao diện Quang học Kính lỏng (Liquid Glass V2 Optical Engine & Design System)**
  * **Hệ thống Vật lý Thấu kính (Optical Physics):** Khối điều hướng Sidebar tích hợp công nghệ **Background Caching** (làm mờ nền nội suy siêu nhẹ không sụt FPS), tạo ảo giác thấu kính quang học với độ lệch khúc xạ (**Refraction Y-offset 1.5px**).
  * **Động lực học Lò xo Độc lập (Independent Spring Dynamics):** Áp dụng định luật Hooke kết hợp giảm chấn (**Spring-Mass-Damper**), vệt sáng phản quang trễ pha 30ms (**Lagging Specular Highlight**), hiệu ứng phồng dẹp theo vận tốc (**Squash & Stretch**) và co giãn vật lý khi nhấn chuột (**Morphing Scale**).
  * **Vật liệu Bán trong suốt Đa tầng (Frosted Translucency):** Hòa trộn màu nền thông minh (**Context-aware Tint**), viền hắt sáng cực mảnh (**Edge Lighting**), ánh sáng trong (**Inner Glow**) và bóng đổ chiều sâu không gian (**Soft Drop Shadow**).
  * **Trải nghiệm Giữ - Kéo - Thả (Continuous Drag-to-Select):** Hỗ trợ click giữ và rê chuột trượt mượt mà dọc thanh Sidebar và các ListBox/Tab; khối kính liên tục bám sát con trỏ và tự động snap kích hoạt mục được chọn khi thả chuột.
  * **Chuẩn hóa Vi kiến trúc (P0 Visual Grammar):** Quy chuẩn hình khối 8px cho Standard Controls, 16px cho Surfaces, 24px/Pill cho Glass & Primary Actions, đồng bộ qua trình biên dịch giao diện duy nhất `LiquidThemeEngine`.

* 🎬 **Xuất xưởng Đa Định dạng & Render Hardsub GPU/CPU**
  * Xuất file phụ đề mềm: `.srt`, `.vtt`, `.txt`.
  * Kết xuất Hardsub trực tiếp vào video thông qua FFmpeg chạy nền, hiển thị đầy đủ tiến độ, tốc độ render (Speed x) và thời gian dự tính (ETA).
---

### Audio Range & Gap Editing

AI Subtitle Studio allows precise control over subtitle generation and editing for specific audio segments without affecting the rest of your project.

*   **Audio Gap Recovery:** The timeline automatically identifies gaps (sections without subtitles). Click on any gap directly on the subtitle track to select that specific audio range.
*   **Range Generation:** Generate subtitles only for a selected audio range. You can select a range by clicking a gap, manually entering Start/End times, or Shift-dragging on the waveform. The generation process safely inserts new subtitles into the selected range without overwriting existing ones.
*   **Segment Editing & Focus:** Select an individual subtitle segment to focus playback and edit its text or timing independently. Trim or extend segments directly within the editor constraints.

### Bổ sung phụ đề cho đoạn âm thanh còn thiếu

Tính năng hỗ trợ rà soát và tạo phụ đề bổ sung cho các khoảng thời gian trống trên trục timeline:

* **Nhận diện khoảng trống trên Timeline (Uncovered Timeline Ranges):**
  * Trục thời gian tự động đánh dấu các khoảng thời gian chưa có phụ đề bao phủ (đây là các khoảng trống thời gian trên timeline, không phải do AI hoặc VAD phát hiện có tiếng nói).
* **Cách chọn khoảng thời gian (Range Selection):**
  * Nhấp chuột trực tiếp vào khoảng trống (gap) trên timeline.
  * Nhập trực tiếp mốc thời gian **Start / End** trên thanh công cụ tạo phụ đề.
  * Giữ phím **Shift** và kéo rê chuột trên dải sóng âm (waveform) để khoanh vùng đoạn cần xử lý.
* **Quy tắc tạo phụ đề theo vùng chọn:**
  * Tính năng tạo phụ đề chỉ áp dụng cho khoảng thời gian hợp lệ chưa có phụ đề bao phủ.
  * Khoảng thời gian có phần giao dương (chồng lấn) với các phụ đề hiện hữu sẽ bị từ chối tạo phụ đề để đảm bảo tính toàn vẹn của dữ liệu.
  * Quá trình sinh phụ đề chỉ tác động đến duy nhất phạm vi thời gian đã chọn; toàn bộ các phụ đề nằm ngoài phạm vi này được giữ nguyên.
  * Mốc thời gian của phụ đề mới sinh có thể được tự động điều chỉnh an toàn để đảm bảo nằm trọn vẹn trong khoảng thời gian đã chỉ định.
* **Tiêu điểm và phát riêng đoạn phụ đề (Focus & Play Segment):**
  * Khi chọn một dòng phụ đề, dải sóng âm sẽ tự động làm nổi bật (highlight) phạm vi thời gian tương ứng và hiển thị chi tiết **Start**, **End** cùng **Duration**.
  * Nhấn nút **Play Segment** để phát riêng biệt đoạn âm thanh của phụ đề đó, giúp kiểm tra nhanh nội dung và độ khớp.
* **Tinh chỉnh thời gian trực quan (Trim / Extend):**
  * Kéo mép trái sang phải để cắt ngắn (trim) đoạn đầu; kéo sang trái để mở rộng (extend) đoạn đầu.
  * Kéo mép phải sang trái để cắt ngắn (trim) đoạn cuối; kéo sang phải để mở rộng (extend) đoạn cuối.
  * Toàn bộ thao tác chỉnh sửa thời gian đều hỗ trợ hoàn tác (**Undo** - `Ctrl+Z`) và làm lại (**Redo** - `Ctrl+Shift+Z`).
* **Giới hạn hiện tại:**
  * Tính năng tạo phụ đề theo vùng chọn hiện chỉ hỗ trợ các khoảng trống chưa có phụ đề (uncovered ranges). Việc tái tạo hoặc thay thế đè (regenerate/replace) lên các phụ đề đã tồn tại chưa nằm trong phạm vi của chức năng này.

---

## ⌨️ Bảng Phím tắt Toàn cục (Shortcuts)

| **Phím tắt**           | **Phạm vi**   | **Chức năng**                                          |
| ---------------------- | ------------- | ------------------------------------------------------ |
| **`Ctrl + N`**         | Toàn ứng dụng | Mở hộp thoại tạo Dự án mới (`.ai-subtitle`)            |
| **`Ctrl + O`**         | Toàn ứng dụng | Mở thư mục Dự án đã có                                 |
| **`Ctrl + S`**         | Toàn ứng dụng | Lưu toàn bộ dự án, cấu hình và ghi đè Timing xuống đĩa |
| **`Space`**            | Video Player  | Bật / Tạm dừng phát video                              |
| **`Ctrl + T`**         | Timeline      | **Cắt khối phụ đề (Split)** tại vị trí kim thời gian   |
| **`Ctrl + M`**         | Timeline      | **Gộp các khối phụ đề (Merge)** đang được chọn         |
| **`Delete`**           | Timeline      | **Xóa khối phụ đề (Delete)** đang chọn                 |
| **`Ctrl + Z`**         | Timeline      | **Hoàn tác (Undo)** thao tác chỉnh sửa gần nhất        |
| **`Ctrl + Shift + Z`** | Timeline      | **Làm lại (Redo)** thao tác vừa hoàn tác               |

## 💻 Yêu cầu hệ thống

| **Thành phần**       | **Yêu cầu tối thiểu**     | **Khuyến nghị**                           |
| -------------------- | ------------------------- | ----------------------------------------- |
| **Hệ điều hành**     | Windows 10 / 11 (64-bit)  | Windows 11 (64-bit)                       |
| **Python**           | Python 3.10               | Python 3.10.x hoặc 3.11.x                 |
| **RAM**              | 8 GB                      | 16 GB trở lên                             |
| **GPU**              | Không bắt buộc (chạy CPU) | NVIDIA GPU (≥ 4GB VRAM, GTX 1650 trở lên) |
| **CUDA / cuDNN**     | Không bắt buộc khi chạy CPU | `requirements-runtime.txt` dùng PyTorch CUDA 12.1; cần driver tương thích |
| **Dung lượng trống** | 5 GB SSD                  | 15 GB SSD                                 |

### Dependency profiles

- `requirements.txt`: bộ dependency nền linh hoạt cho môi trường chạy mã nguồn (PySide6, Faster-Whisper, PyTorch, CTranslate2, Pydantic, Requests, v.v.).
- `requirements-runtime.txt`: profile nền thay thế, ghim phiên bản chính xác để tạo runtime/CI reproducible; hiện dùng PyTorch CUDA 12.1.
- `requirements-dev.txt`: phần bổ sung chỉ dành cho development/test; hiện gồm Pillow cho demo-capture và asset validation.

`requirements-dev.txt` được cài thêm sau một trong hai profile nền ở trên. Không cần cài đồng thời `requirements.txt` và `requirements-runtime.txt`.

Python 3.10/3.11 được khuyến nghị. FFmpeg/FFprobe cần có trong `ffmpeg/` hoặc trên `PATH`.

## 📦 Hướng dẫn cài đặt & Chạy mã nguồn

### Bước 1: Tải mã nguồn


```bash
git clone https://github.com/thaivtkg/ai-subtitle-studio.git
cd ai-subtitle-studio

```

### Bước 2: Thiết lập môi trường ảo


```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Hoặc trên Command Prompt (cmd):
.\.venv\Scripts\activate.bat

```

### Bước 3: Cài đặt các gói phụ thuộc


```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Đường dẫn trên là profile chạy mã nguồn/development. Nếu cần profile runtime đã ghim, dùng nó thay cho `requirements.txt`, sau đó vẫn cài phần dev:

```bash
python -m pip install -r requirements-runtime.txt
python -m pip install -r requirements-dev.txt
```

### Bước 4: Cấu hình FFmpeg

1. Nếu chạy từ mã nguồn, đặt `ffmpeg.exe` và `ffprobe.exe` vào thư mục `ffmpeg/` của dự án hoặc đưa chúng vào `PATH`.
2. Bản đóng gói PyInstaller đã kèm thư mục `ffmpeg/` trong gói ứng dụng.

### Bước 5: Khởi chạy ứng dụng


```bash
python main.py

```

<a id="dong-goi-installer"></a>

## 🛠️ Đóng gói & Tạo bộ cài đặt Windows (Installer)

### 1. Đóng gói mã nguồn thành File thực thi (`PyInstaller`)

Sử dụng kịch bản build tự động hoặc tệp cấu hình spec:

```powershell
# Cách 1: Chạy trực tiếp qua Python script
python build.py

# Cách 2: Sử dụng trực tiếp PyInstaller với file Spec
pyinstaller --noconfirm --clean "AI Subtitle Studio.spec"

# Cách 3: Chạy script đóng gói tự động hóa (PowerShell)
.\tools\build_windows.ps1
```

Gói nhị phân hoàn chỉnh được xuất ra tại thư mục `dist/AI Subtitle Studio/`.

### 2. Tạo File Setup Cài đặt (`Inno Setup`)

1. Cài đặt công cụ [Inno Setup 6+](https://jrsoftware.org/).
2. Biên dịch bộ cài đặt Windows:
   - Mở và biên dịch tệp `installer.iss` (hoặc `deployment/installer/setup.iss`) bằng Inno Setup Compiler.
   - Hoặc chạy bằng lệnh CLI:
     ```powershell
     & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
     ```
3. Tệp cài đặt được xuất ra: `dist/AI_Subtitle_Studio_Setup_v1.0.0.exe`.

<a id="troubleshooting"></a>

## 🧰 Xử lý sự cố thường gặp (Troubleshooting)

### Ứng dụng không khởi động từ mã nguồn

Đảm bảo môi trường ảo đã được kích hoạt và các dependency đã được cài đúng profile:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python main.py
```

Nếu dùng profile runtime đã ghim, thay `requirements.txt` bằng `requirements-runtime.txt`.

### Không tìm thấy FFmpeg / FFprobe

Đặt `ffmpeg.exe` và `ffprobe.exe` trong thư mục `ffmpeg/` của dự án hoặc thêm thư mục chứa chúng vào `PATH`.

Kiểm tra nhanh:

```powershell
ffmpeg -version
ffprobe -version
```

### CUDA / GPU không hoạt động

Nếu nhận dạng giọng nói hoặc tác vụ AI không dùng được GPU, kiểm tra driver NVIDIA và môi trường PyTorch/CUDA đang cài. Có thể xác minh nhanh bằng:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.version.cuda)"
```

Nếu `torch.cuda.is_available()` trả về `False`, ứng dụng vẫn có thể chạy bằng CPU nếu tác vụ tương ứng hỗ trợ.

### Lỗi quyền truy cập thư mục dữ liệu người dùng

Ứng dụng lưu dữ liệu runtime trong hồ sơ người dùng Windows. Hãy chạy ứng dụng bằng tài khoản Windows đang sở hữu hồ sơ đó và tránh tự gán `LOCALAPPDATA` sang hồ sơ của tài khoản khác.

Nếu lỗi quyền vẫn xuất hiện, kiểm tra quyền truy cập của thư mục dữ liệu ứng dụng trong `%LOCALAPPDATA%`.

### Build Windows thất bại vì không tìm thấy PyInstaller

Kích hoạt `.venv` trước khi chạy script build, hoặc bảo đảm `.venv\Scripts` có trong `PATH` của phiên terminal hiện tại:

```powershell
.\.venv\Scripts\Activate.ps1
.\scripts\build_windows.ps1
```

## 📚 Tài liệu thiết kế và lịch sử dự án

Các design spec, implementation plan và hồ sơ review lịch sử được liệt kê tại [docs/README.md](docs/README.md). Checklist trong tài liệu cũ không đại diện cho backlog hiện hành.

## 📄 Giấy phép

Phần mềm được phát hành dưới giấy phép **MIT License**.

**Made with ❤️ for Content Creators, Translators & Video Editors**
