# -*- coding: utf-8 -*-
"""
Created on Tue Jun 11 09:57:57 2024

@author: david
"""
import sys
from PyQt5.QtWidgets import (
    QApplication,QPushButton,
    QCheckBox,QLineEdit,
    QTabWidget,QLabel,
    QVBoxLayout,QFormLayout,
    QWidget,QComboBox,QHBoxLayout
)

dict_tc = {"20ms":"10","50ms":"11","100ms":"12","500ms":"13","1s":"14"}
dict_demodv = {"X":"X.","Y":"Y.","Phase":"PHA.","R":"MAG."}
dict_sens = {"1pA":"15","2pA":"16","5pA":"17","10pA":"18","20pA":"19","50pA":"20"}
delaytimer  = 500

class lockinTab(QWidget):
    
    def __init__(self,expobj,rm):
        super().__init__()
        self.expobj = expobj
        self.rm = rm
        self.lockinTabUI() 

    def lockinTabUI(self):
        """Create the General page UI."""
        lockinTab = QWidget()
        

        fbox =QFormLayout()
        self.setLayout(fbox)

        # Time constant box and label
        label_tc = QLabel("Time Constant: ")
        self.box_tc = QComboBox()
        self.box_tc.addItems(list(dict_tc.keys()))
        self.box_tc.setCurrentText("100ms")

        # sensitivity constant box and label
        label_sens = QLabel("Sensitivity: ")
        self.box_sens = QComboBox()
        self.box_sens.addItems(list(dict_sens.keys()))
        self.box_sens.setCurrentText("2pA")

        # Demod1 box and label
        label_demod1 = QLabel("Demod 1: ")
        self.box_demod1 = QComboBox()
        self.box_demod1.addItems(list(dict_demodv.keys()))

        self.box_demod1.setCurrentText("X")

        # Demod2 box and label
        label_demod2 = QLabel("Demod 2: ")
        self.box_demod2 = QComboBox()
        self.box_demod2.addItems(list(dict_demodv.keys()))
        self.box_demod2.setCurrentText("Phase")

        # Freq box and label
        label_freq = QLabel("Oscillator Frequency (Hz): ")
        self.box_freq = QLineEdit(self)
        self.box_freq.setText("184.9")
        
        # Amplitude box and label
        label_ampl = QLabel("Oscillator Amplitude (V): ")
        self.box_ampl = QLineEdit(self)
        self.box_ampl.setText("0.5")

        self.button_setparams = QPushButton("Set Parameters")


        fbox.addRow(QLabel("Demod variables:"))
        fbox.addRow(label_demod1,self.box_demod1)
        fbox.addRow(label_demod2,self.box_demod2)

        fbox.addRow(QLabel("Lock-in Settings:"))
        fbox.addRow(label_tc,self.box_tc)
        fbox.addRow(label_sens,self.box_sens)    
        fbox.addRow(label_freq,self.box_freq)
        fbox.addRow(label_ampl,self.box_ampl)
        fbox.addRow(self.button_setparams)

        return lockinTab
    
    def setParameters_litab(self):
        
        self.expobj.setTimeConstant(self.box_tc.currentText() )
        self.expobj.setSensitivity(self.box_sens.currentText() )
        self.expobj.setAmp(self.box_ampl.text() )
        self.expobj.setFreq(self.box_freq.text() )
        self.expobj.setdemod1(self.box_demod1.currentText())
        self.expobj.setdemod2(self.box_demod2.currentText())
    
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = lockinTab(1,2)
#     window.show()
#     sys.exit(app.exec_())