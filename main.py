
import os

# Tắt cảnh báo và telemetry từ Hugging Face Hub
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"  # Chỉ in khi có lỗi thực sự

import ctypes
import sys
from dataclasses import replace

from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.runtime.runtime_paths import RuntimePaths
from core.runtime.single_instance_guard import IpcAction, IpcRequest, SingleInstanceGuard
from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.project.source_fingerprint import generate_source_info
from core.recovery.recovery_models import RecoveryContext
# Import MainWindow từ thư mục ui
Gui = None
def build_ipc_request(argv: list[str]) -> IpcRequest:
    if len(argv) < 2:
        return IpcRequest(IpcAction.ACTIVATE_WINDOW)
    path = os.path.abspath(argv[1])
    if os.path.isdir(path) and path.endswith(".ai-subtitle"):
        return IpcRequest(IpcAction.OPEN_PROJECT, path)
    return IpcRequest(IpcAction.OPEN_MEDIA, path)


def run_secondary_instance(guard: SingleInstanceGuard, argv: list[str]) -> int:
    return 0 if guard.relay_to_primary(build_ipc_request(argv)) else 1


def build_recovery_manager():
    undo_manager = GlobalUndoManager()
    tracker = RevisionTracker(undo_manager)
    manager = RecoveryManager(
        RuntimePaths.get_recovery_sessions_dir(),
        RuntimePaths.get_recovery_quarantine_dir(),
        tracker,
        AtomicSnapshotStore(),
        RecoveryValidator(),
    )
    return undo_manager, tracker, manager


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

    guard = SingleInstanceGuard()
    if not guard.try_acquire_primary():
        result = run_secondary_instance(guard, sys.argv)
        guard.close()
        return result
    guard.start_listening()
    undo_manager, revision_tracker, recovery_manager = build_recovery_manager()
    recovery_candidates = recovery_manager.scan_candidates()
    selected_candidate = recovery_candidates[0] if recovery_candidates else None
    recovered_state = None
    recovered_linked = True
    if selected_candidate is not None:
        candidate = selected_candidate
        source_info = None
        if candidate.manifest.video_path and os.path.exists(candidate.manifest.video_path):
            try:
                source_info = generate_source_info(candidate.manifest.video_path)
            except (OSError, ValueError):
                source_info = None
        validation = recovery_manager.validate_candidate(candidate, source_info)
        if not validation.is_valid:
            recovery_manager.discard_session(candidate.manifest.session_id)
            selected_candidate = None
        else:
            dialog_cls = None
            if validation.source_matches:
                from ui.dialogs.recovery_dialog import RecoveryDialog
                dialog_cls = RecoveryDialog
            else:
                from ui.dialogs.source_mismatch_dialog import SourceMismatchDialog
                dialog_cls = SourceMismatchDialog
                recovered_linked = False
            dialog = dialog_cls(
                candidate.manifest.session_id,
                candidate.manifest.project_id or candidate.manifest.project_file_path,
                candidate.manifest.created_at,
            )
            if dialog.exec() == 0:
                recovery_manager.discard_session(candidate.manifest.session_id)
                selected_candidate = None
            else:
                revision_tracker.restore_from_snapshot(
                    candidate.snapshot.edit_revision,
                    candidate.manifest.last_saved_revision,
                    candidate.manifest.last_clean_revision,
                )
                recovered_session = recovery_manager.handoff_recovered_state(
                    candidate,
                    candidate.snapshot,
                    RecoveryContext(
                        candidate.manifest.project_id,
                        candidate.manifest.project_file_path,
                        candidate.manifest.video_path,
                        candidate.manifest.source_fingerprint,
                        candidate.manifest.source_modified_at,
                        candidate.manifest.app_version,
                    ),
                )
                recovered_state = candidate.snapshot
                if not recovered_linked:
                    recovered_state = replace(recovered_state, video_path="")
                selected_candidate = None
    from ui import Gui as gui_module

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
    window = gui_module.MainWindow(
        revision_tracker=revision_tracker,
        recovery_manager=recovery_manager,
        undo_manager=undo_manager,
    )
    if recovered_state is not None:
        window.apply_recovery_working_state(recovered_state, linked=recovered_linked)
    guard.request_received.connect(window.handle_ipc_request)
    window.show()

    # Chạy vòng lặp sự kiện
    return app.exec()

def suppress_qt_warnings(mode, context, message):
    # Nếu log là cảnh báo (Warning) và chứa dòng chữ QFont::setPointSize, lờ nó đi
    if mode == QtMsgType.QtWarningMsg and "QFont::setPointSize" in message:
        return
    # Nếu là lỗi khác, vẫn có thể in ra bình thường (tùy chọn)
        print(message)

if __name__ == "__main__":
    qInstallMessageHandler(suppress_qt_warnings)
    raise SystemExit(main())
