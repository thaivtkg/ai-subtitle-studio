# 🎬 AI Subtitle Studio

> **Hệ thống tạo phụ đề tự động, biên tập Waveform/Timeline và render Hardsub Video theo quy trình NLE chuyên nghiệp.**

AI Subtitle Studio là ứng dụng Windows viết bằng Python và PySide6, tập trung vào quy trình **Timestamp-First**: xác định và chỉnh sửa mốc thời gian trước, sau đó mới chạy nhận dạng giọng nói để sinh nội dung phụ đề.

## 📌 Mục lục

1. [Tính năng](#-tính-năng)
2. [Kiến trúc giao diện](#-kiến-trúc-giao-diện)
3. [Bắt đầu nhanh](#-bắt-đầu-nhanh)
4. [Quy trình sử dụng](#-quy-trình-sử-dụng)
5. [Batch Mode](#-batch-mode)
6. [Dự án và Artifact](#-dự-án-và-artifact)
7. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
8. [Cài đặt dependency](#-cài-đặt-dependency)
9. [Đóng gói Windows](#-đóng-gói-windows)
10. [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
11. [Kiểm thử](#-kiểm-thử)
12. [Xử lý sự cố](#-xử-lý-sự-cố)
13. [Lộ trình](#-lộ-trình)

## 🚀 Tính năng

- **Full Subtitle (Whisper ASR)**: nhận dạng giọng nói bằng Faster-Whisper và sinh phụ đề theo từng Batch.
- **Timing Draft (VAD Only)**: chỉ phát hiện vùng có tiếng nói bằng VAD để tạo các khối thời gian rỗng; không nạp Whisper.
- **Hai cách chia Batch**:
  - `Time-based`: chia theo số phút, phù hợp với video dài và kiểm soát VRAM.
  - `Segment-based`: chia theo số câu thực tế từ Timing Artifact đã hoàn tất.
- **Overlap và Reconciler**: các Batch có vùng chồng lấn để tránh cắt mất từ ở ranh giới; Reconciler loại bỏ câu trùng.
- **Timestamp shifting**: timestamp local từ Whisper được dịch về timeline tuyệt đối của video.
- **Checkpoint/Resume**: lưu tiến độ sau từng Batch, hỗ trợ tiếp tục sau khi hủy hoặc ứng dụng gặp sự cố.
- **Commit nguyên tử**: Artifact JSON và Checkpoint được ghi qua file tạm rồi `os.replace` để tránh file dở dang.
- **Realtime Sync**: phụ đề của Batch vừa hoàn tất được cập nhật ngay lên Editor, Video Player và Timeline.
- **Hallucination filter**: loại các kết quả rác phổ biến như `Transcription by CastingWords` hoặc `Amara.org`.
- **Interactive Waveform/Timeline**: di chuyển, co giãn, cắt, gộp, xóa và Undo/Redo các khối phụ đề.
- **Xuất phụ đề**: hỗ trợ SRT, VTT, TXT và render Hardsub thông qua FFmpeg.
- **Queue Manager**: xử lý nhiều video tuần tự; video kéo-thả khi chưa có Project sẽ được tự động tạo Project nền.

## 🖥️ Kiến trúc giao diện

Workspace chính được tổ chức theo ba vùng:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ TẦNG 1: VIDEO PREVIEW                                                │
│ Video Player · Subtitle Overlay · Play/Pause · Seek · Volume         │
├─────────────────────────────────────────────┬────────────────────────┤
│ TẦNG 2A: SUBTITLE EDITOR                    │ TẦNG 2B: DOCK PANEL     │
│ Bảng STT · Start · End · Text               │ Generate Subtitle       │
│                                             │ Live Log                │
├─────────────────────────────────────────────┴────────────────────────┤
│ TẦNG 3: TIMELINE & WAVEFORM                                           │
│ Ruler · Audio Peaks · Subtitle Blocks · Playhead                       │
└──────────────────────────────────────────────────────────────────────┘
```

Panel **Generate Subtitle** là `QDockWidget`, có thể kéo, dock, float hoặc đóng. Central Widget có kích thước tối thiểu để Workspace không bị co về 0 khi Dock được float.

### Phím tắt

| Phím tắt | Phạm vi | Chức năng |
| --- | --- | --- |
| `Ctrl + N` | Toàn ứng dụng | Tạo Project mới |
| `Ctrl + O` | Toàn ứng dụng | Mở Project có sẵn |
| `Ctrl + S` | Toàn ứng dụng | Lưu Project, cấu hình và dữ liệu Timeline |
| `Space` | Video Player | Phát / tạm dừng video |
| `Ctrl + T` | Timeline | Split tại vị trí Playhead |
| `Ctrl + M` | Timeline | Merge các khối đang chọn |
| `Delete` | Timeline | Xóa khối đang chọn |
| `Ctrl + Z` | Timeline | Undo |
| `Ctrl + Shift + Z` | Timeline | Redo |

## 📦 Bắt đầu nhanh

### 1. Lấy mã nguồn

Thay `<repository-url>` bằng URL repository thực tế của dự án:

```powershell
git clone <repository-url>
cd ai-subtitle-studio
```

### 2. Tạo môi trường ảo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Nếu PowerShell chặn script activation, có thể chạy trực tiếp Python trong `.venv` hoặc dùng Command Prompt:

```bat
.venv\Scripts\activate.bat
```

### 3. Cài dependency

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Chuẩn bị FFmpeg

Đặt hai file sau trong thư mục `ffmpeg/` ở thư mục gốc dự án:

```text
ffmpeg/ffmpeg.exe
ffmpeg/ffprobe.exe
```

Ứng dụng cũng có thể dùng `ffmpeg` và `ffprobe` có sẵn trong `PATH`. Có thể tải bản Windows từ [ffmpeg.org](https://ffmpeg.org/) hoặc [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).

### 5. Chạy ứng dụng

```powershell
python main.py
```

`main.py` là entrypoint khuyến nghị vì nó thiết lập runtime path, icon và cấu hình Qt trước khi mở `MainWindow`.

## 🔄 Quy trình sử dụng

1. Tạo Project mới bằng `Ctrl + N`, mở Project bằng `Ctrl + O`, hoặc kéo video vào Queue.
2. Chọn video trong Queue. Nếu chưa có Project, ứng dụng tự tạo thư mục `.ai-subtitle` cho video.
3. Mở Dock **Generate Subtitle**.
4. Chọn một trong hai chế độ:
   - **Timing Draft (VAD Only)** để tạo khối thời gian rỗng.
   - **Full Subtitle (Whisper ASR)** để nhận dạng và điền nội dung.
5. Chọn Batch Mode, Batch Size và các tùy chọn VAD/Word Timestamps.
6. Nhấn **Generate**. Kết quả được ghi từng Batch và hiển thị realtime.
7. Kiểm tra/chỉnh sửa trên Editor và Timeline.
8. Xuất SRT/VTT/TXT hoặc render Hardsub từ Export Center.

Khi nhấn **Cancel**, Batch đang chạy sẽ dừng an toàn sau khi Worker kết thúc. Nút **Resume** chỉ được mở lại khi luồng cũ đã thực sự kết thúc, tránh lỗi chạy trùng generation.

## ⏱️ Batch Mode

### Time-based

Ví dụ video dài 10 phút, Batch Size là 5 phút và overlap là 2 giây:

```text
Batch 1: 00:00.000 → 05:02.000
Batch 2: 05:00.000 → 10:00.000
```

Đây là chế độ mặc định của Queue và phù hợp để kiểm soát bộ nhớ trên GPU có VRAM thấp.

### Segment-based

Chế độ này yêu cầu Project đã có Timing Artifact. Planner gom các khoảng thời gian thật theo số câu trong Timing Draft:

```text
Timing segments 1–10 → Batch 1
Timing segments 11–20 → Batch 2
```

Nếu chưa có Timing Artifact, UI chỉ cho phép `Time-based`. `overlap_ms` mở rộng vùng thời gian quanh mỗi nhóm để Whisper có thêm ngữ cảnh; Boundary Reconciler chịu trách nhiệm loại bỏ segment trùng.

## 📁 Dự án và Artifact

Mỗi Project có dạng thư mục độc lập:

```text
<project-name>.ai-subtitle/
├── project.json
└── artifacts/
    ├── subtitle/
    │   └── <artifact-id>.sub.json
    ├── subtitle_generation/
    │   └── checkpoint.json
    └── timing/
        ├── <name>_timing.srt
        └── checkpoint.json
```

File `.sub.json` là **canonical subtitle artifact**, không phải file SRT trung gian:

```json
{
  "version": 1,
  "segments": [
    {
      "id": "segment-id",
      "start_ms": 0,
      "end_ms": 2000,
      "text": "Hello",
      "words": [],
      "status": "generated"
    }
  ]
}
```

UI dùng dữ liệu canonical này để cập nhật realtime. File `_shadow.srt` chỉ là bản xuất tạm phục vụ các thành phần hiện đang nhận input SRT; người dùng nên xuất SRT chính thức từ Export Center.

## 💻 Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị |
| --- | --- | --- |
| Hệ điều hành | Windows 10/11 64-bit | Windows 11 64-bit |
| Python | 3.10 | 3.10.x hoặc 3.11.x |
| RAM | 8 GB | 16 GB trở lên |
| GPU | Không bắt buộc, chạy CPU | NVIDIA GPU từ 4 GB VRAM |
| CUDA/cuDNN | Theo bản PyTorch cài đặt | CUDA/cuDNN tương thích |
| Dung lượng trống | 5 GB | 15 GB trở lên |

Model Whisper được tải về khi cần và có thể chiếm thêm dung lượng. Với GPU 4 GB VRAM, nên dùng model nhỏ hơn và `int8`; GPU 8 GB có thể dùng cấu hình lớn hơn tùy video và model.

## 📚 Cài đặt dependency

`requirements.txt` hiện bao gồm các dependency chính:

- `PySide6`: giao diện Qt6.
- `faster-whisper`: nhận dạng giọng nói.
- `torch`, `torchaudio`: runtime xử lý audio/model.
- `numpy`: dữ liệu waveform.
- `psutil`: thông tin tài nguyên hệ thống.

`requirements-runtime.txt` chứa bộ phiên bản đã ghim cho môi trường runtime cụ thể. Chỉ dùng file này khi máy triển khai cần tái tạo đúng bộ phiên bản runtime đã kiểm thử.

## 🛠️ Đóng gói Windows

### PyInstaller

Lệnh mẫu cho bản onedir:

```powershell
pyinstaller --noconfirm --onedir --windowed `
    --name "AI Subtitle Studio" `
    --add-data "ffmpeg;ffmpeg" `
    --add-data "resources;resources" `
    --collect-all faster_whisper `
    main.py
```

Trên Command Prompt, thay ký tự nối dòng PowerShell `` ` `` bằng `^`.

Sau khi build, kiểm tra thư mục `dist/` có executable, `ffmpeg/`, `resources/` và các thư viện Faster-Whisper cần thiết.

### Inno Setup

1. Build PyInstaller trước.
2. Mở [installer/setup.iss](installer/setup.iss) bằng Inno Setup 6+.
3. Kiểm tra `OutputDir` và tên thư mục `dist` khớp với bản build.
4. Nhấn **Compile** hoặc `Ctrl + F9`.

Bộ cài đặt được xuất vào thư mục `release/` theo cấu hình trong `setup.iss`.

## 📂 Cấu trúc thư mục

```text
ai-subtitle-studio/
├── core/
│   ├── artifacts/                    # Artifact và ArtifactStore
│   ├── project/                      # Project và ProjectState
│   ├── services/                     # Project/Workspace services
│   ├── subtitle_generation/          # Whisper, Planner, Validator, Checkpoint
│   │   ├── faster_whisper_service.py
│   │   ├── generation_planner.py
│   │   ├── generation_service.py
│   │   ├── generation_validator.py
│   │   ├── subtitle_artifact_service.py
│   │   ├── subtitle_generation_request.py
│   │   └── subtitle_generation_result.py
│   ├── timing/                       # Timing Draft và VAD batching
│   ├── timeline/                     # Timeline commands, provider, undo/redo
│   ├── waveform/                     # Trích xuất audio peaks
│   ├── queue_manager.py              # Quản lý Queue video
│   └── subtitle_exporter.py          # Xuất SRT/VTT/TXT
├── ffmpeg/                           # ffmpeg.exe và ffprobe.exe
├── installer/                        # Cấu hình Inno Setup
├── player/                           # Video Player và Subtitle Overlay
├── resources/                        # Icon và tài nguyên UI
├── tests/                            # Unit/Integration tests
├── ui/
│   ├── Gui.py                        # MainWindow và điều phối sự kiện
│   ├── subtitle_generation_panel.py  # Panel ASR/Timing/Batch
│   ├── SubEditor.py                  # Subtitle Editor
│   └── timeline/                     # Timeline widgets
├── workers/
│   ├── subtitle_generation_worker.py # Worker một Batch Whisper
│   ├── TimingBatchWorker.py          # Worker Timing/VAD
│   └── TaskQueue.py                  # Hardsub và tác vụ Queue khác
├── main.py                           # Entrypoint khuyến nghị
├── requirements.txt
└── README.md
```

## 🧪 Kiểm thử

Chạy toàn bộ test từ thư mục gốc:

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

Chạy riêng các nhóm test:

```powershell
python -m unittest tests/test_subtitle_generation.py -v
python -m unittest tests/test_timeline.py -v
```

Các kịch bản quan trọng gồm:

- Planner Time-based và Segment-based.
- Request lưu đúng Batch Mode.
- Atomic Artifact/Checkpoint commit.
- Resume bỏ qua Batch đã hoàn tất.
- Cancel không commit Batch dở dang.
- Source fingerprint và Artifact revision stale guard.
- Boundary Reconciliation chống trùng subtitle.
- Hallucination filter của Whisper.
- Undo/Redo và tính toàn vẹn Timeline.

## 🛠️ Xử lý sự cố

### Không tìm thấy FFmpeg

Kiểm tra `ffmpeg/ffmpeg.exe`, `ffmpeg/ffprobe.exe` hoặc thêm FFmpeg vào `PATH`. Khởi động lại ứng dụng sau khi thay đổi.

### CUDA out of memory

Giảm `Model Size`, chuyển `Compute Type` sang `int8`, giảm Batch Size hoặc dùng `Time-based` với Batch ngắn hơn. Không chạy đồng thời nhiều generation worker.

### Không thấy phụ đề sau khi Batch hoàn tất

Kiểm tra tab **Live Log**, file `.sub.json` và `_shadow.srt` trong `artifacts/subtitle/`. Nếu Artifact bị sửa ngoài ứng dụng, Checkpoint có thể bị đánh dấu stale để bảo vệ dữ liệu.

### Resume báo đang chạy

Chờ Worker kết thúc hẳn sau khi nhấn **Cancel**. UI chỉ bật **Resume** sau khi QThread đã phát tín hiệu kết thúc; không nhấn Generate lại trong thời gian đang hiện `Cancelling...`.

### Timeline không có waveform

Video có thể không có audio stream hoặc FFmpeg không đọc được codec. Kiểm tra log và thử mở video bằng FFmpeg/ffprobe độc lập.

### Model tải chậm ở lần chạy đầu

Faster-Whisper cần tải model về máy. Đảm bảo có Internet và đủ dung lượng; các lần chạy sau sẽ dùng model đã cache.

## 🗺️ Lộ trình

- [x] Timestamp-First architecture và Project độc lập `.ai-subtitle`.
- [x] Waveform/Timeline tương tác, Snapshot Undo/Redo.
- [x] Timing Draft với VAD và Checkpoint.
- [x] Subtitle Generation với Faster-Whisper, Time-based và Segment-based batching.
- [x] Atomic Artifact, Reconciler, timestamp shifting và realtime UI sync.
- [x] Queue generation tuần tự và Cancel/Resume an toàn.
- [ ] Tối ưu streaming audio cho video siêu dài trên nhiều cấu hình GPU.
- [ ] Mở rộng cấu hình model và preset VRAM tự động.
- [ ] Cải thiện Word-level Timing/Karaoke export.

## 📄 Giấy phép

Phần mềm được phát hành theo giấy phép **MIT License**.

**Made with ❤️ for Content Creators, Translators & Video Editors**
