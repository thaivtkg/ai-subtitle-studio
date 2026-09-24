# 🎬 AI Subtitle Studio

> **Hệ thống Tạo Phụ đề Tự động, Biên tập Dạng sóng âm (Waveform/Timeline) & Render Hardsub Video chuẩn NLE Chuyên nghiệp.**

---

## 📌 Mục lục

1. [Giới thiệu](#-giới-thiệu)
2. [Tính năng cốt lõi](#-tính-năng-cốt-lõi)
3. [Bảng Phím tắt Toàn cục (Shortcuts)](#-bảng-phím-tắt-toàn-cục-shortcuts)
4. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
5. [Hướng dẫn cài đặt & Chạy mã nguồn](#-hướng-dẫn-cài-đặt--chạy-mã-nguồn)
6. [Đóng gói & Tạo bộ cài đặt Windows (Installer)](#-đóng-gói--tạo-bộ-cài-đặt-windows-installer)
7. [Xử lý sự cố thường gặp (Troubleshooting)](#-xử-lý-sự-cố-thường-gặp-troubleshooting)

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

* 🎬 **Xuất xưởng Đa Định dạng & Render Hardsub GPU/CPU**
  * Xuất file phụ đề mềm: `.srt`, `.vtt`, `.txt`.
  * Kết xuất Hardsub trực tiếp vào video thông qua FFmpeg chạy nền, hiển thị đầy đủ tiến độ, tốc độ render (Speed x) và thời gian dự tính (ETA).

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

- `requirements.txt`: bộ dependency nền linh hoạt cho môi trường chạy mã nguồn.
- `requirements-runtime.txt`: profile nền thay thế, ghim phiên bản để tạo runtime/CI reproducible; hiện dùng PyTorch CUDA 12.1.
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

## 🛠️ Đóng gói & Tạo bộ cài đặt Windows (Installer)

### 1. Đóng gói mã nguồn thành File thực thi (`PyInstaller`)


```powershell
.\scripts\build_windows.ps1

```

### 2. Tạo File Setup Cài đặt (`Inno Setup`)

1. Cài đặt công cụ [Inno Setup 6+](https://jrsoftware.org/).
2. Chạy `scripts/build_windows.ps1`; script sẽ gọi `installer/setup.iss` nếu Inno Setup đã được cài.
3. File cài đặt được xuất vào thư mục `release/`.

## 📄 Giấy phép

Phần mềm được phát hành dưới giấy phép **MIT License**.

**Made with ❤️ for Content Creators, Translators & Video Editors**
