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
        self.timelist = []
        self.biaslist = []
        self.gradientlist = []

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




    def update_plot2(self,timestamp0= 0 ):
        path0 = ".\\kpoutput\\" + f"{self.expsettings.name}\\time_bias_gradient.csv"
        biastemp = 0
        gradienttemp = 0
        if timestamp0 != 0:
            biastemp,gradienttemp = self.fitdata() 
            self.timelist.append(timestamp0/60)
            self.biaslist.append(biastemp)
            self.gradientlist.append(gradienttemp)
        if len(self.biaslist) > 0:
            self.plot_graph2.setTitle(f"Bias Avg:{np.round( np.array(self.biaslist).mean(),3)} V, Std: {np.round( np.array(self.biaslist).std(),3) } V, \n Gradient Avg:{np.round( np.array(self.gradientlist).mean(),2)}  ,Std: {np.round( np.array(self.gradientlist).std(),2)}  ")             
            f = open(path0, 'a')
            f.write(f'{timestamp0/60},{biastemp},{gradienttemp} \n')
            f.close()
            
        self.line = self.plot_graph2.plot(
            self.timelist,
            self.biaslist,
            symbol="o",
            symbolSize=5,
            symbolBrush="b",
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