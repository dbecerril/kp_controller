# threads/scan_worker.py
import os
import time
import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal
import controllers.kputils as kputils

# This is the same Worker you had in main.py
class Worker(QObject):
    finished = pyqtSignal()
    updategraph2 = pyqtSignal(object)
    update = pyqtSignal(object)
    clearsinglecurve = pyqtSignal(object)
    clearplot = pyqtSignal()
    sendfinaldata = pyqtSignal(object)

    def __init__(self, expobj, rm, scan_options):
        QObject.__init__(self)
        self.expobj = expobj
        self.rm = rm
        self.multiscan = scan_options[0]
        self.avgmultiscan = scan_options[1]
        self.numpass = scan_options[2]
        self.terminate = False
        self.timebetweenscans = scan_options[3]

    def listen(self):
        if self.terminate is False:
            self.terminate = True

    def run(self):

        inst = kputils.Connection_Open_RS232(self.rm)
        start_time = time.time()
        kputils.Inst_Query_Command_RS232(inst, "DAC1+00000", verbose=False)
        scanrange = list(np.arange(
            kputils.V_to_index(float(self.expobj.scanparams[0])),
            kputils.V_to_index(float(self.expobj.scanparams[1])),
            int(float(self.expobj.scanparams[2]) * 1000)
        ))

        # dict_tc_to_sec is only used to lookup; if you need it here, import from the caller or constants.
        dataout = np.zeros((len(scanrange), 3))
        numpass = self.numpass if self.multiscan else 1
        data_multscan = []
        for ii in range(numpass):
            datai = []
            tcRatio = 1
            self.clearplot.emit()
            if self.terminate is True:
                break

            count = 0
            for i in scanrange:
                if self.terminate is True:
                    break
                datai.append(kputils.dacScanStep(i, self.expobj, inst, tcRatio, count))
                self.update.emit(datai)
                count += 1

            if self.terminate is not True:
                datai = np.array(datai).reshape(-1, 3)
                dataout = datai
                data_multscan.append(datai)
                self.sendfinaldata.emit(data_multscan)
                self.updategraph2.emit(time.time() - start_time)


            if self.multiscan:
                time.sleep(float(self.timebetweenscans))

        self.clearsinglecurve.emit(dataout)
        self.terminate = False
        kputils.Inst_Query_Command_RS232(inst, "DAC1+00000", verbose=False)
        kputils.Connection_Close(inst)
        self.finished.emit()
