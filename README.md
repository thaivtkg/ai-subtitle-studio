# 🎬 AI Subtitle Studio

> **Hệ thống Tạo Phụ đề Tự động, Biên tập Dạng sóng âm (Waveform/Timeline) & Trợ lý LLM Sinh Ngữ cảnh.**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![UI Framework](https://img.shields.io/badge/PySide6-Qt6-green.svg)](https://pypi.org/project/PySide6/)
[![AI Engine](https://img.shields.io/badge/Faster--Whisper-Large--v3--Turbo-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Audio Processing](https://img.shields.io/badge/FFmpeg-6.0%2B-red.svg)](https://ffmpeg.org/)
[![Architecture](https://img.shields.io/badge/Layout-DAW%203--Tier-purple.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](#)

---

## 📌 Mục lục

- [Giới thiệu](#-giới-thiệu)
- [Tính năng cốt lõi](#-tính-năng-cốt-lõi)
- [Bố cục Giao diện Chuẩn DAW](#-bố-cục-giao-diện-chuẩn-daw-3-tier-workspace)
- [Bảng Phím tắt Toàn cục](#-bảng-phím-tắt-toàn-cục-shortcuts)
- [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
- [Hướng dẫn cài đặt](#-hướng-dẫn-cài-đặt--chạy-mã-nguồn)
- [Đóng gói & Tạo bộ cài đặt](#-đóng-gói--tạo-bộ-cài-đặt-windows-installer)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục-dự-án)
- [Lộ trình phát triển](#-lộ-trình-phát-triển-roadmap)
- [Đóng góp](#-đóng-góp)
- [Giấy phép](#-giấy-phép)

---

## 📖 Giới thiệu

**AI Subtitle Studio** là phần mềm biên tập phụ đề video chuyên dụng chạy trực tiếp trên máy tính cá nhân. Ứng dụng kết hợp sức mạnh nhận diện giọng nói cục bộ của **Faster-Whisper**, công cụ trích xuất **FFmpeg**, cùng giao diện điều khiển phi tuyến tính (NLE) hiện đại được xây dựng hoàn toàn trên nền tảng **PySide6 (Qt6)**.

Phần mềm được thiết kế theo tư duy **Timestamp-First (Timing Artifact)** và kiến trúc **Dự án Độc lập (`.ai-subtitle`)**, cho phép bóc tách – nắn chỉnh thời gian trên trục sóng âm trước khi sinh nội dung chữ bằng AI, đảm bảo độ chính xác tuyệt đối từng mili-giây và an toàn dữ liệu.

---

## 🚀 Tính năng cốt lõi

### 🎚️ Trục thời gian & Dải sóng âm Tương tác
- Tự động trích xuất đỉnh sóng âm thanh (Audio Peaks) chạy trên luồng ngầm không gây đơ giao diện.
- Hỗ trợ thao tác chuột trực quan: Kéo di chuyển (`Move`), Kéo giãn 2 đầu (`Resize Left/Right`), Bôi đen đa khối.
- Đồng bộ vị trí phát tức thì giữa Kim thời gian (Playhead), Video Player và Bảng phụ đề.

### ⚡ Hệ thống Lệnh Cấu trúc & Snapshot Undo/Redo Tuyệt đối
- Áp dụng mẫu thiết kế **Snapshot Pattern**: Chụp toàn bộ trạng thái dữ liệu trước/sau thao tác, đảm bảo hoàn tác (`Ctrl+Z`) và làm lại (`Ctrl+Shift+Z`) chính xác 100% dữ liệu gốc mà không gây rò rỉ bộ nhớ.
- Cơ chế **Transactional Integrity**: Tự động rollback và khóa lệnh nếu phát hiện sai lệch mốc thời gian (Validation) hoặc lỗi tham chiếu Artifact.

### 📁 Quản lý Dự án Độc lập (`.ai-subtitle`)
- Đóng gói toàn bộ Artifacts (SRT, Draft JSON, Hardsub Video, Checkpoint) vào một thư mục dự án duy nhất.
- Tự động lưu/khôi phục không gian làm việc (Workspace State).
- Tự động đồng bộ và ghi đè dữ liệu Timeline xuống chính xác tập tin đang mở khi nhấn `Ctrl+S`.

### ✨ Động cơ Điền chữ AI theo Batch
- Tùy chỉnh Batch AI linh hoạt (1, 5, 10, 20... dòng/lượt).
- Tự động định vị và tiếp tục điền chữ từ câu trống gần nhất kèm cơ chế Auto-checkpoint ngầm.

### 🎨 Hiệu ứng Chữ & Trình phát Video Tối ưu
- Xem trước phụ đề nổi thời gian thực trên khung hình chuẩn tỉ lệ.
- Tích hợp bộ điều khiển hoạt ảnh (Fade, Rise, Drop, Highlight Reveal).
- Tùy biến đầy đủ Font, Cỡ chữ, Màu sắc, Viền chữ (Outline), Vị trí (Top, Center, Bottom).

---

## 🖥️ Bố cục Giao diện Chuẩn DAW (3-Tier Workspace)

Giao diện làm việc chính (`Video Workspace`) được quy hoạch theo bố cục 3 tầng dọc tối ưu luồng mắt:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TẦNG 1: VIDEO PREVIEW                           │
│              [Khung nhìn Video + Subtitle Overlay Nổi]                 │
│              [Nút Play/Pause | Thanh Tua Seek | Âm lượng]              │
├──────────────────────────────────────────┬─────────────────────────────┤
│        TẦNG 2A: SUBTITLE EDITOR          │   TẦNG 2B: AI / LOG PANEL   │
│                                          │                             │
│  STT | Bắt đầu  | Kết thúc | Nội dung    │  [Tab AI Quick Actions]     │
│   1  | 00:00:00 | 00:00:04 | Chào bạn... │  - Chọn Model / Prompt      │
│   2  | 00:00:04 | 00:00:08 | ...         │  - Batch Size & Điền chữ    │
│                                          │  [Tab Live Log]             │
│  [Chốt Timing] [Lưu Draft] [Lưu SRT]     │  - Nhật ký tiến trình ngầm  │
├──────────────────────────────────────────┴─────────────────────────────┤
│                     TẦNG 3: TIMELINE & WAVEFORM                        │
│ 00:00       00:01       00:02       00:03       00:04       00:05      │
│ ════════════════════════ Waveform Sóng Âm ════════════════════════════ │
│   [ #1 Chào bạn... ]   [ #2 ...          ]                             │
│            │ (Playhead Đồng bộ Kim thời gian)                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⌨️ Bảng Phím tắt Toàn cục (Shortcuts)

| Phím tắt | Phạm vi | Chức năng |
|----------|---------|-----------|
| `Ctrl + N` | Toàn ứng dụng | Mở hộp thoại tạo Dự án mới (`.ai-subtitle`) |
| `Ctrl + O` | Toàn ứng dụng | Mở thư mục Dự án đã có |
| `Ctrl + S` | Toàn ứng dụng | Lưu toàn bộ dự án, cấu hình và ghi đè Timing xuống đĩa |
| `Space` | Video Player | Bật / Tạm dừng phát video |
| `Ctrl + T` | Timeline | Cắt khối phụ đề (Split) tại vị trí kim thời gian |
| `Ctrl + M` | Timeline | Gộp các khối phụ đề (Merge) đang được chọn |
| `Delete` | Timeline | Xóa khối phụ đề (Delete) đang chọn |
| `Ctrl + Z` | Timeline | Hoàn tác (Undo) thao tác chỉnh sửa gần nhất |
| `Ctrl + Shift + Z` | Timeline | Làm lại (Redo) thao tác vừa hoàn tác |

---

## 💻 Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu | Khuyến nghị |
|------------|-------------------|-------------|
| **Hệ điều hành** | Windows 10 / 11 (64-bit) | Windows 11 (64-bit) |
| **Python** | Python 3.10 | Python 3.10.x hoặc 3.11.x |
| **RAM** | 8 GB | 16 GB trở lên |
| **GPU** | Không bắt buộc (chạy CPU) | NVIDIA GPU (≥ 4GB VRAM, GTX 1650 trở lên) |
| **CUDA / cuDNN** | CUDA 11.8 hoặc 12.x | cuDNN tương thích với phiên bản PyTorch |

---

## 🛠️ Hướng dẫn cài đặt & Chạy mã nguồn

### Yêu cầu tiên quyết

1. Cài đặt [Python 3.10+](https://www.python.org/downloads/)
2. Cài đặt [FFmpeg 6.0+](https://ffmpeg.org/download.html) và thêm vào PATH
3. (Tùy chọn) Cài đặt [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads) và [cuDNN](https://developer.nvidia.com/cudnn) để tăng tốc GPU

### Cài đặt từ mã nguồn

```bash
# Clone repository
git clone https://github.com/yourusername/ai-subtitle-studio.git
cd ai-subtitle-studio

# Tạo môi trường ảo (khuyến nghị)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate     # Windows

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy ứng dụng
python ui/Gui.py
```

### Cài đặt từ bộ cài đặt Windows

Tải file `AI_Subtitle_Studio_Setup.exe` từ [Releases](https://github.com/yourusername/ai-subtitle-studio/releases) và chạy để cài đặt.

---

## 📦 Đóng gói & Tạo bộ cài đặt Windows (Installer)

### 1. Đóng gói mã nguồn thành File thực thi (PyInstaller)

Chạy lệnh build ứng dụng độc lập không cần cài đặt Python:

```bash
pyinstaller --noconfirm --onedir --windowed ^
    --name "AI Subtitle Studio" ^
    --add-data "bin;bin" ^
    --add-data "resources;resources" ^
    --collect-all faster_whisper ^
    ui/Gui.py
```

Sau khi build xong, sản phẩm sẽ nằm tại thư mục `dist/AI Subtitle Studio/`.

### 2. Tạo File Setup Cài đặt (Inno Setup)

1. Cài đặt công cụ [Inno Setup 6+](https://jrsoftware.org/isinfo.php)
2. Mở file cấu hình cài đặt `installer/setup_script.iss`
3. Nhấn **Compile** (`Ctrl + F9`)

File cài đặt đầu ra `AI_Subtitle_Studio_Setup.exe` sẽ được tạo trong thư mục `release/` với các tính năng:
- Tự động tạo Shortcut ngoài Desktop và Start Menu
- Đính kèm đầy đủ `ffmpeg.exe`, `ffprobe.exe` và thư viện C++ Runtime
- Hỗ trợ gỡ cài đặt (Uninstaller) sạch sẽ khỏi hệ điều hành

---

## 📁 Cấu trúc thư mục dự án

```
ai-subtitle-studio/
├── ui/
│   └── Gui.py                    # File khởi động chính
├── core/
│   ├── timeline.py               # Xử lý Timeline & Waveform
│   ├── project.py                # Quản lý Dự án (.ai-subtitle)
│   └── subtitle.py               # Xử lý Subtitle Artifacts
├── ai/
│   ├── whisper_engine.py         # Faster-Whisper integration
│   └── llm_assistant.py          # Context-aware LLM
├── resources/
│   ├── icons/                    # Biểu tượng ứng dụng
│   └── styles/                   # QSS Stylesheets
├── installer/
│   └── setup_script.iss          # Inno Setup script
├── bin/
│   └── ffmpeg.exe                # FFmpeg binaries
├── requirements.txt              # Python dependencies
└── README.md                     # Tài liệu này
```

---

## 🗺️ Lộ trình phát triển (Roadmap)

- [x] **Sprint 1-5**: Khởi tạo Core Whisper, Subtitle Overlay, Batch Queue & Quản lý Thư mục Output
- [x] **Sprint 6**: Quản lý Vòng đời Artifacts (`.ai-subtitle-draft`) & Tối ưu UI
- [x] **Sprint 7**: Kiến trúc Dự án Độc lập (`.ai-subtitle`), Quản lý Checkpoint & Tự động Khôi phục Workspace
- [x] **Sprint 8**: Trục thời gian Phi tuyến tính (Interactive Waveform Timeline), NLE DAW Layout, Core Validation & Snapshot Undo/Redo Exact-state
- [ ] **Sprint 9**: Contextual Fill-Text & Smart Subtitle Generation (Tách bạch Text/Timing Artifact, Tích hợp Local LLM Context-aware, Generation Planner & Trình quản lý AI Validator)
- [ ] **Sprint 10**: Word-Level Alignment & Timing Optimization
- [ ] **Sprint 11**: ASS Rendering & Hiệu ứng Karaoke nâng cao

---

## 🤝 Đóng góp

Chúng tôi hoan nghênh mọi đóng góp! Vui lòng đọc [CONTRIBUTING.md](CONTRIBUTING.md) để biết chi tiết về quy trình đóng góp.

### Cách đóng góp

1. Fork repository
2. Tạo branch mới (`git checkout -b feature/AmazingFeature`)
3. Commit thay đổi (`git commit -m 'Add some AmazingFeature'`)
4. Push lên branch (`git push origin feature/AmazingFeature`)
5. Mở Pull Request

---

## 📄 Giấy phép

Phần mềm được phát hành dưới giấy phép **MIT License**. Xem file [LICENSE](LICENSE) để biết thêm chi tiết.

---

## 🙏 Cảm ơn

- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) - AI Engine
- [PySide6](https://pypi.org/project/PySide6/) - UI Framework
- [FFmpeg](https://ffmpeg.org/) - Audio/Video Processing

---

<div align="center">

**🌟 Đừng quên star repository nếu bạn thấy dự án hữu ích!**

Made with ❤️ by [Your Team/Name]

---

## 📝 Ghi chú bổ sung

File README này đã được tối ưu hóa với:

1. **Cấu trúc rõ ràng**: Mục lục, các phần được phân tách logic
2. **Badge trực quan**: Hiển thị trạng thái công nghệ sử dụng
3. **Hướng dẫn chi tiết**: Cài đặt, đóng gói, cấu trúc thư mục
4. **Mã nguồn mẫu**: Các lệnh terminal được định dạng rõ ràng
5. **Bảng biểu**: Dễ đọc cho phím tắt và yêu cầu hệ thống
6. **ASCI diagram**: Minh họa giao diện trực quan
7. **Roadmap checklist**: Theo dõi tiến độ phát triển
8. **Phần đóng góp**: Khuyến khích cộng đồng tham gia

Bạn có thể điều chỉnh các URL (GitHub, repository) và thông tin tác giả cho phù hợp với dự án của mình.