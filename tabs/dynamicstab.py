# tabs/dynamicstab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDoubleSpinBox, QComboBox
from PyQt5.QtCore import pyqtSignal, QThread
from controllers import dynamics

class dynamicsTab(QWidget):
    """
    Minimal UI:
      - Duration (s)
      - dt (s)
      - Channel (MAG./PHA./X./Y.)
      - Start (turn light ON and capture)
    Emits dataReady(t, y, label) so Main can plot on the existing right plot.
    """
    dataReady = pyqtSignal(object, object, str)  # (t array, y array, y_label)

    def __init__(self, expobj, rm, parent=None):
        super().__init__(parent)
        self.expobj = expobj
        self.rm = rm
        self._thread = None
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()

        self.btn_start = QPushButton("Start Capture (sync light ON)")

        self.lbl_dur = QLabel("Duration (s):")
        self.spin_dur = QDoubleSpinBox()
        self.spin_dur.setDecimals(3)
        self.spin_dur.setRange(0.001, 3600.0)
        self.spin_dur.setValue(1.000)

        self.lbl_dt = QLabel("dt (s):")
        self.spin_dt = QDoubleSpinBox()
        self.spin_dt.setDecimals(6)
        self.spin_dt.setRange(1e-6, 1.0)
        self.spin_dt.setValue(0.001)

        self.lbl_chan = QLabel("Channel:")
        self.cmb_chan = QComboBox()
        self.cmb_chan.addItems(["MAG.", "PHA.", "X.", "Y."])

        row.addWidget(self.lbl_dur)
        row.addWidget(self.spin_dur)
        row.addSpacing(8)
        row.addWidget(self.lbl_dt)
        row.addWidget(self.spin_dt)
        row.addSpacing(8)
        row.addWidget(self.lbl_chan)
        row.addWidget(self.cmb_chan)
        row.addStretch(1)
        row.addWidget(self.btn_start)

        layout.addLayout(row)

        # --- Live readout row ---
        readout_row = QHBoxLayout()
        self.lbl_ro_title = QLabel("Live Readout:")
        self.lbl_ro = QLabel("—")
        self.lbl_ro.setStyleSheet("font-weight: 600;")
        readout_row.addWidget(self.lbl_ro_title)
        readout_row.addSpacing(8)
        readout_row.addWidget(self.lbl_ro)
        readout_row.addStretch(1)
        layout.addLayout(readout_row)
        # -------------------------

        self.btn_start.clicked.connect(self._on_start)

    def _on_start(self):
        duration_s = float(self.spin_dur.value())
        dt_s = float(self.spin_dt.value())
        chan = self.cmb_chan.currentText()

        # Disable button + UI feedback
        self.btn_start.setEnabled(False)
        self.lbl_ro.setText("Capturing…")

        # Prepare and start the worker thread
        self._thread = QThread(self)
        self._worker = dynamics.DynamicsWorker(self.rm, duration_s, dt_s, chan)
        self._worker.moveToThread(self._thread)

        # Wire signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)          # live updates
        self._worker.finished.connect(self._on_finished)          # final data
        self._worker.error.connect(self._on_error)                # error handling
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_progress(self, t_current: float, y_current: float):
        self.lbl_ro.setText(f"t = {t_current:.6f} s • value = {y_current:.6g}")

    def _on_finished(self, t, y, label: str):
        # update final readout with last value
        if len(y) > 0:
            self.lbl_ro.setText(f"Done • {len(y)} pts • last = {y[-1]:.6g} ({label})")
        else:
            self.lbl_ro.setText("Done • No data")
        self.dataReady.emit(t, y, label)
        self.btn_start.setEnabled(True)

    def _on_error(self, message: str):
        self.lbl_ro.setText(f"Error: {message}")
        self.btn_start.setEnabled(True)
