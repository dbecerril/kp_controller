# -*- coding: utf-8 -*-
"""
Created on Tue Jun 11 09:55:10 2024

@author: david
"""
import sys
import controllers.kputils as kputils
from PyQt5.QtWidgets import (
    QApplication,QPushButton,
    QCheckBox,QLineEdit,
    QTabWidget,QLabel,
    QVBoxLayout,QFormLayout,QGroupBox,
    QWidget,QComboBox,QHBoxLayout
)

dict_tc = {"20ms":"10","50ms":"11","100ms":"12","500ms":"13","1s":"14"}
dict_demodv = {"X":"X.","Y":"Y.","Phase":"PHA.","R":"MAG."}
dict_sens = {"1pA":"15","2pA":"16","5pA":"17"}
delaytimer  = 500
list_voltsp = [  "+"+str(g) + str(h)+"."+str(i) + str(j) + str(k) for g in range(10) for h in range(10) for i in range(10) for j in range(10) for k in range(10)]
list_voltsn = [  "-"+str(g) + str(h)+"."+str(i) + str(j) + str(k) for g in range(9,-1,-1) for h in range(9,-1,-1) for i in range(9,-1,-1) for j in range(9,-1,-1) for k in range(9,-1,-1)]
list_volts = list_voltsn + list_voltsp


class expTab(QWidget):
    
    def __init__(self,expobj,rm):
        super().__init__()
        self.expobj = expobj
        self.rm = rm
        self.experimentTabUI()  
        self.dcVoltage = 8.0

    def experimentTabUI(self):
        """Create the General page UI."""
        experimentTab = QWidget()
        
        fbox =QFormLayout()
        self.setLayout(fbox)

        label_expname2    = QLabel("File Name")
        self.box_expname = QLineEdit()
        self.box_expname.setText(" ")
        # Scan Parmaeters
        groupBox = QGroupBox("Scan Options")
        label_scanparam = QLabel("Scan Parameters: ")
        fbox_sp = QFormLayout()

        hbox = QHBoxLayout()
        groupBox.setLayout(fbox_sp)

        self.box_eVi = QLineEdit(self)
        self.box_eVi.setText("-0.30")
        
        self.box_eVf = QLineEdit(self)
        self.box_eVf.setText("0.30")
        
        self.box_eVstep = QLineEdit(self)
        self.box_eVstep.setText(".010")
        
        hbox.addWidget(QLabel("Vi"))
        hbox.addWidget(self.box_eVi)
        hbox.addWidget(QLabel("Vf"))
        hbox.addWidget(self.box_eVf)
        hbox.addWidget(QLabel("Vstep"))
        hbox.addWidget(self.box_eVstep)
        fbox_sp.addRow(hbox)
 
        
        self.hboxmscan = QHBoxLayout()
        fbox_sp.addRow(self.hboxmscan)

        # Height Control
        hbox_heightctrl = QHBoxLayout()

        self.dcVstep = QLineEdit(self)
        self.dcVstep.setText("0.5")
        self.dcV_label = QLabel( f"DC Voltage: 8.0 V" )

        hbox_heightctrl.addWidget(QLabel("Step (V):"))

        hbox_heightctrl.addWidget(self.dcVstep)
        self.button_dcVon = QPushButton("Lock")
        self.button_dcVup = QPushButton("+")
        self.button_dcVdown = QPushButton("-")

        hbox_heightctrl.addWidget(self.button_dcVdown)
        hbox_heightctrl.addWidget(self.button_dcVup)
        hbox_heightctrl.addWidget(self.button_dcVon)

        self.button_dcVon.clicked.connect(self.dcVswitch) 
        self.button_dcVup.clicked.connect(self.dcVup)
        self.button_dcVdown.clicked.connect(self.dcVdown)

        #

        hbox2 = QHBoxLayout()
        label_noscans = QLabel("No. of scans: ")
        self.box_noscans = QLineEdit(self)
        self.box_noscans.setText("1")
        label_delay = QLabel("delay (secs) : ")
        self.box_delay = QLineEdit(self)
        self.box_delay.setText("1")    
        
    
        hbox2.addWidget(label_noscans)
        hbox2.addWidget(self.box_noscans)
        hbox2.addWidget(label_delay)
        hbox2.addWidget(self.box_delay)        
        fbox_sp.addRow(hbox2)
        #Start and save buttons
        
        self.button_start = QPushButton("Start")
        label_savedata = QLabel("Save Data: ")
        self.button_stop = QPushButton("Stop")
        self.CkBox_savedata = QCheckBox()
        self.CkBox_savedata.setChecked(True)


        # Fit parameters

        #hbox3.addWidget(self.button_fit )
        #hbox3.addWidget(self.box_fitmodel )


        self.box_expname.textChanged.connect(self.setParameters_exptab)
        self.box_eVstep.textChanged.connect(self.setParameters_exptab)
        self.box_eVf.textChanged.connect(self.setParameters_exptab)
        self.box_eVi.textChanged.connect(self.setParameters_exptab)  


        # Add all widgets to the fbox 
        fbox.addRow(label_expname2)
        fbox.addRow(self.box_expname)

        fbox.addRow(groupBox)
        fbox.addRow(self.button_start)
        fbox.addRow(self.button_stop)

        fbox.addRow(label_savedata,self.CkBox_savedata)
        fbox.addRow(self.dcV_label)
        fbox.addRow(hbox_heightctrl)
    
        return experimentTab
    

    def setParameters_exptab(self):
        
        dtemp = [self.box_eVi.text(),self.box_eVf.text(), self.box_eVstep.text()]

        self.expobj.setScanParam(dtemp)
        self.expobj.setName(self.box_expname.text())

    def dcVswitch(self):
        if self.button_dcVon.text() == "Lock":
            self.button_dcVon.setText("Unlock")
        else:
            self.button_dcVon.setText("Lock")            

    def dcVup(self):
        if self.button_dcVon.text() == "Unlock":
            vstep = 0.0
        else:
            inst     = kputils.Connection_Open_RS232(self.expobj.port, "9600",self.rm,verbose = False)
            try:
                vstep = float(self.dcVstep.text())
            except:
                vstep = 0.0

            self.dcVoltage = self.dcVoltage + vstep
            itemp = kputils.V_to_index( float(self.dcVoltage ))

            kputils.Inst_Query_Command_RS232(inst, "DAC.2"+ list_volts[itemp],verbose = False)
            self.dcV_label.setText( f"DC Voltage: {self.dcVoltage} V" )
            kputils.Connection_Close(inst,verbose = False)

    def dcVdown(self):
        if self.button_dcVon.text() == "Unlock":
            vstep = 0.0
        else:
            inst     = kputils.Connection_Open_RS232(self.expobj.port, "9600",self.rm,verbose = False)
            try:
                vstep = float(self.dcVstep.text())
            except:
                vstep = 0.0

            self.dcVoltage = self.dcVoltage - vstep
            itemp = kputils.V_to_index( float(self.dcVoltage ))

            kputils.Inst_Query_Command_RS232(inst, "DAC.2"+ list_volts[itemp],verbose = False)
            self.dcV_label.setText( f"DC Voltage: {self.dcVoltage} V" )

            kputils.Connection_Close(inst,verbose = False)  
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = expTab(1,2)
#     window.show()
#     sys.exit(app.exec_())