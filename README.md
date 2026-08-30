# 🎬 AI Subtitle Studio

> **Hệ thống Tạo Phụ đề Tự động, Biên tập Dạng sóng âm (Waveform/Timeline) & Render Hardsub Video chuẩn NLE Chuyên nghiệp.**

---

## 📌 Mục lục

1. [Giới thiệu](https://www.google.com/search?q=%23-gi%E1%BB%9Bi-thi%E1%BB%87u)
2. [Tính năng cốt lõi](https://www.google.com/search?q=%23-t%C3%ADnh-n%C4%83ng-c%E1%BB%91t-l%C3%B5i)
3. [Bố cục Giao diện Chuẩn DAW (3-Tier Workspace)](https://www.google.com/search?q=%23-b%E1%BB%91-c%E1%BB%A5c-giao-di%E1%BB%87n-chu%E1%BA%A9n-daw-3-tier-workspace)
4. [Bảng Phím tắt Toàn cục (Shortcuts)](https://www.google.com/search?q=%23-b%E1%BA%A3ng-ph%C3%ADm-t%E1%BA%AFt-to%C3%A0n-c%E1%BB%A5c-shortcuts)
5. [Yêu cầu hệ thống](https://www.google.com/search?q=%23-y%C3%AAu-c%E1%BA%A7u-h%E1%BB%87-th%E1%BB%91ng)
6. [Hướng dẫn cài đặt & Chạy mã nguồn](https://www.google.com/search?q=%23-h%C6%B0%E1%BB%9Bng-d%E1%BA%ABn-c%C3%A0i-%C4%91%E1%BA%B7t--ch%E1%BA%A1y-m%C3%A3-ngu%E1%BB%93n)
7. [Đóng gói & Tạo bộ cài đặt Windows (Installer)](https://www.google.com/search?q=%23-%C4%91%C3%B3ng-g%C3%B3i--t%E1%BA%A1o-b%E1%BB%99-c%C3%A0i-%C4%91%E1%BA%B7t-windows-installer)
8. [Cấu trúc thư mục dự án](https://www.google.com/search?q=%23-c%E1%BA%A5u-tr%C3%BAc-th%C6%B0-m%E1%BB%A5c-d%E1%BB%B1-%C3%A1n)
9. [Quy trình làm việc (Workflows)](https://www.google.com/search?q=%23-quy-tr%C3%ACnh-l%C3%A0m-vi%E1%BB%87c-workflows)
10. [Kiểm thử tự động (Automated Testing)](https://www.google.com/search?q=%23-ki%E1%BB%83m-th%E1%BB%AD-t%E1%BB%B1-%C4%91%E1%BB%99ng-automated-testing)
11. [Xử lý sự cố thường gặp (Troubleshooting)](https://www.google.com/search?q=%23-x%E1%BB%AD-l%C3%BD-s%E1%BB%B1-c%E1%BB%91-th%C6%B0%E1%BB%9Dng-g%E1%BA%B7p-troubleshooting)
12. [Lộ trình phát triển (Roadmap)](https://www.google.com/search?q=%23-l%E1%BB%99-tr%C3%ACnh-ph%C3%A1t-tri%E1%BB%83n-roadmap)

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
* Áp dụng mẫu thiết kế **Snapshot Pattern**: Chụp toàn bộ trạng thái dữ liệu trước/sau thao tác, đảm bảo hoàn tác (`Ctrl+Z`) và làm lại (`Ctrl+Shift+Z`) chính xác 100% dữ liệu gốc mà không gây rò rỉ bộ nhớ.
* Cơ chế **Transactional Integrity**: Tự động rollback và khóa lệnh nếu phát hiện sai lệch mốc thời gian hoặc lỗi tham chiếu Artifact.


* 📁 **Quản lý Dự án Độc lập (`.ai-subtitle`)**
* Đóng gói toàn bộ Artifacts (SRT, Draft JSON, Hardsub Video, Checkpoint) vào một thư mục dự án duy nhất.
* Tự động lưu/khôi phục không gian làm việc (Workspace State & Window Geometry).
* Tự động đồng bộ và ghi đè dữ liệu Timeline xuống chính xác tập tin đang mở khi nhấn `Ctrl+S`.


* ✨ **Động cơ Điền chữ AI theo Batch (In-Memory Slicing)**
* Nạp dải âm thanh lên RAM và cắt trực tiếp trên mảng dữ liệu mảng, giảm thiểu tối đa độ trễ đọc/ghi ổ cứng.
* Tùy chỉnh Batch AI linh hoạt (1, 5, 10, 20... dòng/lượt).
* Tự động định vị và tiếp tục điền chữ từ câu trống gần nhất.


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
| --- | --- | --- |
| **`Ctrl + N`** | Toàn ứng dụng | Mở hộp thoại tạo Dự án mới (`.ai-subtitle`) |
| **`Ctrl + O`** | Toàn ứng dụng | Mở thư mục Dự án đã có |
| **`Ctrl + S`** | Toàn ứng dụng | Lưu toàn bộ dự án, cấu hình và ghi đè Timing xuống đĩa |
| **`Space`** | Video Player | Bật / Tạm dừng phát video |
| **`Ctrl + T`** | Timeline | **Cắt khối phụ đề (Split)** tại vị trí kim thời gian |
| **`Ctrl + M`** | Timeline | **Gộp các khối phụ đề (Merge)** đang được chọn |
| **`Delete`** | Timeline | **Xóa khối phụ đề (Delete)** đang chọn |
| **`Ctrl + Z`** | Timeline | **Hoàn tác (Undo)** thao tác chỉnh sửa gần nhất |
| **`Ctrl + Shift + Z`** | Timeline | **Làm lại (Redo)** thao tác vừa hoàn tác |

---

## 💻 Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu | Khuyến nghị |
| --- | --- | --- |
| **Hệ điều hành** | Windows 10 / 11 (64-bit) | Windows 11 (64-bit) |
| **Python** | Python 3.10 | Python 3.10.x hoặc 3.11.x |
| **RAM** | 8 GB | 16 GB trở lên |
| **GPU** | Không bắt buộc (chạy CPU) | NVIDIA GPU (≥ 4GB VRAM, GTX 1650 trở lên) |
| **CUDA / cuDNN** | CUDA 11.8 hoặc 12.x | cuDNN tương thích với phiên bản PyTorch |
| **Dung lượng trống** | 5 GB SSD | 15 GB SSD |

---

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

# Cài đặt dependencies
pip install -r requirements.txt

```

### Bước 4: Cấu hình FFmpeg

1. Tải bản build tĩnh của FFmpeg từ [gyan.dev](https://www.google.com/search?q=https://www.gyan.dev/ffmpeg/builds/) hoặc [ffmpeg.org](https://www.google.com/search?q=https://ffmpeg.org/).
2. Đặt `ffmpeg.exe` và `ffprobe.exe` vào thư mục `bin/` hoặc `installer/ffmpeg/` của dự án.

### Bước 5: Khởi chạy ứng dụng

```bash
python ui/Gui.py

```

---

## 🛠️ Đóng gói & Tạo bộ cài đặt Windows (Installer)

Dự án cung cấp quy trình đóng gói thành tập tin `.exe` độc lập và đóng gói bộ cài đặt Setup tự động cho Windows.

### 1. Đóng gói mã nguồn thành File thực thi (`PyInstaller`)

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

### 2. Tạo File Setup Cài đặt (`Inno Setup`)

1. Cài đặt công cụ [Inno Setup 6+](https://www.google.com/search?q=https://jrsoftware.org/isdl.php).
2. Mở file cấu hình cài đặt `installer/setup_script.iss` (hoặc script trong thư mục `installer/`).
3. Nhấn **Compile** (`Ctrl + F9`).
4. File cài đặt đầu ra `AI_Subtitle_Studio_Setup.exe` sẽ được tạo trong thư mục `release/` với các tính năng:
* Tự động tạo Shortcut ngoài Desktop và Start Menu.
* Đính kèm đầy đủ `ffmpeg.exe`, `ffprobe.exe` và thư viện C++ Runtime.
* Hỗ trợ gỡ cài đặt (Uninstaller) sạch sẽ khỏi hệ điều hành.



### 2. Tạo File Setup Cài đặt (Inno Setup)

1. Cài đặt công cụ [Inno Setup 6+](https://jrsoftware.org/isinfo.php)
2. Mở file cấu hình cài đặt `installer/setup_script.iss`
3. Nhấn **Compile** (`Ctrl + F9`)

```text
ai-subtitle-studio/
├── bin/                              # Binary FFmpeg / FFprobe độc lập
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── core/                             # Tầng Logic Xử lý Cốt lõi
│   ├── artifacts/                    # Quản lý Artifact & Vòng đời Subtitle/Draft
│   │   ├── artifact.py
│   │   ├── artifact_store.py
│   │   └── artifact_types.py
│   ├── services/                     # Quản lý Trạng thái Dự án & Workspace
│   │   ├── project_service.py
│   │   └── workspace_service.py
│   ├── timeline/                     # Động cơ Timeline & Quản lý Lệnh
│   │   ├── timeline_commands.py      # Lệnh Move, Resize, Split, Merge, Delete
│   │   ├── timeline_controller.py    # Bộ điều phối Tương tác Chuột / Bàn phím
│   │   ├── timeline_data_provider.py # Cầu nối Dữ liệu RAM & Bảng Editor
│   │   ├── timeline_integration.py   # Cầu nối Đồng bộ Video <-> Timeline
│   │   ├── timeline_state.py         # Quản lý Máy trạng thái FSM (Idle, Moving, ...)
│   │   └── timeline_undo_manager.py  # Quản lý Ngăn xếp Undo/Redo
│   ├── timing/                       # Thuật toán Timing & VAD Batching
│   │   ├── timing_batch_service.py
│   │   └── timing_checkpoint.py
│   ├── waveform/                     # Dịch vụ Trích xuất Sóng âm Background
│   │   └── waveform_service.py
│   ├── Backend.py                    # Whisper/VAD Engine Core
│   ├── queue_manager.py              # Quản lý danh sách hàng đợi Video
│   ├── subtitle_controller.py        # Bộ điều khiển lớp phụ đề Overlay
│   └── subtitle_exporter.py          # Dịch vụ xuất file SRT, VTT, TXT
├── installer/                        # Kịch bản đóng gói & Tạo file cài đặt Setup
│   └── setup_script.iss
├── player/                           # Thành phần Video Player (QGraphicsView)
│   ├── subtitle_overlay.py
│   └── video_player.py
├── tests/                            # Bộ kiểm thử Tự động (Automated Test Suite)
│   └── test_timeline.py              # Kiểm thử Snapshot, Exact-state, Undo/Redo
├── ui/                               # Giao diện Người dùng PySide6 (Qt6)
│   ├── animations/                   # Động cơ Diễn họa Chữ Phụ đề
│   ├── components/                   # Custom UI Components (AnimatedStack, Toast)
│   ├── dialogs/                      # Hộp thoại Dự án Mới, Model Manager
│   ├── pages/                        # Các Surface: Dashboard, Settings, Export, Drafts
│   ├── timeline/                     # Các Widget Vẽ Timeline, Waveform, Ruler, Track
│   │   ├── playhead.py
│   │   ├── subtitle_track.py         # Vẽ khối phụ đề + text trực tiếp
│   │   ├── timeline_container.py
│   │   ├── timeline_ruler.py
│   │   ├── timeline_widget.py
│   │   └── waveform_view.py
│   ├── Gui.py                        # Cửa sổ Chính & Điều phối Sự kiện Toàn cục
│   ├── queue_widget.py
│   ├── SubEditor.py                  # Bảng Biên tập Phụ đề Dạng Lưới
│   └── theme.py                      # Hệ thống Bảng màu Cyber Dark Theme
├── workers/                          # Background Worker Threads
│   └── TaskQueue.py                  # WhisperWorker, HardsubWorker, FillTextWorker
├── requirements.txt                  # Danh sách thư viện Python
└── README.md                         # Tài liệu hướng dẫn sử dụng

```

---

## 🔄 Quy trình làm việc (Workflows)

### 1. Quy trình Timing-First & Điền chữ AI (Khuyến nghị)

```text
[Tạo / Mở Dự Án] ──► [Nạp Video vào Queue] ──► [Chọn Mode: Timing Only]
                                                        │
┌───────────────────────────────────────────────────────┘
▼
[AI VAD bóc tách các khối thời gian rỗng]
│
├─► [Kiểm tra Waveform & Nắn chỉnh Timeline] (Cắt: Ctrl+T | Gộp: Ctrl+M | Di chuyển)
│
├─► [Nhấn "Chốt Timing"] (Đồng bộ mốc thời gian hoàn tất)
│
├─► [Tab AI Actions: Chọn Batch 5-10 dòng] ──► [Bấm "Tiếp tục từ câu..."]
│                                                        │
├─► [AI tự động nghe và điền chữ vào khung đã nắn] ◄────┘
│
└─► [Nhấn "Ctrl + S"] (Lưu đè file SRT/Draft và cấu hình Project)

```

### 2. Quy trình Xuất xưởng & Render Hardsub

* **Xuất Phụ đề Mềm (Softsub)**: Chuyển sang `Export Center` -> Chọn định dạng (`SRT`, `VTT`, `TXT`) -> Bấm **Export Subtitles**.
* **Kết xuất Phụ đề Cứng (Hardsub)**: Thiết lập Style chữ -> Bấm **Burn Hardsub Video** -> FFmpeg sẽ tiến hành encode video với hiệu năng tối đa mà không gây khóa giao diện.

---

## 🧪 Kiểm thử tự động (Automated Testing)

Dự án tích hợp bộ kiểm thử đơn vị (`unittest`) nhằm đảm bảo tính toàn vẹn của dữ liệu và hệ thống lệnh Snapshot Undo/Redo.

Chạy kiểm thử từ thư mục gốc:

```bash
python -m unittest tests/test_timeline.py -v

```

**Các kịch bản kiểm thử trọng tâm:**

* `test_01_move_undo_redo_exact_state`: Xác minh lệnh di chuyển giữ nguyên dữ liệu tuyệt đối qua các chu kỳ Undo/Redo.
* `test_02_split_structural_integrity`: Xác minh lệnh cắt sinh ra khối mới và xóa sạch khối rác khi hoàn tác.
* `test_03_merge_text_and_timing_integrity`: Xác minh tính toàn vẹn của văn bản nối và mốc thời gian sau khi gộp.
* `test_04_delete_restoration`: Xác minh khả năng phục hồi nguyên trạng khối bị xóa.
* `test_05_revision_failure_rollback`: Kiểm tra tính nguyên tử (Atomic Fail), tự động hủy lệnh nếu Artifact bị ngắt kết nối.

---

## 🛠️ Xử lý sự cố thường gặp (Troubleshooting)

### 1. Timeline không hiển thị sóng âm

* **Nguyên nhân**: File video không chứa luồng âm thanh hoặc định dạng audio không tương thích.
* **Khắc phục**: Kiểm tra thông số video trên Dashboard. Ứng dụng sẽ tự động bỏ qua tính năng sóng âm và hiển thị thông báo an toàn nếu không tìm thấy Audio Track.

### 2. Lỗi `CUDA out of memory` khi chạy AI

* **Nguyên nhân**: Dung lượng VRAM trên GPU không đủ để chứa Model kích thước lớn cùng lúc với video player.
* **Khắc phục**: Vào `Settings Center` -> Chuyển `Compute Type` từ `float16` sang `int8` hoặc đổi `Model Size` sang `medium` / `small`.

### 3. Thao tác Undo/Redo không phản hồi

* **Nguyên nhân**: Con trỏ chuột hoặc Focus đang nằm ngoài vùng làm việc.
* **Khắc phục**: Nhấp chuột vào dải Timeline hoặc Bảng phụ đề để kích hoạt Focus, sau đó sử dụng tổ hợp phím `Ctrl+Z` / `Ctrl+Shift+Z`.

---

<div align="center">

**🌟 Đừng quên star repository nếu bạn thấy dự án hữu ích!**

* [x] **Sprint 1 - 5**: Khởi tạo Core Whisper, Subtitle Overlay, Batch Queue, Timestamp-First Architecture & Quản lý Thư mục Output.
* [x] **Sprint 6**: Quản lý Vòng đời Artifacts (`.ai-subtitle-draft`) & Chế độ Điền chữ AI trên RAM.
* [x] **Sprint 7**: Kiến trúc Dự án Độc lập (`.ai-subtitle`), Quản lý Checkpoint & Tự động Khôi phục Workspace.
* [x] **Sprint 8**: Trục thời gian Phi tuyến tính (Interactive Waveform Timeline), Snapshot Undo/Redo, Bố cục DAW 3-Tier Layout & Bộ Test Suite Core Integrity.
* [ ] **Sprint 9**: Tối ưu hóa Bộ nhớ RAM khi Streaming Audio Video siêu dài (>5 tiếng), Trình quản lý Tải Model AI (`ModelManagerDialog`) & Hiệu ứng Chữ theo từng từ (Word-level Timing / Karaoke ASS).

---

## 📝 Ghi chú bổ sung

Phần mềm được phát hành dưới giấy phép **MIT License**.

1. **Cấu trúc rõ ràng**: Mục lục, các phần được phân tách logic
2. **Badge trực quan**: Hiển thị trạng thái công nghệ sử dụng
3. **Hướng dẫn chi tiết**: Cài đặt, đóng gói, cấu trúc thư mục
4. **Mã nguồn mẫu**: Các lệnh terminal được định dạng rõ ràng
5. **Bảng biểu**: Dễ đọc cho phím tắt và yêu cầu hệ thống
6. **ASCI diagram**: Minh họa giao diện trực quan
7. **Roadmap checklist**: Theo dõi tiến độ phát triển
8. **Phần đóng góp**: Khuyến khích cộng đồng tham gia

**Made with ❤️ for Content Creators, Translators & Video Editors**
