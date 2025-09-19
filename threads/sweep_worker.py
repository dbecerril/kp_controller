# threads/scan_worker.py
import os
import time
import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal
import controllers.kputils as kputils
import config.constants as constants

def hz_to_indx(x_hz):
    xtemp = int(x_hz*1e3)
    return str(xtemp)
    
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
        time_cte = constants.DICT_TC.get( self.expobj.timeconstant )
        tc_sec   = constants.DICT_TC_TO_SEC.get(self.expobj.timeconstant)
        sens     = constants.DICT_SENS.get(self.expobj.sensitivity )
        inst = kputils.Connection_Open_RS232(self.rm)
        
        #print("Starting dac scan.. \n")
        #print("Centering phase, zeroing dac1...\n")
        indxs = self.scanoptions
        kputils.Inst_Query_Command_RS232(inst, "AQN", verbose = False)
        kputils.Inst_Query_Command_RS232(inst, "TC"+time_cte, verbose = False)
        kputils.Inst_Query_Command_RS232(inst, "SEN"+sens, verbose = False)
        indxx = kputils.V_to_index(indxs[4])
        kputils.Inst_Query_Command_RS232(inst, "DAC.1" + constants.LIST_VOLTS[indxx]  , verbose = False)
        
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
                dataii,tempii = kputils.Inst_Query_Command_RS232(inst, constants.DICT_DEMOD_OPTIONS.get(indxs[3]) ,verbose = False)
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
    