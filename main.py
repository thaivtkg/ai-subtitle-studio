
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

from core.app_context import build_startup_context
from core.project.source_fingerprint import generate_source_info
from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_models import RecoveryContext
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker
from core.runtime.runtime_paths import RuntimePaths
from core.runtime.single_instance_guard import (
    IpcAction,
    IpcRequest,
    SingleInstanceGuard,
)
from core.subtitle_editing.global_undo_manager import GlobalUndoManager

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

    app = QApplication(sys.argv)

    guard = SingleInstanceGuard()
    if not guard.try_acquire_primary():
        result = run_secondary_instance(guard, sys.argv)
        guard.close()
        return result
    guard.start_listening()
    undo_manager, revision_tracker, recovery_manager = build_recovery_manager()
    recovery_candidates = recovery_manager.scan_candidates()
    recovery_manager.log_runtime_event(
        "startup-recovery-scan-complete",
        candidate_count=len(recovery_candidates),
    )
    startup_context = build_startup_context(
        sys_args=sys.argv,
        has_pending_recovery=bool(recovery_candidates),
    )
    selected_candidate = recovery_candidates[0] if recovery_candidates else None
    recovered_state = None
    recovered_linked = True
    if selected_candidate is not None:
        candidate = selected_candidate
        recovery_manager.log_runtime_event(
            "startup-candidate-selected",
            session_id=candidate.manifest.session_id,
            project_id=candidate.manifest.project_id,
            project_file_path=candidate.manifest.project_file_path,
            revision=candidate.snapshot.edit_revision,
        )
        source_info = None
        if candidate.manifest.video_path and os.path.exists(candidate.manifest.video_path):
            try:
                source_info = generate_source_info(candidate.manifest.video_path)
            except (OSError, ValueError):
                source_info = None
        validation = recovery_manager.validate_candidate(candidate, source_info)
        if not validation.is_valid:
            recovery_manager.log_runtime_event(
                "startup-candidate-discarded",
                session_id=candidate.manifest.session_id,
                reason=validation.reason,
            )
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
                recovery_manager.log_runtime_event(
                    "restore-choice",
                    session_id=candidate.manifest.session_id,
                    choice="discard",
                )
                recovery_manager.discard_session(candidate.manifest.session_id)
                selected_candidate = None
            else:
                recovery_manager.log_runtime_event(
                    "restore-choice",
                    session_id=candidate.manifest.session_id,
                    choice="restore",
                )
                revision_tracker.restore_from_snapshot(
                    candidate.snapshot.edit_revision,
                    candidate.manifest.last_saved_revision,
                    candidate.manifest.last_clean_revision,
                )
                recovery_manager.handoff_recovered_state(
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
                recovery_manager.log_runtime_event(
                    "restore-state-selected",
                    session_id=candidate.manifest.session_id,
                    project_id=candidate.manifest.project_id,
                    revision=candidate.snapshot.edit_revision,
                    linked=recovered_linked,
                )
    from ui import Gui as gui_module
    from ui.theme import Theme

    # --- CHỈNH SỬA TẠI ĐÂY: Sử dụng RuntimePaths load icon ---
    icon_path = str(RuntimePaths.get_resources_dir() / "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    # ----------------------------------------------------

    
    # Thiết lập Stylesheet toàn cục (QMessageBox) chuyển từ file Gui cũ sang
    app.setStyleSheet(Theme.get_global_stylesheet())



    # Khởi tạo và hiển thị giao diện chính
    window = gui_module.MainWindow(
        revision_tracker=revision_tracker,
        recovery_manager=recovery_manager,
        undo_manager=undo_manager,
        startup_context=startup_context,
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

if __name__ == "__main__":
    qInstallMessageHandler(suppress_qt_warnings)
    raise SystemExit(main())
