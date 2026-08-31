# 🎬 AI Subtitle Studio

> **Hệ thống Tạo Phụ đề Tự động, Biên tập Dạng sóng âm (Waveform/Timeline) & Render Hardsub Video chuẩn NLE Chuyên nghiệp.**

---

## 📌 Mục lục

1. [Giới thiệu](#-giới-thiệu)
2. [Tính năng cốt lõi](#-tính-năng-cốt-lõi)
3. [Bố cục Giao diện Chuẩn DAW (3-Tier Workspace)](#-bố-cục-giao-diện-chuẩn-daw-3-tier-workspace)
4. [Bảng Phím tắt Toàn cục (Shortcuts)](#-bảng-phím-tắt-toàn-cục-shortcuts)
5. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
6. [Hướng dẫn cài đặt & Chạy mã nguồn](#-hướng-dẫn-cài-đặt--chạy-mã-nguồn)
7. [Đóng gói & Tạo bộ cài đặt Windows (Installer)](#-đóng-gói--tạo-bộ-cài-đặt-windows-installer)
8. [Cấu trúc thư mục dự án](#-cấu-trúc-thư-mục-dự-án)
9. [Quy trình làm việc (Workflows)](#-quy-trình-làm-việc-workflows)
10. [Kiểm thử tự động (Automated Testing)](#-kiểm-thử-tự-động-automated-testing)
11. [Xử lý sự cố thường gặp (Troubleshooting)](#-xử-lý-sự-cố-thường-gặp-troubleshooting)
12. [Lộ trình phát triển (Roadmap)](#-lộ-trình-phát-triển-roadmap)

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

* 🎨 **Hiệu ứng Chữ & Trình phát Video Tối ưu**
  * Xem trước phụ đề nổi thời gian thực trên khung hình chuẩn tỉ lệ (Aspect Ratio Locked).
  * Tích hợp bộ điều khiển hoạt ảnh (Fade, Rise, Drop, Highlight Reveal).
  * Tùy biến đầy đủ Font, Cỡ chữ, Màu sắc, Viền chữ (Outline), Vị trí (Top, Center, Bottom).

* 🎬 **Xuất xưởng Đa Định dạng & Render Hardsub GPU/CPU**
  * Xuất file phụ đề mềm: `.srt`, `.vtt`, `.txt`.
  * Kết xuất Hardsub trực tiếp vào video thông qua FFmpeg chạy nền, hiển thị đầy đủ tiến độ, tốc độ render (Speed x) và thời gian dự tính (ETA).

---

## 🖥️ Bố cục Giao diện Chuẩn DAW (3-Tier Workspace)

Giao diện làm việc chính (`Video Workspace`) được quy hoạch theo bố cục 3 tầng dọc tối ưu luồng mắt:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        TẦNG 1: VIDEO PREVIEW                           │
│               [Khung nhìn Video + Subtitle Overlay Nổi]                │
│               [Nút Play/Pause | Thanh Tua Seek | Âm lượng]             │
├──────────────────────────────────────────┬─────────────────────────────┤
│          TẦNG 2A: SUBTITLE EDITOR        │   TẦNG 2B: AI / LOG PANEL   │
│                                          │                             │
│  STT | Bắt đầu  | Kết thúc | Nội dung    │  [Tab AI Quick Actions]     │
│   1  | 00:00:00 | 00:00:04 | Chào bạn... │  - Chọn Model / Mode        │
│   2  | 00:00:04 | 00:00:08 | ...         │  - Batch Mode & Time/Count  │
│                                          │  [Tab Live Log]             │
│  [Chốt Timing] [Lưu Draft] [Lưu SRT]     │  - Nhật ký tiến trình ngầm  │
├──────────────────────────────────────────┴─────────────────────────────┤
│                         TẦNG 3: TIMELINE & WAVEFORM                    │
│ 00:00      00:01      00:02      00:03      00:04      00:05      │
│ ════════════════════════ Waveform Sóng Âm ════════════════════════════ │
│   [ #1 Chào bạn... ]   [ #2 ...          ]                             │
│          │ (Playhead Đồng bộ Kim thời gian)                            │
└────────────────────────────────────────────────────────────────────────┘

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
| **CUDA / cuDNN**     | CUDA 11.8 hoặc 12.x       | cuDNN tương thích với phiên bản PyTorch   |
| **Dung lượng trống** | 5 GB SSD                  | 15 GB SSD                                 |

## 📦 Hướng dẫn cài đặt & Chạy mã nguồn

### Bước 1: Tải mã nguồn


```bash
git clone https://github.com/your-username/ai-subtitle-studio.git
cd ai-subtitle-studio

```

### Bước 2: Thiết lập môi trường ảo


```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt trên Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Hoặc trên Command Prompt (cmd):
.\venv\Scripts\activate.bat

```

### Bước 3: Cài đặt các gói phụ thuộc


```bash
pip install --upgrade pip
pip install -r requirements.txt



### Bước 4: Cấu hình FFmpeg

1. Tải bản build tĩnh của FFmpeg từ trang chủ hoặc các nguồn uy tín (Gyan.dev).
2. Đặt `ffmpeg.exe` và `ffprobe.exe` vào thư mục `bin/` hoặc `installer/ffmpeg/` của dự án.

### Bước 5: Khởi chạy ứng dụng


```bash
python ui/Gui.py

```

## 🛠️ Đóng gói & Tạo bộ cài đặt Windows (Installer)

### 1. Đóng gói mã nguồn thành File thực thi (`PyInstaller`)


```bash
pyinstaller --noconfirm --onedir --windowed ^
    --name "AI Subtitle Studio" ^
    --add-data "bin;bin" ^
    --add-data "resources;resources" ^
    --collect-all faster_whisper ^
    ui/Gui.py

```

### 2. Tạo File Setup Cài đặt (`Inno Setup`)

1. Cài đặt công cụ [Inno Setup 6+](https://jrsoftware.org/).
2. Mở file cấu hình cài đặt `installer/setup_script.iss`.
3. Nhấn **Compile** (`Ctrl + F9`) để xuất file `AI_Subtitle_Studio_Setup.exe` vào thư mục `release/`.

## 📂 Cấu trúc thư mục dự án


```
ai-subtitle-studio/
├── bin/                          # Binary FFmpeg / FFprobe độc lập
├── core/                         # Tầng Logic Xử lý Cốt lõi
│   ├── artifacts/                # Quản lý Artifact & Vòng đời Subtitle/Draft
│   ├── subtitle_generation/      # Domain Faster-Whisper, Planner, Reconciler, Checkpoint
│   ├── services/                 # Quản lý Trạng thái Dự án & Workspace
│   ├── timeline/                 # Động cơ Timeline & Quản lý Lệnh (Undo/Redo)
│   ├── timing/                   # Thuật toán Timing & VAD Batching
│   ├── waveform/                 # Dịch vụ Trích xuất Sóng âm Background
│   └── queue_manager.py          # Quản lý danh sách hàng đợi Video
├── installer/                    # Kịch bản đóng gói Inno Setup
├── player/                       # Thành phần Video Player (QGraphicsView)
├── tests/                        # Bộ kiểm thử Tự động (Automated Test Suite)
│   └── test_subtitle_generation.py
├── ui/                           # Giao diện Người dùng PySide6 (Qt6)
│   ├── subtitle_generation_panel.py # Panel ngăn kéo cấu hình ASR & Batch
│   ├── Gui.py                    # Cửa sổ Chính & Điều phối Sự kiện Toàn cục
│   └── SubEditor.py              # Bảng Biên tập Phụ đề Dạng Lưới
├── workers/                      # Background Worker Threads (Hardsub, Subtitle Gen)
└── requirements.txt              # Danh sách thư viện Python

```

## 🧪 Kiểm thử tự động (Automated Testing)

Chạy bộ kiểm thử tích hợp (bao gồm kiểm tra Time/Segment Planner, Stale Guard, Checkpoint Resume và Boundary Reconciliation):


```bash
python -m unittest tests/test_subtitle_generation.py -v
python -m unittest tests/test_timeline.py -v

```

## 📄 Giấy phép

Phần mềm được phát hành dưới giấy phép **MIT License**.

**Made with ❤️ for Content Creators, Translators & Video Editors**