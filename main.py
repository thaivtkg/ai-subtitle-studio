
import os

# Tắt cảnh báo và telemetry từ Hugging Face Hub
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"  # Chỉ in khi có lỗi thực sự

import ctypes
import sys

from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.runtime.runtime_paths import RuntimePaths
# Import MainWindow từ thư mục ui
from ui.Gui import MainWindow
#from utils import resource_path    


def main():
    # --- THÊM ĐOẠN CODE NÀY ĐỂ FIX ICON TASKBAR TRÊN WINDOWS ---
    if os.name == 'nt':
        myappid = 'aisubtitlestudio.v0.1.alpha' # Một chuỗi ID định danh tùy ý
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    # -----------------------------------------------------------
    # Khởi tạo ứng dụng

    # 0. Khởi tạo toàn bộ cấu trúc thư mục Dữ liệu Người dùng ngay khi app mở
    RuntimePaths.ensure_user_data_dirs()

    if os.name == 'nt':
        myappid = 'aisubtitlestudio.v0.1.alpha' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication(sys.argv)

    # --- CHỈNH SỬA TẠI ĐÂY: Sử dụng RuntimePaths load icon ---
    icon_path = str(RuntimePaths.get_resources_dir() / "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    # ----------------------------------------------------

    
    # Thiết lập Stylesheet toàn cục (QMessageBox) chuyển từ file Gui cũ sang
    global_stylesheet = """
        QMessageBox { 
            background-color: #1E232E; /* Ép nền hộp thoại thành màu tối */
        }
        QMessageBox QLabel { 
            color: #FFFFFF; /* Chữ màu trắng */
            font-size: 14px; 
            background-color: transparent; /* Loại bỏ màu nền thừa của Windows */
        }
        QMessageBox QPushButton { 
            background-color: #283548; 
            color: #FFFFFF; 
            border: 1px solid #3A475C; 
            border-radius: 4px; 
            padding: 6px 20px; 
            font-weight: bold; 
        }
        QMessageBox QPushButton:hover { 
            background-color: #35C8FF; 
            color: #0D111A; 
        }
/* --- THÊM ĐOẠN NÀY ĐỂ FIX LỖI CẢNH BÁO FONT --- */
        QComboBox {
            font-size: 13px; /* Ép cứng kích thước chữ > 0 */
        }
        QComboBox QAbstractItemView {
            font-size: 14px; /* Ép cứng kích thước chữ cho danh sách xổ xuống */
        }
/* =========================================
           1. NÚT PRIMARY (Gradient - Start Batch)
           ========================================= */
        QPushButton#btn_primary {
            background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #4AC1FF, stop: 1 #8A75FF);
            color: #FFFFFF;
            font-weight: bold;
            border-radius: 6px;
            border: none;
            padding: 8px 16px;
        }
        QPushButton#btn_primary:hover {
            /* Sáng lên một chút khi lướt chuột */
            background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #6CD0FF, stop: 1 #9E8DFF);
        }
        QPushButton#btn_primary:pressed {
            /* Tối đi và lõm xuống khi click */
            background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #3399D4, stop: 1 #6854CC);
            padding-top: 10px; /* padding gốc 8px + 2px lõm = 10px */
            padding-bottom: 6px;
        }

        /* =========================================
           2. NÚT DANGER (Đỏ - Cancel, X)
           ========================================= */
        QPushButton#btn_danger {
            background-color: #FF1F1F;
            color: #FFFFFF;
            font-weight: bold;
            border-radius: 6px;
            border: none;
            padding: 8px 16px;
        }
        QPushButton#btn_danger:hover {
            background-color: #FF758F; /* Sáng hơn */
        }
        QPushButton#btn_danger:pressed {
            background-color: #D6425C; /* Tối hơn */
            padding-top: 10px;
            padding-bottom: 6px;
        }

        /* =========================================
           3. NÚT SECONDARY (Tối màu - Browse, Mở thư mục)
           ========================================= */
        QPushButton#btn_secondary {
            background-color: #2B3547;
            color: #FFFFFF;
            font-weight: bold;
            border-radius: 6px;
            border: 1px solid #1E2532;
            padding: 8px 16px;
        }
        QPushButton#btn_secondary:hover {
            background-color: #38455A; /* Sáng hơn một tông */
            border: 1px solid #4AC1FF; /* Viền sáng lên màu xanh */
        }
        QPushButton#btn_secondary:pressed {
            background-color: #1A212E; /* Chìm xuống */
            border: 1px solid #1A212E;
            padding-top: 10px;
            padding-bottom: 6px;
        }
    """
    app.setStyleSheet(app.styleSheet() + global_stylesheet)



    # Khởi tạo và hiển thị giao diện chính
    window = MainWindow()
    window.show()

    # Chạy vòng lặp sự kiện
    sys.exit(app.exec())

def suppress_qt_warnings(mode, context, message):
    # Nếu log là cảnh báo (Warning) và chứa dòng chữ QFont::setPointSize, lờ nó đi
    if mode == QtMsgType.QtWarningMsg and "QFont::setPointSize" in message:
        return
    # Nếu là lỗi khác, vẫn có thể in ra bình thường (tùy chọn)
        print(message)

if __name__ == "__main__":
    qInstallMessageHandler(suppress_qt_warnings)
    main()
