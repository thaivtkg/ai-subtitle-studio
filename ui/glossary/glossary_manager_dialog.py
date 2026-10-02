import csv
import io
import os
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database.glossary_manager import GlossaryEntry, GlossaryManager
from ui.theme import Theme


def parse_glossary_csv_text(text: str) -> List[dict]:
    """
    Parses glossary text from CSV or TSV or plain text format:
    - CSV format: Source,Target[,Domain,LangPair]
    - Mapping format: Source -> Target or Source = Target
    """
    entries = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return entries

    # Check if first line looks like a CSV header
    first_lower = lines[0].lower()
    start_idx = 0
    if "source" in first_lower and "target" in first_lower:
        start_idx = 1

    reader = csv.reader(lines[start_idx:])
    for row in reader:
        if not row:
            continue
        if len(row) == 1:
            line = row[0].strip()
            if "->" in line:
                parts = line.split("->", 1)
                entries.append({
                    "source_text": parts[0].strip(),
                    "target_text": parts[1].strip(),
                    "domain": "general",
                    "lang_pair": "",
                })
            elif "=" in line:
                parts = line.split("=", 1)
                entries.append({
                    "source_text": parts[0].strip(),
                    "target_text": parts[1].strip(),
                    "domain": "general",
                    "lang_pair": "",
                })
            else:
                entries.append({
                    "source_text": line,
                    "target_text": line,
                    "domain": "general",
                    "lang_pair": "",
                })
        elif len(row) >= 2:
            src = row[0].strip()
            tgt = row[1].strip()
            domain = row[2].strip() if len(row) > 2 and row[2].strip() else "general"
            lang = row[3].strip() if len(row) > 3 else ""
            if src and tgt:
                entries.append({
                    "source_text": src,
                    "target_text": tgt,
                    "domain": domain,
                    "lang_pair": lang,
                })
    return entries


class TermEditDialog(QDialog):
    """Dialog for adding or editing a single glossary entry."""

    def __init__(self, entry: Optional[GlossaryEntry] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Term" if entry else "Add Term")
        self.setFixedWidth(400)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG_APP}; color: {Theme.TEXT_PRIMARY}; }}
            QLabel {{ color: {Theme.TEXT_SECONDARY}; font-size: 13px; }}
            QLineEdit {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 6px; }}
            QLineEdit:focus {{ border: 1px solid {Theme.PRIMARY_PURPLE}; }}
            QPushButton {{ padding: 6px 16px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
        """)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.source_edit = QLineEdit()
        self.target_edit = QLineEdit()
        self.domain_edit = QLineEdit()
        self.domain_edit.setPlaceholderText("general")
        self.lang_edit = QLineEdit()
        self.lang_edit.setPlaceholderText("e.g. en-vi, ja-vi")

        if entry:
            self.source_edit.setText(entry.source_text)
            self.target_edit.setText(entry.target_text)
            self.domain_edit.setText(entry.domain)
            self.lang_edit.setText(entry.lang_pair)

        form.addRow("Source Term *:", self.source_edit)
        form.addRow("Target Translation *:", self.target_edit)
        form.addRow("Domain:", self.domain_edit)
        form.addRow("Language Pair:", self.lang_edit)
        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_SECONDARY};")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"background-color: {Theme.PRIMARY_PURPLE}; color: white;")
        save_btn.clicked.connect(self._on_save)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def _on_save(self):
        if not self.source_edit.text().strip() or not self.target_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Source and Target terms cannot be empty.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "source_text": self.source_edit.text().strip(),
            "target_text": self.target_edit.text().strip(),
            "domain": self.domain_edit.text().strip() or "general",
            "lang_pair": self.lang_edit.text().strip(),
        }


class GlossaryManagerDialog(QDialog):
    """Full-featured Glossary management dialog with search, filters, CRUD, and CSV import/export."""

    def __init__(self, manager: Optional[GlossaryManager] = None, parent=None):
        super().__init__(parent)
        self.manager = manager if manager is not None else GlossaryManager()
        self.setWindowTitle("Glossary Manager — Termbase")
        self.setMinimumSize(780, 500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG_APP}; color: {Theme.TEXT_PRIMARY}; }}
            QLabel {{ color: {Theme.TEXT_SECONDARY}; font-size: 13px; }}
            QLineEdit, QComboBox {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 6px; }}
            QLineEdit:focus, QComboBox:focus {{ border: 1px solid {Theme.PRIMARY_PURPLE}; }}
            QTableWidget {{ background-color: {Theme.SURFACE}; color: {Theme.TEXT_PRIMARY};
                gridline-color: {Theme.BORDER}; border: 1px solid {Theme.BORDER}; border-radius: 6px; }}
            QHeaderView::section {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_SECONDARY};
                font-weight: 600; font-size: 12px; padding: 6px; border: none; border-bottom: 1px solid {Theme.BORDER}; }}
            QPushButton {{ padding: 6px 14px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
        """)
        self._build_ui()
        self._load_entries()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header & Filter Row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search terms...")
        self.search_edit.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_edit, stretch=2)

        self.domain_filter = QComboBox()
        self.domain_filter.addItem("All Domains")
        self.domain_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.domain_filter, stretch=1)

        self.lang_filter = QComboBox()
        self.lang_filter.addItem("All Languages")
        self.lang_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.lang_filter, stretch=1)

        main_layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Source Term", "Target Translation", "Domain", "Language Pair"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        main_layout.addWidget(self.table)

        # Action Buttons Row
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        add_btn = QPushButton("➕ Add Term")
        add_btn.setStyleSheet(f"background-color: {Theme.PRIMARY_PURPLE}; color: white;")
        add_btn.clicked.connect(self._on_add)
        action_layout.addWidget(add_btn)

        edit_btn = QPushButton("✏️ Edit Term")
        edit_btn.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY};")
        edit_btn.clicked.connect(self._on_edit)
        action_layout.addWidget(edit_btn)

        del_btn = QPushButton("🗑️ Delete")
        del_btn.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.DANGER};")
        del_btn.clicked.connect(self._on_delete)
        action_layout.addWidget(del_btn)

        action_layout.addStretch()

        import_btn = QPushButton("📥 Import CSV/TXT")
        import_btn.setStyleSheet(f"background-color: {Theme.SURFACE_SOFT}; color: {Theme.CYAN};")
        import_btn.clicked.connect(self._on_import)
        action_layout.addWidget(import_btn)

        export_btn = QPushButton("📤 Export CSV")
        export_btn.setStyleSheet(f"background-color: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY};")
        export_btn.clicked.connect(self._on_export)
        action_layout.addWidget(export_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_SECONDARY};")
        close_btn.clicked.connect(self.accept)
        action_layout.addWidget(close_btn)

        main_layout.addLayout(action_layout)

    def _load_entries(self):
        all_entries = self.manager.list_entries()
        self._all_entries = all_entries

        # Populate filters without resetting selection
        curr_domain = self.domain_filter.currentText()
        curr_lang = self.lang_filter.currentText()

        self.domain_filter.blockSignals(True)
        self.lang_filter.blockSignals(True)

        self.domain_filter.clear()
        self.domain_filter.addItem("All Domains")
        domains = sorted({e.domain for e in all_entries if e.domain})
        for d in domains:
            self.domain_filter.addItem(d)
        if curr_domain in ["All Domains"] + domains:
            self.domain_filter.setCurrentText(curr_domain)

        self.lang_filter.clear()
        self.lang_filter.addItem("All Languages")
        langs = sorted({e.lang_pair for e in all_entries if e.lang_pair})
        for l in langs:
            self.lang_filter.addItem(l)
        if curr_lang in ["All Languages"] + langs:
            self.lang_filter.setCurrentText(curr_lang)

        self.domain_filter.blockSignals(False)
        self.lang_filter.blockSignals(False)

        self._apply_filters()

    def _apply_filters(self):
        query = self.search_edit.text().strip().lower()
        selected_domain = self.domain_filter.currentText()
        selected_lang = self.lang_filter.currentText()

        filtered = []
        for e in self._all_entries:
            if selected_domain != "All Domains" and e.domain != selected_domain:
                continue
            if selected_lang != "All Languages" and e.lang_pair != selected_lang:
                continue
            if query and query not in e.source_text.lower() and query not in e.target_text.lower():
                continue
            filtered.append(e)

        self._filtered_entries = filtered
        self.table.setRowCount(len(filtered))
        for row, entry in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(entry.source_text))
            self.table.setItem(row, 1, QTableWidgetItem(entry.target_text))
            self.table.setItem(row, 2, QTableWidgetItem(entry.domain))
            self.table.setItem(row, 3, QTableWidgetItem(entry.lang_pair))

    def _get_selected_entry(self) -> Optional[GlossaryEntry]:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        idx = selected_rows[0].row()
        if 0 <= idx < len(self._filtered_entries):
            return self._filtered_entries[idx]
        return None

    def _on_add(self):
        dialog = TermEditDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            self.manager.add_entry(
                source_text=data["source_text"],
                target_text=data["target_text"],
                domain=data["domain"],
                lang_pair=data["lang_pair"],
            )
            self._load_entries()

    def _on_edit(self):
        entry = self._get_selected_entry()
        if not entry:
            QMessageBox.information(self, "Select Term", "Please select a term to edit.")
            return

        dialog = TermEditDialog(entry=entry, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            self.manager.add_entry(
                source_text=data["source_text"],
                target_text=data["target_text"],
                domain=data["domain"],
                lang_pair=data["lang_pair"],
            )
            self._load_entries()

    def _on_delete(self):
        entry = self._get_selected_entry()
        if not entry:
            QMessageBox.information(self, "Select Term", "Please select a term to delete.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete term '{entry.source_text}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.manager.delete_entry(entry.id)
            self._load_entries()

    def _on_import(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Glossary", "", "Text/CSV Files (*.csv *.txt *.tsv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            entries = parse_glossary_csv_text(content)
            if entries:
                count = self.manager.import_entries(entries)
                self._load_entries()
                QMessageBox.information(
                    self, "Import Complete", f"Successfully imported {count} terms."
                )
            else:
                QMessageBox.warning(self, "Empty File", "No valid glossary entries found in file.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import file:\n{e}")

    def _on_export(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Glossary", "glossary_export.csv", "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Source", "Target", "Domain", "LanguagePair"])
                for e in self._filtered_entries:
                    writer.writerow([e.source_text, e.target_text, e.domain, e.lang_pair])
            QMessageBox.information(
                self, "Export Complete", f"Exported {len(self._filtered_entries)} terms to {os.path.basename(file_path)}."
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export file:\n{e}")
