# controllers/dynamics.py
from typing import Tuple, Dict
import numpy as np
import time

import controllers.kputils as kputils
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from pyvisa import errors as visa_errors
from pyvisa.constants import VI_ERROR_TMO


# ---------------- Buffer helpers ----------------

# Example SRAT index map (adjust for your model!)
# Key = sample period dt (s) approx; Value = SRAT index or integer Hz if your fw accepts it.
_SRAT_INDEX_BY_DT = {
    1e-3: 1000,   # 1 kHz (example if SRAT accepts Hz)
    2e-3: 500,
    5e-3: 200,
    1e-2: 100,
    2e-2: 50,
    5e-2: 20,
    1e-1: 10,
    2e-1: 5,
    5e-1: 2,
    1.0: 1,
}

# Tunables discovered from your ST tests
_INTER_CHAR_DELAY = 0.02       # 20 ms gap between characters (adjust 10–30 ms if needed)
_OVERALL_RD_TIMEOUT_S = 3.0    # overall time to wait for the prompt

def _inst_cmd(inst, cmd: str):
    """
    Send `cmd` with a small inter-character delay, then read bytes until the
    instrument prompt '*' (OK) or '?' (error). Returns (payload_text, status_byte).
    We strip the echoed command text (e.g., 'ST') so callers see just the data.
    """
    # --- Write: char-by-char without echo reads ---
    for ch in cmd:
        inst.write_raw(ch.encode('ascii'))
        time.sleep(_INTER_CHAR_DELAY)
    inst.write_raw(b'\r')

    # --- Read: 1 byte at a time until '*' or '?' (ignore CR/LF) ---
    # Use short per-read timeout to implement our own overall deadline.
    old_timeout = inst.timeout
    inst.timeout = 100  # ms per read attempt
    deadline = time.time() + _OVERALL_RD_TIMEOUT_S

    buf = bytearray()
    prompt = None
    try:
        while time.time() < deadline:
            try:
                b = inst.read_bytes(1)
            except visa_errors.VisaIOError as e:
                if getattr(e, "error_code", None) == VI_ERROR_TMO:
                    # no byte this slice; keep looping until deadline
                    continue
                raise
            if not b:
                continue
            if b in (b'*', b'?'):
                prompt = b
                break
            if b not in (b'\r', b'\n'):
                buf.extend(b)
    finally:
        inst.timeout = old_timeout

    # Decode and strip the echoed command (device echoes 'CMD' before data)
    text = buf.decode('utf-8', errors='ignore')
    if text.upper().startswith(cmd.upper()):
        text = text[len(cmd):].lstrip()

    # Mimic the old API's (response, status_byte) signature.
    # Callers in this file ignore status; return 1 for "done".
    return text, 1

def set_sample_rate(inst, dt_s: float):
    """
    Configure buffer sample rate to (about) 1/dt_s.
    Many instruments want SRAT <index>. If your firmware accepts SRAT <Hz>, keep that path.
    """
    # Pick nearest entry
    chosen_dt = min(_SRAT_INDEX_BY_DT.keys(), key=lambda d: abs(d - dt_s))
    target = _SRAT_INDEX_BY_DT[chosen_dt]
    try:
        # Try index/Hz as-is
        _inst_cmd(inst, f"SRAT {int(target)}")
    except Exception:
        # Fallback: try sending exact Hz
        hz = max(1, int(round(1.0 / max(dt_s, 1e-6))))
        _inst_cmd(inst, f"SRAT {hz}")

def set_buffer_points(inst, n_points: int):
    _inst_cmd(inst, f"SIZE {int(n_points)}")

def buffer_start(inst):
    _inst_cmd(inst, "STRT")

def buffer_pause(inst):
    _inst_cmd(inst, "PAUS")

def buffer_points_collected(inst) -> int:
    resp, _ = _inst_cmd(inst, "SPTS?")
    try:
        return int(str(resp).strip())
    except Exception:
        return 0

def buffer_send(inst) -> np.ndarray:
    """
    Dump buffer with SEND. Parse floats.
    Many devices return interleaved columns (e.g., R, Theta, DAC1 ...).
    """
    data_str, _ = _inst_cmd(inst, "SEND")
    vals = []
    for tok in data_str.replace(",", " ").split():
        try:
            vals.append(float(tok))
        except Exception:
            pass
    return np.asarray(vals, dtype=float)

# ---------------- Light + parsing ----------------

def _set_light(inst, volts: float = 5.0, channel: int = 2):
    mv = int(round(volts * 1000))
    sign = "+" if mv >= 0 else "-"
    payload = f"{abs(mv):05d}"
    cmd = f"DAC{channel}{sign}{payload}"
    _inst_cmd(inst, cmd)

def _select_channel_column(arr_1d: np.ndarray, channel_cmd: str) -> np.ndarray:
    """
    Heuristic demux for interleaved returns (e.g., [R, Theta, DAC1, R, Theta, DAC1, ...]).
    Adjust mapping if your instrument differs.
    """
    if arr_1d.size == 0:
        return arr_1d
    # Try triples first (common on some setups)
    if arr_1d.size % 3 == 0:
        data = arr_1d.reshape(-1, 3)
        colmap = {"MAG.": 0, "PHA.": 1, "X.": 0, "Y.": 1}  # adapt if SEND returns X,Y instead of R,Theta
        col = colmap.get(channel_cmd, 0)
        return data[:, col]
    # Try pairs
    if arr_1d.size % 2 == 0:
        return arr_1d.reshape(-1, 2)[:, 0]
    # Fallback: assume it's already the desired column
    return arr_1d

# ---------------- Worker (buffered) ----------------

class DynamicsWorker(QObject):
    """
    Buffered acquisition worker:
      - sets SRAT & SIZE from (dt_s, duration)
      - turns light ON
      - STRT acquisition
      - polls SPTS? to show live progress (and live value via quick MAG./PHA. read)
      - PAUS + SEND at the end to retrieve the full trace
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
        self._stop = False

    @pyqtSlot()
    def run(self):

        n_total = max(1, int(round(self.duration_s / max(self.dt_s, 1e-6))))
        n_total = min(n_total, 65535)  # instrument cap

        inst = None
        try:
            inst = kputils.Connection_Open_RS232(self.rm, verbose=False)

            # Light ON and configure buffer sampler

            _set_light(inst, volts=5.0, channel=2)
            set_sample_rate(inst, self.dt_s)
            set_buffer_points(inst, n_total)

            # Arm acquisition: some instruments prefer a clear/arm sequence; AQN is your "auto-sequence"
            _inst_cmd(inst, "AQN")
            buffer_start(inst)

            last_pts = 0
            last_live_val = float("nan")
            t_start = time.perf_counter()

            # Poll SPTS? ~20 Hz for responsive UI, throttled to not spam serial
            poll_interval = 0.05  # 50 ms
            self._stop = False
            while not self._stop:
                pts = buffer_points_collected(inst)
                pts = max(0, min(pts, n_total))
                print(pts, "of", n_total)

                # Optional: lightweight live value read during acquisition.
                # If your device supports instantaneous read commands (e.g., "MAG.", "PHA."),
                # you can query only the selected channel to show a value without dumping the buffer.
                try:
                    if self.channel_cmd == "PHA.":
                        live_str, _ = _inst_cmd(inst, "PHA.")
                    else:
                        live_str, _ = _inst_cmd(inst, "MAG.")
                    last_live_val = float(str(live_str).strip().split()[0])
                except Exception:
                    # Non-fatal; keep going
                    pass

                t_current = pts * self.dt_s
                self.progress.emit(float(t_current), float(last_live_val))

                if pts >= n_total:
                    self._stop = True
                    break

                # Pace the loop
                time.sleep(poll_interval)

            # Stop and dump buffer
            print("Finalizing capture")
            buffer_pause(inst)
            print("Reading buffer...")
            raw = buffer_send(inst)
            print("Buffer read complete.")
            y = _select_channel_column(raw, self.channel_cmd)
            print("Data parsed.")
            print(y)
            # Build time base to the number of *actual* points returned
            n_eff = min(y.size, n_total)
            y = y[:n_eff]
            t = np.arange(n_eff, dtype=float) * self.dt_s
            self.finished.emit(t, y, self.channel_cmd)

        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")
        finally:
            try:
                if inst is not None:
                    _set_light(inst, volts=0.0, channel=2)  # remove if you want light to stay on
            finally:
                if inst is not None:
                    kputils.Connection_Close(inst, verbose=False)

# ---------------- Synchronous API (buffered) ----------------

def start_capture(rm, duration_s: float, dt_s: float, channel_cmd: str = "MAG.") -> Tuple[np.ndarray, np.ndarray, str]:
    """
    Synchronous capture using buffer mode (no live updates).
    """
    n_total = max(1, int(round(duration_s / max(dt_s, 1e-6))))
    n_total = min(n_total, 65535)

    inst = kputils.Connection_Open_RS232(rm, verbose=False)
    try:
        _set_light(inst, volts=5.0, channel=2)
        set_sample_rate(inst, dt_s)
        set_buffer_points(inst, n_total)
        _inst_cmd(inst, "AQN")
        buffer_start(inst)

        # Busy-wait on SPTS? (short sleeps); you can also compute a deadline from duration_s
        while True:
            pts = buffer_points_collected(inst)
            if pts >= n_total:
                break
            time.sleep(0.05)

        buffer_pause(inst)
        raw = buffer_send(inst)
        y = _select_channel_column(raw, channel_cmd)

        n_eff = min(y.size, n_total)
        y = y[:n_eff]
        t = np.arange(n_eff, dtype=float) * float(dt_s)
        return t, y, channel_cmd
    finally:
        _set_light(inst, volts=0.0, channel=2)
        kputils.Connection_Close(inst, verbose=False)
