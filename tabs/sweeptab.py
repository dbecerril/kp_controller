# -*- coding: utf-8 -*-
"""
Created on Mon Jun 10 14:54:52 2024

@author: david
"""
import numpy as np
import pandas as pd
import sys,time
import controllers.kputils as kputils
from PyQt5.QtCore import QTimer,QThread,pyqtSignal,QObject
from PyQt5.QtWidgets import (
    QApplication,QPushButton,
    QCheckBox,QLineEdit,
    QTabWidget,QLabel,
    QVBoxLayout,QFormLayout,
    QWidget,QComboBox,QHBoxLayout
)

dict_tc = {"20ms":"10","50ms":"11","100ms":"12","500ms":"13","1s":"14"}
dict_tc_to_sec = {"20ms":0.02,"50ms":.050,"100ms":.100,"500ms":.500,"1s":1}
dict_demodv = {"X":"X.","Y.":"Y","Phase":"PHA.","R":"MAG."}
dict_sens = {"1pA":"15","2pA":"16","5pA":"17","10pA":"18","20pA":"19","50pA":"20"}
list_voltsp = [  "+"+str(g) + str(h)+"."+str(i) + str(j) + str(k) for g in range(10) for h in range(10) for i in range(10) for j in range(10) for k in range(10)]
list_voltsn = [  "-"+str(g) + str(h)+"."+str(i) + str(j) + str(k) for g in range(9,-1,-1) for h in range(9,-1,-1) for i in range(9,-1,-1) for j in range(9,-1,-1) for k in range(9,-1,-1)]
list_volts = list_voltsn + list_voltsp
# Step 1: Create a worker class
# We work with the average curve and single curve
class sweepWorker(QObject) :

    finished     = pyqtSignal()
    # used to clear single plot but has to send avg plot
    # so replots avg plot.
    updateplot    = pyqtSignal(object)

    def __init__(self,expobj,rm,scan_options ):
        QObject.__init__(self)
        self.expobj = expobj
        self.rm = rm
        self.scanoptions = scan_options
        self.terminate = False

    def listen(self):
        if self.terminate == False:
            self.terminate = True
        else:
            self.terminate = False

    def runSweep(self):                      
        time_cte = dict_tc.get( self.expobj.timeconstant )
        tc_sec   = dict_tc_to_sec.get(self.expobj.timeconstant)
        sens     = dict_sens.get(self.expobj.sensitivity )
        inst = kputils.Connection_Open_RS232(self.expobj.port, "9600",self.rm)
        
        #print("Starting dac scan.. \n")
        #print("Centering phase, zeroing dac1...\n")
        indxs = self.scanoptions
        kputils.Inst_Query_Command_RS232(inst, "AQN", verbose = False)
        kputils.Inst_Query_Command_RS232(inst, "TC"+time_cte, verbose = False)
        kputils.Inst_Query_Command_RS232(inst, "SEN"+sens, verbose = False)
        indxx = kputils.V_to_index(indxs[4])
        kputils.Inst_Query_Command_RS232(inst, "DAC.1" + list_volts[indxx]  , verbose = False)
        
        scanrange = np.arange(indxs[0], indxs[1],indxs[2])
        
        datai = []
        count= 0 
        for freqi in scanrange:
            if self.terminate == True:
                break
            #set DAC value
            cmmdi = "OF" + hz_to_indx(freqi)
            kputils.Inst_Query_Command_RS232(inst, cmmdi,verbose = False) 
            
            if count == 0:
                time.sleep(2)
            else:
                time.sleep(1*tc_sec)  
            dataMag = 0.0
            temp = 0.0
            for i in range(10):
                dataii,tempii = kputils.Inst_Query_Command_RS232(inst, dict_demodv.get(indxs[3]) ,verbose = False)
                try:
                    dataMag += float(dataii)
                    temp += float(tempii)
                except:
                    dataMag = dataMag
            dataMag = dataMag/5
            temp = temp/5

            count +=1        

            datai.append(freqi)
            datai.append(kputils.checkLockinDataFormat(dataMag) )
            self.updateplot.emit(datai)

        data = np.array(datai).reshape(-1,2)
            
        kputils.Connection_Close(inst)
        self.finished.emit()
        return pd.DataFrame(data,columns = ["Freq. (Hz) ",indxs[3]] )
    
def hz_to_indx(x_hz):
    xtemp = int(x_hz*1e3)
    return str(xtemp)
    
class sweepTab(QWidget):
    signalWorker     = pyqtSignal()

    
    def __init__(self,expobj,rm):
        super().__init__()
        self.expobj = expobj
        self.rm = rm
        self.setUpSweepTab()     
      
    def setUpSweepTab(self):
      """Create the General page UI."""
      sweep_tab = QWidget()
      layout =QFormLayout()
      self.setLayout(layout)

      # Demod1 box and label
      self.box_demod1 = QComboBox()
      self.box_demod1.addItems(list(dict_demodv.keys()))
      self.box_demod1.setCurrentText("R")

      fbox = QHBoxLayout()
      fbox.addWidget(QLabel("Freq. start") )
      self.box_fi = QLineEdit(self)
      self.box_fi.setText("170")
      fbox.addWidget(self.box_fi )

      fbox.addWidget(QLabel("Freq. stop") )
      self.box_ff = QLineEdit(self)
      self.box_ff.setText("190")     
      fbox.addWidget(self.box_ff )

      fbox.addWidget(QLabel("Freq. step") )
      self.box_fstep = QLineEdit(self)
      self.box_fstep.setText("1")     
      fbox.addWidget(self.box_fstep )
      self.bias = QLineEdit(self)
      self.bias.setText("0.0")
      fbox.addWidget(QLabel("Vbias") )
      fbox.addWidget(self.bias)

      self.button_start = QPushButton("Start Fequency Sweep")
      self.button_stop = QPushButton("Stop Fequency Sweep")

      self.label_rfreq = QLabel("Resonant Frequency: ")
      
      layout.addRow(QLabel("Demod variable:"),self.box_demod1)
      layout.addRow(fbox)
      layout.addRow(self.label_rfreq)
      layout.addRow(self.button_start)
      layout.addRow(self.button_stop)


      return sweep_tab
    
    
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = sweepTab(1,2)
#     window.show()
#     sys.exit(app.exec_())