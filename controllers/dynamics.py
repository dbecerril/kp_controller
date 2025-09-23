# controllers/dynamics.py
from typing import Tuple
import numpy as np
import math
import time

import controllers.kputils as kputils

# --- Optional: PyQt worker for live readout ---
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

def _set_light(inst, volts: float = 5.0, channel: int = 2):
    """Drive DAC{channel} to volts (e.g., 5.000 V)"""
    mv = int(round(volts * 1000))
    sign = "+" if mv >= 0 else "-"
    payload = f"{abs(mv):05d}"
    cmd = f"DAC{channel}{sign}{payload}"
    kputils.Inst_Query_Command_RS232(inst, cmd, verbose=False)

def _read_cbd(inst, n_points: int):
    """
    Read n_points from the instrument's fast buffer using the 'CBDxxxxx' command.
    Returns a 1D numpy array of floats (already converted).
    """
    cmd = f"CBD{int(n_points):05d}"
    raw, _ = kputils.Inst_Query_Command_RS232(inst, cmd, verbose=False)
    vals = kputils.convert_lockin_data((raw,))
    return np.asarray(vals, dtype=float)

def _select_channel_column(arr_1d: np.ndarray, channel_cmd: str) -> np.ndarray:
    """
    Heuristic demux: CBD often returns interleaved values (e.g., MAG, PHA, DAC1 ...).
    Adjust the mapping if your device differs.
    """
    if arr_1d.size % 3 == 0:
        data = arr_1d.reshape(-1, 3)
        colmap = {"MAG.": 0, "PHA.": 1, "X.": 0, "Y.": 1}
        col = colmap.get(channel_cmd, 0)
        return data[:, col]
    elif arr_1d.size % 2 == 0:
        return arr_1d.reshape(-1, 2)[:, 0]
    else:
        return arr_1d

class DynamicsWorker(QObject):
    """
    QThread-able worker that:
      - turns light ON
      - arms acquisition
      - reads CBD in chunks
      - emits progress(t, y_last) during capture
      - emits finished(t_array, y_array, label) at the end
    """
    progress = pyqtSignal(float, float)             # t_current, y_current
    finished = pyqtSignal(object, object, str)      # t array, y array, label
    error = pyqtSignal(str)

    def __init__(self, rm, duration_s: float, dt_s: float, channel_cmd: str = "MAG.", parent=None):
        super().__init__(parent)
        self.rm = rm
        self.duration_s = float(duration_s)
        self.dt_s = float(dt_s)
        self.channel_cmd = channel_cmd

    @pyqtSlot()
    def run(self):
        n_total = max(1, int(round(self.duration_s / max(self.dt_s, 1e-6))))
        n_total = min(n_total, 65535)

        # Choose a chunk size so we update ~10–30 times per second (UI-friendly) but never <1 point
        # Also cap chunks to avoid too-large CBD commands.
        target_ui_hz = 20.0
        points_per_ui = max(1, int(round(target_ui_hz * self.dt_s)))  # often 0 -> fix with max(1,...)
        # If dt is small, points_per_ui becomes small, good. If dt is large, shrink updates.
        # Fall back to ~1–5% of total if that produced too tiny/huge chunks.
        chunk = max(1, min(2048, max(points_per_ui, int(n_total * 0.02))))

        inst = None
        all_y = []
        try:
            inst = kputils.Connection_Open_RS232(self.rm, verbose=False)

            # Light ON + arm acquisition
            _set_light(inst, volts=5.0, channel=2)
            kputils.Inst_Query_Command_RS232(inst, "AQN", verbose=False)

            n_done = 0
            t0 = time.perf_counter()

            while n_done < n_total:
                n_left = n_total - n_done
                this_chunk = min(chunk, n_left)

                # CBD read of this_chunk points
                raw_chunk = _read_cbd(inst, this_chunk)
                y_chunk = _select_channel_column(raw_chunk, self.channel_cmd)
                # Some devices return more than requested when interleaved; trim to this_chunk if needed
                if y_chunk.size > this_chunk:
                    y_chunk = y_chunk[:this_chunk]

                all_y.append(y_chunk)
                n_done += y_chunk.size

                # Emit last sample time and value as "live readout"
                t_current = n_done * self.dt_s
                y_current = float(y_chunk[-1]) if y_chunk.size else float("nan")
                self.progress.emit(float(t_current), y_current)

                # Pace loop a bit so we don't spam the UI if instrument is very fast
                # (Keep this small; real timing is governed by instrument I/O)
                time.sleep(0.0)

            y = np.concatenate(all_y) if all_y else np.empty(0, dtype=float)
            # Build time axis from dt_s
            t = np.arange(y.size, dtype=float) * self.dt_s

            # Done
            self.finished.emit(t, y, self.channel_cmd)

        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")
        finally:
            try:
                # Light OFF after capture (remove if you want it to stay ON)
                if inst is not None:
                    _set_light(inst, volts=0.0, channel=2)
            finally:
                if inst is not None:
                    kputils.Connection_Close(inst, verbose=False)

# --- Keep your original synchronous function available (unchanged API) ---
def start_capture(rm, duration_s: float, dt_s: float, channel_cmd: str = "MAG.") -> Tuple[np.ndarray, np.ndarray, str]:
    """
    Synchronous version: one-shot buffer read (no live updates).
    """
    n_points = max(1, int(round(duration_s / max(dt_s, 1e-6))))
    n_points = min(n_points, 65535)

    inst = kputils.Connection_Open_RS232(rm, verbose=False)
    try:
        _set_light(inst, volts=5.0, channel=2)
        kputils.Inst_Query_Command_RS232(inst, "AQN", verbose=False)

        raw = _read_cbd(inst, n_points)
        y = _select_channel_column(raw, channel_cmd)

        t = np.arange(y.size, dtype=float) * float(dt_s)
        return t, y, channel_cmd
    finally:
        _set_light(inst, volts=0.0, channel=2)
        kputils.Connection_Close(inst, verbose=False)
