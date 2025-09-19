# -*- coding: utf-8 -*-
"""
Created on Tue Jun 11 09:55:10 2024

@author: david
"""
import sys
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


   
class calibrationTab(QWidget):
    
    def __init__(self,expobj,rm):
        super().__init__()
        self.expobj = expobj
        self.rm = rm
        self.calibrationTab()     
      
    def calibrationTab(self):
        calibration_tab = QWidget()
        layout =QFormLayout()
        self.setLayout(layout)
        groupBox = QGroupBox("Mesh Calibration")
        formbox1 = QFormLayout()
        self.box_meshwf = QLineEdit(self)
        self.box_meshwf.setText("4.66")
        groupBox.setLayout(formbox1)
        formbox1.addRow(QLabel("Mesh Work Function (Volts) :"), self.box_meshwf )  
        layout.addWidget(groupBox)


        return calibration_tab
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = calibrationTab(1,2)
    window.show()
    sys.exit(app.exec_())