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

from PyQt5.QtWidgets import (
    QApplication,QPushButton,
    QCheckBox,QLineEdit,
    QTabWidget,QLabel,
    QVBoxLayout,QFormLayout,
    QWidget,QComboBox,QHBoxLayout
)

from PyQt5.QtCore import QTimer,QThread,pyqtSignal,QObject
from PyQt5 import QtGui
from tabs import sweeptab,exptab,lockintab
from config import constants
DICT_TC_TO_SEC = constants.DICT_TC_TO_SEC
from threads.scan_worker import Worker

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

    def setupUi(self):
        #mainWindow = QWidget()

        self.setWindowTitle("Kelvin Probe GUI")
        self.resize(1000, 450)

        # Create a top-level layout
        
        layout = QVBoxLayout()
        self.setLayout(layout)
      
        #Plots and tabs
        topbox = QHBoxLayout()
       
        # status bar and real time measurment
        self.botbox = QHBoxLayout()


        tabs = QTabWidget()
        
        #Exp tab

        self.experimentTabUI = exptab.expTab(self.expsettings,self.rm)
        self.experimentTabUI.button_start.clicked.connect(self.runScan)
        self.experimentTabUI.button_stop.clicked.connect(self.stopScan)
        
        #Sweep tab        
        self.sweepTabUI = sweeptab.sweepTab(self.expsettings,self.rm)
        self.sweepTabUI.button_start.clicked.connect(self.freqSweep)
        self.sweepTabUI.button_stop.clicked.connect(self.stopSweep)
        
        #Lock in Tab
        self.lockinTabUI = lockintab.lockinTab(self.expsettings,self.rm)
        self.lockinTabUI.button_setparams.clicked.connect(self.set_params)
        
        tabs.addTab(self.experimentTabUI, "Experiment")
        tabs.addTab(self.lockinTabUI, "Lock-in Settings")
        tabs.addTab(self.sweepTabUI, "Sweeps")
        
        plotbox = QVBoxLayout()
        self.plot_graph = pg.PlotWidget()
        self.plot_graph.setTitle("Current Scan")
        self.plot_graph.setLabel("left", self.expsettings.demod1)
        self.plot_graph.setLabel("bottom", "DAC1 (V)")

        self.plot_graph2 = pg.PlotWidget()

        self.plot_graph2.setTitle("Bias History")
        self.plot_graph2.setLabel("left", "Bias (V)")
        self.plot_graph2.setLabel("bottom", "Time (min)")

        plotbox.addWidget(self.plot_graph)

        plotbox.addWidget(self.plot_graph2)
        self.bias_curve = self.plot_graph2.plot([], [], symbol="o", symbolSize=5, symbolBrush="b")

        topbox.addWidget(tabs,25)
        topbox.addLayout(plotbox,75) 
        
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
        
        layout.addLayout(topbox)        
        layout.addLayout(self.botbox)
        

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
        dataR,dataPhi= kputils.update_RP(self.expsettings, self.rm)
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
        savedata = self.experimentTabUI.CkBox_savedata.isChecked()

        #tc_pointdelay = float( self.experimentTabUI.box_pointdelay.text() )
        self.thread = QThread()

        # Step 3: Create a worker object
        self.worker = Worker(self.expsettings,self.rm,[multiscan,avgmultiscans,numscans,savedata,time_between_scans])
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


    def update_plot2(self, timestamp0=0):
        # only act when a new point arrives
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
        datatemp = np.array(data).reshape(-1,3)
        datatemp = pd.DataFrame(datatemp,columns = ["DAC1 (V)",self.expsettings.demod1,self.expsettings.demod2] )
        self.expsettings.datatemp = datatemp
        
    def mV_to_index(self,x_mV):
        idx_temp = int(x_mV)
        
        return idx_temp + 1000       


    def fitdata(self):
        
        fit_model = "linear"
        myFont=QtGui.QFont()
        myFont.setBold(True)

        x,y0,y,res,gradient= kputils.fitLinear(self.expsettings, 
                                        float( self.experimentTabUI.box_eVi.text() ), 
                                        float( self.experimentTabUI.box_eVf.text() ))
        #self.experimentTabUI.label_fittedGradient.setText(f"gradient: {np.round(gradient,3)} ")

        self.plot_graph.clear()
        self.plot_graph.plot(self.expsettings.datatemp["DAC1 (V)"], 
                             self.expsettings.datatemp[self.expsettings.demod1].values*1e12)        
        #self.plot_graph.plot(x, y0,pen ='g')
        
        self.plot_graph.plot(x, y,pen ='r')
        #self.experimentTabUI.label_fitvalue.setText(f"bias: {np.round(res,3)} V")
        #self.experimentTabUI.label_fitvalue.setFont(myFont)

        return res,gradient

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