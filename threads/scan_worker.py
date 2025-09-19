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
        self.savedata = scan_options[3]
        self.terminate = False
        self.timebetweenscans = scan_options[4]

    def listen(self):
        if self.terminate is False:
            self.terminate = True

    def fitdata(self):
        x, y0, y, res, gradient = kputils.fitLinear(
            self.expobj,
            float(self.expobj.scanparams[0] / 2),
            float(self.expobj.scanparams[1] / 2)
        )
        return res, gradient

    def stampData(self, df0, path0, start_time):
        with open(path0, 'a') as f:
            timestamp = (time.time() - start_time)
            f.write(f'# {timestamp} secs \n')
            exp_dict = self.expobj.getSettings()
            for keys, values in exp_dict.items():
                f.write(f'# {keys} : {values} \n')
            df0.to_csv(f)

    def lockGradient(self, gradient0):
        inst = kputils.Connection_Open_RS232(self.rm)
        tcRatio = 1
        kputils.Inst_Query_Command_RS232(inst, "AQN", verbose=False)
        kputils.Inst_Query_Command_RS232(inst, "DAC1+00000", verbose=False)
        scanrange = list(np.arange(
            kputils.V_to_index(float(self.expobj.scanparams[0] / 2)),
            kputils.V_to_index(float(self.expobj.scanparams[1] / 2)),
            int(float(self.expobj.scanparams[2]) * 1000)
        ))

        nn = 0
        crit = 0.1
        # NOTE: gradi is defined below in the loop, kept as-is to preserve original behavior
        while nn < 10 and np.abs(gradi) - gradient0 > crit:
            a = 1 if np.abs(gradi) > gradient0 else 2

            datai = []
            count = 0
            for i in scanrange:
                if self.terminate is True:
                    break
                datai.append(kputils.dacScanStep(i, self.expobj, inst, tcRatio, count))
                self.update.emit(datai)
                count += 1
            resi, gradi = self.fitdata(np.array(datai).reshape(-1, 3))

    def run(self):
        path0 = ".\\kpoutput\\" + f"{self.expobj.name}\\"
        if self.savedata:
            try:
                os.mkdir(path0)
            except Exception:
                self.terminate = True

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
                self.sendfinaldata.emit(dataout)
                self.updategraph2.emit(time.time() - start_time)

                if self.savedata:
                    datacsv = pd.DataFrame(
                        dataout, columns=["DAC1 (V)", self.expobj.demod1, self.expobj.demod2]
                    )
                    self.stampData(datacsv, path0 + self.expobj.name + f"scan_{ii}.csv", start_time)

            if self.multiscan:
                time.sleep(float(self.timebetweenscans))

        self.clearsinglecurve.emit(dataout)
        self.terminate = False
        kputils.Inst_Query_Command_RS232(inst, "DAC1+00000", verbose=False)
        kputils.Connection_Close(inst)
        self.finished.emit()
