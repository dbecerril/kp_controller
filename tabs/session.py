# tabs/session.py
import re
from datetime import datetime
import pandas as pd

from PyQt5.QtCore import QAbstractTableModel, Qt, QVariant, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QHeaderView,
    QLabel, QLineEdit, QFileDialog, QMessageBox, QDialog, QListWidget,
    QListWidgetItem, QDialogButtonBox
)

# ---------------------------
# Qt model for a pandas.DataFrame
# ---------------------------
import numpy as np
class PandasModel(QAbstractTableModel):
    """Minimal DataFrame→Qt model"""
    def __init__(self, df=None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def rowCount(self, parent=None):
        return 0 if self._df is None else len(self._df)

    def columnCount(self, parent=None):
        return 0 if self._df is None else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole or self._df is None:
            return QVariant()
        val = self._df.iat[index.row(), index.column()]
        if pd.isna(val):
                return ""
            # --- format numbers nicely ---
        if isinstance(val, (float, np.floating)):
            return f"{val:.3f}"    # max 3 decimals
        
        return str(val)
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or self._df is None:
            return QVariant()
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    def update(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df.copy() if self._df is not None else pd.DataFrame()


# ---------------------------
# Columns chooser dialog
# ---------------------------
class ColumnsDialog(QDialog):
    def __init__(self, all_columns, visible_columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Columns")
        self.resize(420, 420)

        self.listw = QListWidget(self)
        self.listw.setSelectionMode(QListWidget.NoSelection)

        # Put currently visible columns on top (checked), then the rest
        visible_set = set(visible_columns or [])
        ordered_cols = list(visible_columns or []) + [c for c in all_columns if c not in visible_set]

        for col in ordered_cols:
            item = QListWidgetItem(col)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if col in visible_set else Qt.Unchecked)
            self.listw.addItem(item)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # Quick presets
        self.btn_compact = QPushButton("Compact preset")
        self.btn_all = QPushButton("Show all")
        self.btn_none = QPushButton("Show none")
        self.btn_compact.clicked.connect(lambda: self._apply_preset(["timestamp_iso", "sample_name", "bias_V", "gradient", "session_name"]))
        self.btn_all.clicked.connect(self._check_all)
        self.btn_none.clicked.connect(self._uncheck_all)

        row1 = QHBoxLayout()
        row1.addWidget(self.btn_compact)
        row1.addWidget(self.btn_all)
        row1.addWidget(self.btn_none)
        row1.addStretch()

        lay = QVBoxLayout(self)
        lay.addLayout(row1)
        lay.addWidget(self.listw)
        lay.addWidget(self.button_box)

    def _check_all(self):
        for i in range(self.listw.count()):
            self.listw.item(i).setCheckState(Qt.Checked)

    def _uncheck_all(self):
        for i in range(self.listw.count()):
            self.listw.item(i).setCheckState(Qt.Unchecked)

    def _apply_preset(self, preset_cols):
        preset = set(preset_cols)
        for i in range(self.listw.count()):
            it = self.listw.item(i)
            it.setCheckState(Qt.Checked if it.text() in preset else Qt.Unchecked)

    def selected_columns(self):
        cols = []
        for i in range(self.listw.count()):
            it = self.listw.item(i)
            if it.checkState() == Qt.Checked:
                cols.append(it.text())
        return cols


# ---------------------------
# Session Tab UI
# ---------------------------
class SessionTab(QWidget):
    """
    - First row: Session Name (wide)
    - Second row: Import / Export / Clear / Columns...
    - Table with selectable visible columns

    Signals:
      - clearRequested: ask host to clear its session state (optional)
      - dataImported(object): emits a pandas.DataFrame when a CSV is imported
    """
    clearRequested = pyqtSignal()
    dataImported = pyqtSignal(object)  # pandas.DataFrame

    REQUIRED_COLUMNS = [
        "timestamp_iso", "sample_name", "bias_V", "gradient",
        "lockin_params_json", "scan_params_json", "session_name"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_df = pd.DataFrame(columns=self.REQUIRED_COLUMNS)

        # Default visible columns (compact)
        self._visible_columns = ["timestamp_iso", "sample_name", "bias_V", "gradient", "session_name"]

        layout = QVBoxLayout(self)

        # --- Row 1: Session name only (more space) ---
        row_session = QHBoxLayout()
        self.label_session_name = QLabel("Session Name:")
        self.input_session_name = QLineEdit()
        self.input_session_name.setPlaceholderText("Enter session name...")
        self.input_session_name.textChanged.connect(self._ensure_session_name_on_df)

        row_session.addWidget(self.label_session_name)
        row_session.addWidget(self.input_session_name, stretch=1)

        # --- Row 2: Action buttons ---
        row_buttons = QHBoxLayout()
        self.button_import_csv = QPushButton("Import CSV")
        self.button_export_csv = QPushButton("Export CSV")
        self.button_clear_session = QPushButton("Clear Session")
        self.button_choose_columns = QPushButton("Columns...")

        row_buttons.addWidget(self.button_import_csv)
        row_buttons.addWidget(self.button_export_csv)
        row_buttons.addWidget(self.button_clear_session)
        row_buttons.addSpacing(12)
        row_buttons.addWidget(self.button_choose_columns)
        row_buttons.addStretch()

        # --- Table ---
        self.table = QTableView()
        self.model = PandasModel(self._current_df)
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)

        # Improve contrast for header + cells (works with/without your global QSS)
        self.table.setStyleSheet("""
        QTableView {
            background: #1f1f1f;             /* table background */
            color: #e9e9e9;                   /* cell text */
            gridline-color: #3a3a3a;
            selection-background-color: #2a82da;
            selection-color: #ffffff;
            alternate-background-color: #252525;
        }
        QHeaderView::section {
            background-color: #2b2b2b;        /* header background */
            color: #f5f5f5;                   /* header text */
            padding: 6px 8px;
            border: 1px solid #3c3c3c;
            font-weight: 600;
        }
        QTableCornerButton::section {
            background-color: #2b2b2b;
            border: 1px solid #3c3c3c;
        }
        """)

        # --- Wire up ---
        self.button_export_csv.clicked.connect(self._on_export_clicked)
        self.button_import_csv.clicked.connect(self._on_import_clicked)
        self.button_clear_session.clicked.connect(self.clearRequested.emit)
        self.button_choose_columns.clicked.connect(self._open_columns_dialog)

        layout.addLayout(row_session)
        layout.addLayout(row_buttons)
        layout.addWidget(self.table)

        # Apply initial visibility
        self._apply_visible_columns()

    # ---------------------------
    # Public API (used by main.py)
    # ---------------------------
    def update_dataframe(self, df: pd.DataFrame):
        """Host calls this whenever the session DataFrame changes."""
        safe = self._normalize_df(df)
        self._current_df = safe
        self.model.update(safe)
        # Columns may have changed; re-apply visibility with reconciliation
        self._reconcile_visible_columns()
        self._apply_visible_columns()

    def set_session_name(self, name: str):
        """Host can set a default session name (e.g., project name)."""
        self.input_session_name.setText(name.strip())

    def get_session_name(self) -> str:
        return self.input_session_name.text().strip()

    # ---------------------------
    # Internal helpers
    # ---------------------------
    def _normalize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure required columns exist; fill session_name column."""
        df = df.copy() if df is not None else pd.DataFrame()
        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = pd.Series([pd.NA] * len(df))
        # keep column order (ensure required first, then any extra trailing)
        other_cols = [c for c in df.columns if c not in self.REQUIRED_COLUMNS]
        df = df[self.REQUIRED_COLUMNS + other_cols]

        # Fill session_name with current field if empty
        sess = self.get_session_name()
        if sess and "session_name" in df.columns:
            empty_mask = df["session_name"].isna() | (df["session_name"].astype(str).str.strip() == "")
            if empty_mask.any():
                df.loc[empty_mask, "session_name"] = sess
        return df

    def _ensure_session_name_on_df(self, *_):
        """When the text changes, ensure the model has session_name filled."""
        if self._current_df is None or self._current_df.empty:
            return
        sess = self.get_session_name()
        if not sess:
            return
        if "session_name" not in self._current_df.columns:
            return
        df = self._current_df.copy()
        empty_mask = df["session_name"].isna() | (df["session_name"].astype(str).str.strip() == "")
        if empty_mask.any():
            df.loc[empty_mask, "session_name"] = sess
            self.update_dataframe(df)

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text.strip("-") or "session"

    def _suggest_filename(self) -> str:
        sess = self.get_session_name() or "session"
        slug = self._slugify(sess)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{ts}_{slug}.csv"

    # ---------------------------
    # Column visibility logic
    # ---------------------------
    def _reconcile_visible_columns(self):
        """Keep only columns that still exist; if none, fall back to compact preset."""
        cols = list(self._current_df.columns)
        self._visible_columns = [c for c in (self._visible_columns or []) if c in cols]
        if not self._visible_columns:
            # fallback compact
            compact = ["timestamp_iso", "sample_name", "bias_V", "gradient", "session_name"]
            self._visible_columns = [c for c in compact if c in cols] or cols[:5]

    def _apply_visible_columns(self):
        """Hide table columns that are not selected; show selected ones."""
        if self._current_df is None or self._current_df.empty:
            # nothing to hide/show yet; still set headers stretch
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            return

        all_cols = list(self._current_df.columns)
        visible_set = set(self._visible_columns)

        for logical_idx, col_name in enumerate(all_cols):
            self.table.setColumnHidden(logical_idx, col_name not in visible_set)

        # Stretch visible columns nicely
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _open_columns_dialog(self):
        all_cols = list(self._current_df.columns)
        if not all_cols:
            QMessageBox.information(self, "Columns", "No columns available yet.")
            return
        dlg = ColumnsDialog(all_columns=all_cols, visible_columns=self._visible_columns, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            selected = dlg.selected_columns()
            if not selected:
                QMessageBox.information(self, "Columns", "You must keep at least one column visible.")
                return
            self._visible_columns = selected
            self._apply_visible_columns()

    # ---------------------------
    # Export / Import
    # ---------------------------
    def _on_export_clicked(self):
        """Export current table to CSV; include session_name column & filename."""
        df = self.model.dataframe()
        if df.empty:
            QMessageBox.information(self, "Export CSV", "There is no data to export.")
            return

        # Ensure session_name column is filled with the current name
        sess = self.get_session_name()
        if "session_name" in df.columns and sess:
            empty_mask = df["session_name"].isna() | (df["session_name"].astype(str).str.strip() == "")
            if empty_mask.any():
                df.loc[empty_mask, "session_name"] = sess

        suggested = self._suggest_filename()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session CSV", suggested, "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            df.to_csv(path, index=False)
            QMessageBox.information(self, "Export CSV", f"Saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export CSV", f"Failed to save file:\n{e}")

    def _on_import_clicked(self):
        """Import CSV; populate session name if present; emit DataFrame for host."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Session CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            df = pd.read_csv(path)
        except Exception as e:
            QMessageBox.critical(self, "Import CSV", f"Failed to open file:\n{e}")
            return

        # Normalize columns and session_name handling
        df = self._normalize_df(df)

        # If file has a session_name, populate the text field from it (mode)
        if "session_name" in df.columns:
            non_empty = df["session_name"].dropna().astype(str).str.strip()
            if not non_empty.empty:
                # pick the most frequent non-empty value
                sess = non_empty.value_counts().idxmax()
                if sess:
                    self.input_session_name.setText(sess)

        # Update UI + notify host
        self.update_dataframe(df)
        self.dataImported.emit(df)

        QMessageBox.information(self, "Import CSV", f"Loaded:\n{path}")
