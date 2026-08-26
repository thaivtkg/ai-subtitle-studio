import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt
from core.services.model_manager import ModelManager
from ui.theme import Theme

class ModelManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📦 Quản lý Mô hình AI (Model Manager)")
        self.resize(700, 450)
        
        # Áp dụng chuẩn UI Dark Mode của dự án
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG_APP}; }}
            QLabel {{ color: {Theme.TEXT_PRIMARY}; }}
            QTableWidget {{ 
                background-color: {Theme.SURFACE}; 
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                gridline-color: {Theme.BORDER};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background-color: {Theme.SURFACE_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                padding: 6px;
                border: 1px solid {Theme.BORDER};
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {Theme.SURFACE_ELEVATED};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; border: 1px solid {Theme.CYAN}; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        lbl_title = QLabel("Kho Lưu Trữ Mô Hình (Model Storage)")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(lbl_title)
        
        lbl_desc = QLabel("Quản lý dung lượng ổ cứng. Nhập mô hình Offline (CTranslate2) từ USB/Thư mục vào hệ thống hoặc xóa các mô hình không còn sử dụng để giải phóng không gian.")
        lbl_desc.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 13px;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Tên Model", "Dung lượng (Tương đối)", "Trạng thái", "Hành động"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.table)
        
        # Buttons Bottom
        btn_layout = QHBoxLayout()
        self.btn_import = QPushButton("📥 Import Model Offline...")
        self.btn_import.setStyleSheet(f"QPushButton {{ background-color: {Theme.PRIMARY_PURPLE}; color: white; font-weight: bold; border: none; }} QPushButton:hover {{ background-color: #9D85FF; }}")
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
            
            # Tên Model
            self.table.setItem(row, 0, QTableWidgetItem(m["size"]))
            
            # Dung lượng
            self.table.setItem(row, 1, QTableWidgetItem(m["weight"]))
            
            # Trạng thái
            status_item = QTableWidgetItem("✅ Đã cài đặt" if m["installed"] else "❌ Chưa tải")
            status_item.setForeground(Qt.green if m["installed"] else Qt.gray)
            self.table.setItem(row, 2, status_item)
            
            # Hành động
            btn_delete = QPushButton("🗑 Xóa Model")
            if not m["installed"]:
                btn_delete.setEnabled(False)
                btn_delete.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background-color: transparent; border: none;")
            else:
                btn_delete.setStyleSheet(f"color: {Theme.DANGER}; background-color: transparent; border: 1px solid {Theme.DANGER}; border-radius: 4px;")
                btn_delete.clicked.connect(lambda checked, size=m["size"]: self.delete_model(size))
            
            self.table.setCellWidget(row, 3, btn_delete)

    def delete_model(self, size):
        reply = QMessageBox.question(
            self, "Xác nhận xóa", 
            f"Bạn có chắc chắn muốn xóa tận gốc model '{size}' khỏi hệ thống không?\n\n(Dung lượng ổ cứng sẽ được giải phóng ngay lập tức)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if ModelManager.delete_model(size):
                QMessageBox.information(self, "Thành công", f"Đã dọn dẹp sạch model '{size}'.")
                self.load_data()
            else:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy model để xóa.")

    def import_model(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa Model CTranslate2 (cần có file config.json)")
        if folder:
            sizes = [m["size"] for m in ModelManager.get_discovery_list()]
            size, ok = QInputDialog.getItem(self, "Định danh Model", "Model Offline này thuộc size nào?", sizes, 0, False)
            if ok and size:
                try:
                    ModelManager.import_offline_model(size, folder)
                    QMessageBox.information(self, "Hoàn tất", f"Đã Import thành công model '{size}' vào hệ thống!")
                    self.load_data()
                except Exception as e:
                    QMessageBox.critical(self, "Lỗi Import", str(e))