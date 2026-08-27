import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from core.services.model_manager import ModelManager
from ui.theme import Theme

# Worker chạy ẩn để không làm đơ giao diện khi tải
class DownloadWorker(QThread):
    finished_signal = Signal(bool, str)
    
    def __init__(self, size):
        super().__init__()
        self.size = size
        
    def run(self):
        try:
            ModelManager.download_model_sync(self.size)
            self.finished_signal.emit(True, "")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class ModelManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📦 Quản lý Mô hình AI (Model Manager)")
        self.resize(750, 450)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG_APP}; }}
            QLabel {{ color: {Theme.TEXT_PRIMARY}; }}
            QTableWidget {{ background-color: {Theme.SURFACE}; color: {Theme.TEXT_PRIMARY}; border: 1px solid {Theme.BORDER}; border-radius: 6px; }}
            QHeaderView::section {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_SECONDARY}; padding: 6px; border: 1px solid {Theme.BORDER}; font-weight: bold; }}
            QPushButton {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY}; border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 6px 12px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; border: 1px solid {Theme.CYAN}; }}
            QPushButton:disabled {{ background-color: transparent; color: {Theme.TEXT_MUTED}; border: none; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        lbl_title = QLabel("Kho Lưu Trữ Mô Hình (Model Storage)")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl_title)
        
        lbl_desc = QLabel("Quản lý vòng đời AI: Tải xuống trực tuyến, Nhập Offline (USB), Xóa mô hình cũ.")
        lbl_desc.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(lbl_desc)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5) # Thêm cột Hành động Tải
        self.table.setHorizontalHeaderLabels(["Tên Model", "Dung lượng", "Trạng thái", "Tải xuống", "Xóa"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.btn_import = QPushButton("📥 Import Model Offline...")
        self.btn_import.setStyleSheet(f"QPushButton {{ background-color: {Theme.PRIMARY_PURPLE}; color: white; border: none; }} QPushButton:hover {{ background-color: #9D85FF; }}")
        self.btn_import.clicked.connect(self.import_model)
        
        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_import)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)
        
        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        models = ModelManager.get_discovery_list()
        
        for row, m in enumerate(models):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(m["size"]))
            self.table.setItem(row, 1, QTableWidgetItem(m["weight"]))
            
            status = QTableWidgetItem("✅ Đã cài đặt" if m["installed"] else "❌ Chưa tải")
            status.setForeground(Qt.green if m["installed"] else Qt.gray)
            self.table.setItem(row, 2, status)
            
            # Nút Tải
            btn_download = QPushButton("⬇️ Tải về")
            if m["installed"]:
                btn_download.setEnabled(False)
            else:
                btn_download.setStyleSheet(f"color: {Theme.CYAN}; border: 1px solid {Theme.CYAN}; background-color: transparent;")
                btn_download.clicked.connect(lambda checked, size=m["size"], r=row: self.download_model(size, r))
            self.table.setCellWidget(row, 3, btn_download)

            # Nút Xóa
            btn_delete = QPushButton("🗑 Xóa")
            if not m["installed"]:
                btn_delete.setEnabled(False)
            else:
                btn_delete.setStyleSheet(f"color: {Theme.DANGER}; border: 1px solid {Theme.DANGER}; background-color: transparent;")
                btn_delete.clicked.connect(lambda checked, size=m["size"]: self.delete_model(size))
            self.table.setCellWidget(row, 4, btn_delete)

    def download_model(self, size, row):
        btn = self.table.cellWidget(row, 3)
        btn.setEnabled(False)
        btn.setText("⏳ Đang tải...")
        btn.setStyleSheet(f"color: {Theme.WARNING}; border: 1px solid {Theme.WARNING}; background-color: transparent;")
        
        self.worker = DownloadWorker(size)
        self.worker.finished_signal.connect(self.on_download_finished)
        self.worker.start()

    def on_download_finished(self, success, error_msg):
        if success:
            QMessageBox.information(self, "Hoàn tất", "Tải Model thành công!")
        else:
            QMessageBox.critical(self, "Lỗi", f"Tải thất bại: {error_msg}")
        self.load_data()

    def delete_model(self, size):
        if QMessageBox.question(self, "Xác nhận", f"Xóa model '{size}'?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            ModelManager.delete_model(size)
            self.load_data()

    def import_model(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa config.json")
        if folder:
            sizes = [m["size"] for m in ModelManager.get_discovery_list()]
            size, ok = QInputDialog.getItem(self, "Định danh", "Model thuộc size nào?", sizes, 0, False)
            if ok and size:
                ModelManager.import_offline_model(size, folder)
                self.load_data()