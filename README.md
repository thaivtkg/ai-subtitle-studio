# 🎬 AI Subtitle Studio

> **Hệ thống Tạo Phụ đề Tự động, Biên tập Thời gian thực & Render Hardsub Video chuẩn xác cao.**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![UI Framework](https://img.shields.io/badge/PySide6-Qt6-green.svg)](https://pypi.org/project/PySide6/)
[![AI Engine](https://img.shields.io/badge/Faster--Whisper-Large--v3--Turbo-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Video Processing](https://img.shields.io/badge/FFmpeg-6.0%2B-red.svg)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](#)

---

## 📌 Mục lục
1. [Giới thiệu](#-giới-thiệu)
2. [Tính năng cốt lõi](#-tính-năng-cốt-lõi)
3. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
4. [Hướng dẫn cài đặt](#-hướng-dẫn-cài-đặt)
   - [Bước 1: Clone mã nguồn](#bước-1-clone-mã-nguồn)
   - [Bước 2: Tạo môi trường ảo](#bước-2-tạo-môi-trường-ảo)
   - [Bước 3: Cài đặt thư viện](#bước-3-cài-đặt-thư-viện)
   - [Bước 4: Cấu hình FFmpeg](#bước-4-cấu-hình-ffmpeg)
   - [Bước 5: Cấu hình tăng tốc GPU (CUDA)](#bước-5-cấu-hình-tăng-tốc-gpu-cuda)
5. [Cấu trúc thư mục dự án](#-cấu-trúc-thư-mục-dự-án)
6. [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
7. [Xử lý sự cố thường gặp (Troubleshooting)](#-xử-lý-sự-cố-thường-gặp-troubleshooting)
8. [Lộ trình phát triển (Roadmap)](#-lộ-trình-phát-triển-roadmap)

---

## 📖 Giới thiệu

**AI Subtitle Studio** là giải pháp phần mềm chuyên dụng trên desktop dành cho dịch thuật viên, nhà sáng tạo nội dung và biên tập viên video. Ứng dụng kết hợp sức mạnh nhận diện giọng nói siêu tốc của **Faster-Whisper** với công cụ render mạnh mẽ của **FFmpeg**, gói gọn trong một giao diện Dark Theme hiện đại bằng **PySide6**.

Ứng dụng tiên phong áp dụng kiến trúc **Timestamp-First / Timing Artifact**, cho phép người dùng bóc tách và tinh chỉnh khung thời gian trước khi nhận diện nội dung văn bản.

---

## 🚀 Tính năng cốt lõi

* ⚡ **Nhận diện giọng nói AI tốc độ cao:** Tích hợp mô hình `large-v3-turbo` qua `faster-whisper`, hỗ trợ lọc khoảng lặng thông minh bằng Silero VAD.
* 🕒 **Kiến trúc Timing Draft (Timestamp-First):** Tạo khung phụ đề rỗng chỉ gồm mốc thời gian (`[ Chưa có nội dung ]`), phục vụ kiểm duyệt nhịp điệu cắt câu trước khi sinh text.
* 🎨 **Trình biên tập phụ đề & Live Video Overlay:** - Xem trước phụ đề ngay trên video player với viền chữ nổi sắc nét.
  - Chỉnh sửa trực tiếp trên bảng dữ liệu, tự động đồng bộ thời gian thực (Live Sync).
  - Tùy biến toàn diện: Font chữ, Cỡ chữ, Màu sắc, Độ dày viền (Stroke) và Vị trí (Top/Center/Bottom).
* 🎬 **Render Hardsub không giật lag (Non-blocking UI):** Luồng FFmpeg chạy ngầm độc lập, đo đạc tốc độ xử lý (FPS, Speed x, ETA) và mức tiêu thụ phần cứng (CPU/GPU).
* 🗂️ **Hàng đợi Batch Processing thông minh:**
  - Tự động bỏ qua xác nhận đối với video đã có sẵn SRT.
  - Cơ chế **Failure Recovery**: Một video lỗi không làm dừng cả hàng đợi.
  - Tự động kiểm tra luồng âm thanh (Pre-check Audio) ngăn chặn lỗi sập Backend.
* 📁 **Quản lý thư mục đầu ra tự động (Output-centric):**
  - Tự động phân cấp: `/Output/subtitles/` (SRT, VTT, TXT) và `/Output/hardsub/` (Video MP4).
  - Làm sạch đường dẫn (Clean Path), an toàn tuyệt đối với hệ điều hành Windows.

---

## 💻 Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu | Khuyến nghị |
| :--- | :--- | :--- |
| **Hệ điều hành** | Windows 10 / 11 (64-bit) | Windows 11 (64-bit) |
| **Python** | Python 3.10 | Python 3.10.x hoặc 3.11.x |
| **RAM** | 8 GB RAM | 16 GB RAM trở lên |
| **GPU** | Không bắt buộc (chạy CPU) | NVIDIA GPU (>= 4GB VRAM, GTX 1650 trở lên) |
| **CUDA / cuDNN** | CUDA 11.8 hoặc 12.x | cuDNN 8.x/9.x tương thích |
| **Dung lượng trống** | 5 GB SSD | 10 GB SSD |

---

## 📦 Hướng dẫn cài đặt

### Bước 1: Clone mã nguồn
Mở Terminal / Command Prompt hoặc PowerShell và gõ lệnh:
```bash
git clone [https://github.com/your-username/ai-subtitle-studio.git](https://github.com/your-username/ai-subtitle-studio.git)
cd ai-subtitle-studio
Bước 2: Tạo môi trường ảo (Virtual Environment)
Khuyến nghị tạo môi trường ảo độc lập để tránh xung đột thư viện:

Bash
# Tạo môi trường ảo với tên .venv
python -m venv .venv

# Kích hoạt môi trường ảo (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Hoặc kích hoạt trên Command Prompt (cmd)
.venv\Scripts\activate.bat
Bước 3: Cài đặt thư viện phụ thuộc
Tạo file requirements.txt (nếu chưa có) và cài đặt toàn bộ gói thư viện:

Bash
pip install --upgrade pip
pip install -r requirements.txt
Danh sách các thư viện chính trong requirements.txt:

Plaintext
PySide6>=6.5.0
faster-whisper>=1.0.0
psutil>=5.9.0
gputil>=1.4.0
torch>=2.0.0
ctranslate2>=3.20.0
Bước 4: Cấu hình FFmpeg
Tải bản build tĩnh của FFmpeg từ trang chủ: https://ffmpeg.org/download.html (hoặc gyan.dev).

Giải nén và copy 2 file thực thi vào thư mục bin/ trong dự án:

bin/ffmpeg.exe

bin/ffprobe.exe

Bước 5: Cấu hình tăng tốc GPU (CUDA)
Để sử dụng GPU NVIDIA cho mô hình Whisper:

Đảm bảo máy tính đã cài đặt NVIDIA Driver mới nhất.

Tải và cài đặt CUDA Toolkit 11.8 hoặc CUDA 12.x từ trang chủ NVIDIA.

Tải cuDNN tương thích, giải nén các file .dll vào thư mục bin/ của dự án hoặc đưa vào PATH hệ thống.

📂 Cấu trúc thư mục dự án
Plaintext
ai-subtitle-studio/
├── bin/                       # Chứa file thực thi FFmpeg / FFprobe
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── core/                      # Kiến trúc tầng Logic & Backend
│   ├── Backend.py             # Whisper Inference & FFmpeg Hardsub Core
│   ├── output_path_service.py # Quản lý cấu trúc thư mục Output
│   ├── subtitle_controller.py # Bộ điều phối đồng bộ thời gian Video & Editor
│   ├── subtitle_exporter.py   # Dịch vụ xuất file SRT / VTT / TXT
│   └── subtitle_model.py      # Data Model (Timing Artifact, SubtitleSegment)
├── player/                    # Video Player Components
│   ├── subtitle_overlay.py    # Lớp vẽ chữ phụ đề nổi trên video
│   └── video_player.py        # Widget Media Player (QGraphicsView)
├── ui/                        # Giao diện người dùng (PySide6)
│   ├── Gui.py                 # Cửa sổ chính & Điều phối Batch Queue
│   ├── hardsub_confirm_dialog.py # Hộp thoại xác nhận sau khi tạo SRT
│   ├── QueueManager.py        # Logic quản lý danh sách Video
│   ├── QueueUI.py             # Bảng giao diện hàng đợi
│   └── SubEditor.py           # Bảng biên tập & Preview Style phụ đề
├── utils/                     # Công cụ tiện ích hệ thống
│   └── resource_path.py       # Xử lý đường dẫn tài nguyên PyInstaller
├── workers/                   # Background Thread Workers
│   └── TaskQueue.py           # WhisperWorker & HardsubWorker
├── requirements.txt           # Danh sách thư viện Python
├── main.py                    # Điểm khởi chạy ứng dụng
└── README.md                  # Tài liệu hướng dẫn
🖥️ Hướng dẫn sử dụng
1. Khởi động ứng dụng
Bash
python main.py
2. Quy trình làm việc tiêu chuẩn (Standard Workflow)
Plaintext
[Thêm Video vào Queue]
          ↓
[Cấu hình Mô hình & Prompt]
          ↓
[Nhấn "Start Processing"]
          ↓
[AI tạo phụ đề (.srt)]
          ↓
┌───────────────────────────────────────────────┐
│ Hộp thoại Xác nhận:                            │
│ 1. Chèn Hardsub ngay ──► Render Video mới     │
│ 2. Chỉnh sửa Subtitle ──► Chuyển sang Editor  │
│ 3. Bỏ qua ─────────────► Giữ nguyên SRT       │
└───────────────────────────────────────────────┘
3. Tinh chỉnh trong Subtitle Editor
Chỉnh sửa Text/Time: Click đúp trực tiếp vào ô tương ứng trên bảng để sửa.

Seek video: Click đúp vào cột Bắt đầu để tua nhanh video đến đúng vị trí câu thoại.

Tùy biến Style: Thay đổi Font, Cỡ chữ, Màu sắc, Viền chữ ở bảng điều khiển bên phải. Thay đổi sẽ hiển thị ngay lập tức lên màn hình video.

Lưu thay đổi: Nhấn nút Lưu thay đổi (Ctrl+S) để cập nhật file SRT trên ổ đĩa.

🛠️ Xử lý sự cố thường gặp (Troubleshooting)
1. Lỗi FFmpeg: Error initializing filters / Invalid argument (4294967274)
Nguyên nhân: Đường dẫn file hoặc thư mục đầu ra chứa ký tự đặc biệt hoặc thư mục chưa được tạo trước.

Khắc phục: Hệ thống hiện tại đã tích hợp OutputPathService tự động chuyển đổi sang định dạng /. Hãy đảm bảo bạn không chọn thư mục bị khóa quyền Administrator (như C:\Program Files).

2. Lỗi tuple index out of range hoặc Crash khi nạp Video
Nguyên nhân: File video không chứa luồng âm thanh (No Audio Stream).

Khắc phục: Ứng dụng đã có bộ quét has_audio_stream(). Video không có tiếng sẽ được tự động bỏ qua an toàn mà không làm crash chương trình.

3. Không sử dụng được GPU (Tụt về CPU / Chạy chậm)
Nguyên nhân: Thiếu các file .dll của CUDA/cuDNN trong môi trường Python.

Khắc phục: Chạy lệnh kiểm tra trong Terminal:

Python
python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"
Nếu kết quả trả về 0, hãy cài đặt lại gói torch bản CUDA tương thích từ pytorch.org.
