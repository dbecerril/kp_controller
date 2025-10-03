import sys
import pyqtgraph as pg
import time
import pyvisa
import controllers.kputils as kputils
import experiment 
import numpy as np
import threading
import queue,os
import pandas as pd
import json  # make sure this is at the top of your file

from PyQt5.QtWidgets import (
    QApplication,QPushButton,
    QCheckBox,QLineEdit,
    QTabWidget,QLabel,
    QVBoxLayout,QFormLayout,
    QWidget,QComboBox,QHBoxLayout
)

from PyQt5.QtWidgets import QTableView, QHeaderView
from PyQt5.QtCore import QAbstractTableModel, Qt, QVariant
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtCore import QTimer,QThread,pyqtSignal,QObject
from PyQt5 import QtGui
from tabs import sweeptab,exptab,lockintab
from config import constants
from PyQt5.QtWidgets import QSplitter, QSizePolicy
from PyQt5.QtWidgets import QSizePolicy
DICT_TC_TO_SEC = constants.DICT_TC_TO_SEC
import tabs
from threads.scan_worker import Worker
from tabs import session
# Step 1: Create a worker class
# We work with the average curve and single curve

class Window(QWidget):
    signalWorker     = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.expsettings = experiment.experiment()
        self.rm = pyvisa.ResourceManager()
        self.biaslist = []
        self.timelist = []
        self.gradientlist = []
        self.setupUi()
        self.bias_history = pd.DataFrame(columns=["time_min", "bias_V", "gradient"])
        self.bias_csv_path = os.path.join("kpoutput", "time_bias_gradient.csv")
        #self.bias_curve = None  # will become a PlotDataItem
        # --- Session storage for saved scans (table + JSONL log) ---
        self.session_records = []  # list of dicts (one per saved scan)
        self.session_df = pd.DataFrame(columns=[
            "timestamp_iso", "sample_name", "bias_V", "bias_V_std", "gradient", "gradient_std", "num_scans",
            "lockin_params_json", "scan_params_json", "session_name"  # <-- added
        ])

        ts_str = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs("kpoutput", exist_ok=True)
        self.session_jsonl_path = os.path.join("kpoutput", f"session_{ts_str}.jsonl")

    def setupUi(self):
        #mainWindow = QWidget()

        self.setWindowTitle("Kelvin Probe GUI")
        self.resize(1150, 450)

        # Create a top-level layout
        
        layout = QVBoxLayout()

        self.setLayout(layout)
        self.botbox = QHBoxLayout()
        
        # --- Left: tabs ---
        tabs_widget = QTabWidget()
        tabs_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.experimentTabUI = exptab.expTab(self.expsettings, self.rm)
        self.experimentTabUI.button_start.clicked.connect(self.runScan)
        self.experimentTabUI.button_stop.clicked.connect(self.stopScan)

        self.sweepTabUI = sweeptab.sweepTab(self.expsettings, self.rm)
        self.sweepTabUI.button_start.clicked.connect(self.freqSweep)
        self.sweepTabUI.button_stop.clicked.connect(self.stopSweep)

        self.lockinTabUI = lockintab.lockinTab(self.expsettings, self.rm)
        self.lockinTabUI.button_setparams.clicked.connect(self.set_params)

        self.sessionTabUI = session.SessionTab()
        self.sessionTabUI.clearRequested.connect(self.clear_session)
        self.sessionTabUI.dataImported.connect(self._on_session_data_imported)

        tabs_widget.addTab(self.experimentTabUI, "Experiment")
        tabs_widget.addTab(self.lockinTabUI, "Lock-in Settings")
        tabs_widget.addTab(self.sweepTabUI, "Sweeps")
        tabs_widget.addTab(self.sessionTabUI, "Session")

        # --- Right: plots (put them in a QWidget so it can be added to splitter) ---
        right_panel = QWidget()
        right_vbox = QVBoxLayout(right_panel)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # <-- grows both ways

        # Optional: vertical splitter inside the right side so users can resize the two plots
        plots_splitter = QSplitter(Qt.Vertical)
        plots_splitter.setChildrenCollapsible(False)  # don't collapse to zero height
        plots_splitter.setHandleWidth(6)
        # Let both plots expand equally by default


        self.plot_graph = pg.PlotWidget()
        self.plot_graph.setTitle("Current Scan")
        self.plot_graph.setLabel("left", self.expsettings.demod1)
        self.plot_graph.setLabel("bottom", "DAC1 (V)")

        self.plot_graph2 = pg.PlotWidget()
        self.plot_graph2.setTitle("Bias History")
        self.plot_graph2.setLabel("left", "Bias (V)")
        self.plot_graph2.setLabel("bottom", "Time (min)")

        plots_splitter.addWidget(self.plot_graph)
        plots_splitter.addWidget(self.plot_graph2)
        plots_splitter.setStretchFactor(0, 1)
        plots_splitter.setStretchFactor(1, 1)
        plots_splitter.setSizes([300, 300])  # initial heights; tweak as you like

        right_vbox.addWidget(plots_splitter,1)

        self.bias_curve = self.plot_graph2.plot([], [], symbol="o", symbolSize=5, symbolBrush="b")

        # --- Top-level horizontal splitter between tabs and plots ---
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(6)
        main_splitter.addWidget(tabs_widget)
        main_splitter.addWidget(right_panel)

        # Initial sizes: 30% left, 70% right (adjust to taste)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([int(self.width() * 0.25), int(self.width() * 0.75)])

        # Optional: wider handle so it’s easy to grab
        main_splitter.setStyleSheet("QSplitter::handle { background: #404040; }")

        # Now add the splitter to your outer layout

        # Bottom widget
        self.timer = QTimer(self)
        self.timer.timeout.connect( self.updateMeasure )
        self.timer.start(constants.DELAY_TIMER_MS) 
        
        self.label_currentR = QLabel("0.0")
        self.label_currentPhi = QLabel("0.0")
        
        self.botbox.addWidget(QLabel("R:"),3)
        self.botbox.addWidget(self.label_currentR,3)
        self.botbox.addWidget(QLabel("pA"),3)
        
        self.botbox.addWidget(QLabel("Phi:"),3)
        self.botbox.addWidget(self.label_currentPhi,3)
        self.botbox.addWidget(QLabel("deg"),3)
        
        self.label_status = QLabel("Status:")
        self.botbox.addWidget(self.label_status,82 )

        self.experimentTabUI.button_save.clicked.connect(self.save_current_scan)

        layout.addWidget(main_splitter,1)
        layout.addLayout(self.botbox,0)    
                

    def _on_session_data_imported(self, df: pd.DataFrame):
        """Receive imported data from SessionTab and adopt it as the current session."""
        self.session_df = df.copy()
        self.refresh_session_table()
        self.label_status.setText("Status: Session table loaded from CSV.")
            
    def refresh_session_table(self):
        # Push current DF to the Session tab
        self.sessionTabUI.update_dataframe(self.session_df)

    def clear_session(self):
        self.session_records = []
        # keep columns, empty rows
        self.session_df = self.session_df.iloc[0:0]
        # rotate JSONL so new saves start a fresh file
        ts_str = time.strftime("%Y%m%d_%H%M%S")
        self.session_jsonl_path = os.path.join("kpoutput", f"session_{ts_str}.jsonl")
        self.refresh_session_table()
        self.label_status.setText("Status: Session cleared.")

    def _safe_getattr(self, obj, name, default=None):
        try:
            return getattr(obj, name)
        except Exception:
            return default

    def _collect_lockin_params(self):
        params = {}
        for k in [
            "tc", "sens", "harm", "freq_hz", "ampl_v", "reserve", "phase_deg",
            "filter_slope", "input_config", "time_constant", "sensitivity"
        ]:
            v = self._safe_getattr(self.expsettings, k, None)
            if v is not None:
                params[k] = v

        ui_map = {
            "box_tc": "tc",
            "box_sens": "sens",
            "box_harm": "harm",
            "box_freq": "freq_hz",
            "box_ampl": "ampl_v",
            "box_reserve": "reserve",
            "box_phase": "phase_deg",
        }
        for widget_name, key in ui_map.items():
            w = self._safe_getattr(self.lockinTabUI, widget_name, None)
            if w is not None:
                try:
                    if hasattr(w, "currentText"):
                        params[key] = w.currentText()
                    elif hasattr(w, "text"):
                        params[key] = w.text()
                except Exception:
                    pass
        return params

    def _collect_scan_params(self):
        params = {}
        ui_map = {
            "box_eVi": "eV_start",
            "box_eVf": "eV_stop",
            "box_eVstep": "eV_step",     # matches your expTab
            "box_noscans": "num_scans",
            "box_delay": "delay_between_scans_s",
            #"CkBox_savedata": "savedata",
        }
        for widget_name, key in ui_map.items():
            w = self._safe_getattr(self.experimentTabUI, widget_name, None)
            if w is None:
                continue
            try:
                if hasattr(w, "isChecked"):
                    params[key] = bool(w.isChecked())
                elif hasattr(w, "currentText"):
                    params[key] = w.currentText()
                elif hasattr(w, "text"):
                    params[key] = w.text()
            except Exception:
                pass
        params["demod1_label"] = self._safe_getattr(self.expsettings, "demod1", None)
        params["demod2_label"] = self._safe_getattr(self.expsettings, "demod2", None)
        return params

    def save_current_scan(self):
        bias_v,bias_std, gradient, gradient_std, num_scans = self.fitdata_to_session()
        print("fitdata_to_session:", bias_v, bias_std, gradient, gradient_std, num_scans)
        # Require data
        if self.expsettings.data_multscan is None:
            self.label_status.setText("Status: No data to save (run a scan first).")
            return

        # Compute bias & gradient
        try:
            bias_v,bias_std, gradient, gradient_std, num_scans = self.fitdata_to_session()
            print("fitdata_to_session:", bias_v, bias_std, gradient, gradient_std, num_scans)
            bias_v = float(bias_v) if bias_v is not None else None
            gradient = float(gradient) if gradient is not None else None
            bias_std = float(bias_std) if bias_std is not None else None
            gradient_std = float(gradient_std) if gradient_std is not None else None

        except Exception:
            bias_v, bias_std, gradient, gradient_std,num_scans = None, None, None, None, None

        # Metadata
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            sample_name = self.experimentTabUI.box_samplename.text().strip()
        except Exception:
            sample_name = ""

        lockin_params = self._collect_lockin_params()
        scan_params   = self._collect_scan_params()

        record = {
            "timestamp_iso": timestamp_iso,
            "sample_name": sample_name,
            "bias_V": np.round(bias_v,3) if bias_v is not None else None,
            "bias_V_std": np.round(bias_std,3) if bias_std is not None else None,
            "gradient": np.round(gradient,3) if gradient is not None else None,
            "gradient_std": np.round(gradient_std,3) if gradient_std is not None else None,
            "num_scans": num_scans,
            "lockin_params": lockin_params,
            "scan_params": scan_params,
        }

        # In-memory
        self.session_records.append(record)
        # Pull current session name from the Session tab
        try:
            session_name = self.sessionTabUI.get_session_name().strip()
        except Exception:
            session_name = ""
        # --- build the row dict (unchanged) ---
        row = {
            "timestamp_iso": timestamp_iso,
            "sample_name": sample_name,
            "bias_V": float(bias_v) if bias_v is not None else np.nan,
            "bias_V_std": float(bias_std) if bias_std is not None else np.nan,
            "gradient": float(gradient) if gradient is not None else np.nan,
            "gradient_std": float(gradient_std) if gradient_std is not None else np.nan,
            "num_scans": num_scans,
            "lockin_params_json": json.dumps(lockin_params),
            "scan_params_json": json.dumps(scan_params),
            "session_name": self.sessionTabUI.get_session_name().strip() if hasattr(self.sessionTabUI, "get_session_name") else "",
        }

        # --- make a 1-row DataFrame with the SAME columns as self.session_df ---
        new_row = pd.DataFrame([row], columns=self.session_df.columns)

        # --- drop all-NA columns from the row to avoid the deprecation path ---
        new_row = new_row.dropna(axis=1, how='all')

        # --- concat only non-empty frames (kills the warning path) ---
        frames = []
        if not self.session_df.empty:
            frames.append(self.session_df)
        if not new_row.empty:
            frames.append(new_row)

        if frames:
            self.session_df = pd.concat(frames, ignore_index=True, copy=False)
        else:
            # If both were empty (unlikely), initialize with expected columns
            self.session_df = pd.DataFrame(columns=[
                "timestamp_iso","sample_name","bias_V","bias_V_std","gradient","gradient_std","num_scans",
                "lockin_params_json","scan_params_json","session_name"
            ])

        # push to the Session tab
        self.refresh_session_table()


######################################
### Logic Functions  start here
###################################
    def stopScan(self):
        try:
            self.signalWorker.emit()
        except:
            print("No thread")

    def stopSweep(self):
        try:
            self.sweepTabUI.signalWorker.emit()
        except:
            print("No thread")

    def set_params(self):
        self.timer.stop()
        self.lockinTabUI.setParameters_litab()

        kputils.setLockinParams(self.expsettings,self.rm)
        
        self.timer.start(constants.DELAY_TIMER_MS) 

   

    def updateMeasure(self):
        dataR,dataPhi= kputils.update_RP( self.rm)
        try:
            dataR = str( np.round( float(dataR)*1E12,3)  )
        except:
            dataR = "--"
        try:
            dataPhi = str( np.round( float(dataPhi), 2)  )
        except:
            dataPhi = "--"
            
        self.label_currentR.setText(dataR)
        self.label_currentPhi.setText(dataPhi)
        
    def runScan(self):
        self.plot_graph.clear()
        self.plot_graph2.clear()
        self.bias_history = pd.DataFrame(columns=["time_min", "bias_V", "gradient"])

        self.bias_curve = self.plot_graph2.plot([], [], symbol="o", symbolSize=5, symbolBrush="b")
        self.timelist = []
        self.biaslist = []
        self.gradientlist = []
        
        self.bias_curve.setData([], [])
        # reset csv path in case name changed mid-session
        self.bias_csv_path = os.path.join("kpoutput", "time_bias_gradient.csv")



        self.expsettings.datatemp = pd.DataFrame([])
        self.timer.stop()
        numscans  = int(self.experimentTabUI.box_noscans.text()) 

        if numscans > 1:
            multiscan = True
        else:
            multiscan = False

        time_between_scans = self.experimentTabUI.box_delay.text() 
        avgmultiscans = False
        #savedata = self.experimentTabUI.CkBox_savedata.isChecked()

        #tc_pointdelay = float( self.experimentTabUI.box_pointdelay.text() )
        self.thread = QThread()

        # Step 3: Create a worker object
        self.worker = Worker(self.expsettings,self.rm,[multiscan,avgmultiscans,numscans,time_between_scans])
        self.signalWorker.connect(self.worker.listen)
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.sendfinaldata.connect(self.updateExpObjData)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.worker.update.connect(self.updateCurrentPlot)
        self.worker.updategraph2.connect(self.update_plot2)
        #self.worker.update2.connect(self.updateAvgPlot)
        self.worker.clearsinglecurve.connect(self.clearCurrentPlot)
        self.worker.clearplot.connect(self.clearPlot)

        # Step 6: Start the thread
        self.thread.start()

        # Final resets
        self.experimentTabUI.button_start.setEnabled(False)

        self.thread.finished.connect(
            lambda: self.experimentTabUI.button_start.setEnabled(True)
        )
        self.thread.finished.connect(
            lambda: self.timer.start(constants.DELAY_TIMER_MS)
        )
    def on_dynamics_data_ready(self, t, y, label):
    # Plot on the right-side plot
        self.updateDynamicsPlot(t, y, ylabel=label)

    def updateDynamicsPlot(self, t, y, ylabel):
        """Plot dynamics data on the main right-side plot."""
        self.plot_graph.clear()
        self.plot_graph.setLabel("bottom", "Time (s)")
        self.plot_graph.setLabel("left", ylabel)
        # draw as markers to mirror your style; change as you prefer
        self.plot_graph.plot(t, y, symbol='o', symbolSize=4, symbolBrush=0.01, name='Dynamics')

    def update_plot2(self, timestamp0=0):
        # only act when a new point arrives7
        if not timestamp0:
            return

        # 1) compute bias & gradient from current data
        bias_v, gradient = self.fitdata()
        t_min = float(timestamp0) / 60.0

        # 2) append to in-memory lists
        self.timelist.append(t_min)
        self.biaslist.append(float(bias_v))
        self.gradientlist.append(float(gradient))

        # 3) append one row to CSV (header once)
        try:
            folder = os.path.dirname(self.bias_csv_path)
            os.makedirs(folder, exist_ok=True)
            write_header = not os.path.exists(self.bias_csv_path) or os.path.getsize(self.bias_csv_path) == 0
            with open(self.bias_csv_path, "a", encoding="utf-8") as f:
                if write_header:
                    f.write("time_min,bias_V,gradient\n")
                f.write(f"{t_min},{bias_v},{gradient}\n")
        except Exception:
            pass  # ignore file errors during plotting

        # 4) update the plot using the single persistent curve
        if self.bias_curve is None:
            self.bias_curve = self.plot_graph2.plot([], [], symbol="o", symbolSize=5, symbolBrush="b")
        self.bias_curve.setData(self.timelist, self.biaslist)

        # 5) update the title with mean/std
        b = np.array(self.biaslist, dtype=float)
        g = np.array(self.gradientlist, dtype=float)
        self.plot_graph2.setTitle(
            f"Bias Avg:{np.round(b.mean(),3)} V, Std:{np.round(b.std(),3)} V,\n"
            f"Gradient Avg:{np.round(g.mean(),2)}, Std:{np.round(g.std(),2)}"
        )

        #return mainWindow
    def updateCurrentPlot(self,data):
        datatemp = np.array(data).reshape(-1,3)
        datatemp = pd.DataFrame(datatemp,columns = ["DAC1 (V)",self.expsettings.demod1,self.expsettings.demod2] )
        self.plot_graph.plot(datatemp["DAC1 (V)"], datatemp[self.expsettings.demod1].values*1e12, symbol ='o', name ='Current Scan',symbolBrush = 0.01,symbolSize = 5)
        #self.plot_graph.plot(datatemp["DAC1 (V)"], datatemp[self.expsettings.demod2].values, symbol ='o', name ='Current Scan',symbolBrush = 0.01,symbolSize = 5)

        self.plot_graph.setLabel("bottom", "DAC1 (V)")

    def updateSweepPlot(self,data):
        datatemp = np.array(data).reshape(-1,2)
        self.plot_graph.setLabel("bottom", "Frequency (Hz)")
        self.plot_graph.setLabel("left", self.sweepTabUI.box_demod1.currentText())

        datatemp = pd.DataFrame(datatemp,columns = ["Frequency (Hz)",self.expsettings.demod1] )
        self.plot_graph.plot(datatemp["Frequency (Hz)"], datatemp[self.expsettings.demod1].values*1e12, symbol ='o', name ='Frequency Sweep',symbolBrush = 0.01,symbolSize = 5)
     
    def clearPlot(self):
        self.plot_graph.clear()

    def clearCurrentPlot(self,data):
        self.plot_graph.clear()
        datatemp = np.array(data).reshape(-1,3)
        datatemp = pd.DataFrame(datatemp,columns = ["DAC1 (V)",self.expsettings.demod1,self.expsettings.demod2] )
        self.plot_graph.plot(datatemp["DAC1 (V)"], datatemp[self.expsettings.demod1].values*1e12,pen ='b', symbolPen ='b',symbol ='o', name ='Average',symbolBrush = 0.01,symbolSize = 5)
        #self.plot_graph.plot(datatemp["DAC1 (V)"], datatemp[self.expsettings.demod2].values*1e12,pen ='g', symbolPen ='b',symbol ='o', name ='Average',symbolBrush = 0.01,symbolSize = 5)
        

    def updateExpObjData(self,data):

        self.expsettings.data_multscan = data
        self.expsettings.datatemp = pd.DataFrame(data[-1],columns = ["DAC1 (V)",self.expsettings.demod1,self.expsettings.demod2] )

    def mV_to_index(self,x_mV):
        idx_temp = int(x_mV)
        
        return idx_temp + 1000       


    def fitdata(self):
        
        # fit_model = "linear"
        myFont=QtGui.QFont()
        myFont.setBold(True)

        x,y0,y,res,gradient= kputils.fitLinear(self.expsettings, 
                                        float( self.experimentTabUI.box_eVi.text() ), 
                                        float( self.experimentTabUI.box_eVf.text() ))

        self.plot_graph.clear()
        self.plot_graph.plot(self.expsettings.datatemp["DAC1 (V)"], 
                             self.expsettings.datatemp[self.expsettings.demod1].values*1e12)        
        
        self.plot_graph.plot(x, y,pen ='r')


        return res,gradient
    
    def fitdata_to_session(self):
        avg_grad, avg_xint, std_grad, std_xint = kputils.fitLinear_batch_np(self.expsettings.data_multscan,
                                                                            float( self.experimentTabUI.box_eVi.text() ), 
                                                                            float( self.experimentTabUI.box_eVf.text() ))

        return  avg_xint,std_xint, avg_grad, std_grad, len(self.expsettings.data_multscan)
    
    def hz_to_indx(self,x_hz):
        xtemp = int(x_hz*1e3)
        return str(xtemp)
    
    def freqSweep(self):
        self.plot_graph.clear()
        self.expsettings.datatemp = pd.DataFrame([])
        self.timer.stop()

        #tc_pointdelay = float( self.experimentTabUI.box_pointdelay.text() )
        self.thread = QThread()
        fi = float( self.sweepTabUI.box_fi.text())
        ff = float( self.sweepTabUI.box_ff.text())
        fstep = float( self.sweepTabUI.box_fstep.text())
        demod = self.sweepTabUI.box_demod1.currentText()
        vbias0 = self.sweepTabUI.bias.text()
        # Step 3: Create a worker object
        self.worker = sweeptab.sweepWorker(self.expsettings,self.rm,[ fi, ff, fstep,demod,vbias0])
        self.sweepTabUI.signalWorker.connect(self.worker.listen)
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.runSweep)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.worker.updateplot.connect(self.updateSweepPlot)
        # Step 6: Start the thread
        self.thread.start()

        # Final resets
        self.sweepTabUI.button_start.setEnabled(False)

        self.thread.finished.connect(
            lambda: self.sweepTabUI.button_start.setEnabled(True)
        )
        self.thread.finished.connect(
            lambda: self.timer.start(constants.DELAY_TIMER_MS)
        )
                    

                
if __name__ == "__main__":
      
    rm = pyvisa.ResourceManager() 
    app = QApplication(sys.argv)
    # Apply dark theme if available
    try:
        with open('styles/dark.qss','r',encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    except Exception:
        pass
    window = Window()
    window.show()
    sys.exit(app.exec_())