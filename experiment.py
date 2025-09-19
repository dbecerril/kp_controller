import pandas as pd
import config.settings as settings

class experiment:

    def __init__(self):
        self.timeconstant = settings.INITIAL_TIME_CONSTANT
        self.sensitivity  = settings.INITIAL_SENSITIVITY
        self.demod1       = settings.INITIAL_DEMOD1
        self.demod2       = settings.INITIAL_DEMOD2
        self.freq         = settings.INITIAL_FREQ_HZ
        self.amp          = settings.INITIAL_AMP_V
        self.name         = " "
        self.port         = settings.RS232_PORT_NAME
        self.scanparams   = settings.INITIAL_SCAN_PARAMS
        self.numpass      = 1
        self.data         = []
        self.datanotes    = []
        self.datatemp     = pd.DataFrame([])
        
    def setTimeConstant(self,x):
        self.timeconstant = x

    def setSensitivity(self,x):
        self.sensitivity = x

    def setdemod1(self,x):
        self.demod1 = x
    
    def setdemod2(self,x):
        self.demod2 = x
    
    def setAmp(self,x):
        self.amp = x
    def setScanParam(self,x):
        self.scanparams = x

    def setFreq(self,x):
        self.freq = x
    
    def setName(self,x):
        self.name = x

    def addData(self,x):
        self.data.append(x)
        exp_dict = {"Time Constant":self.timeconstant,
                    "Sensitivity":self.sensitivity,
                    "Demod 1": self.demod1,
                    "Demod 2": self.demod2,
                    "Frequency": self.freq,
                    "Amplitude": self.amp,
                    "Name": self.name}
        
        self.datanotes.append(exp_dict)

    def getSettings(self):

        exp_dict = {"Time Constant":self.timeconstant,
                    "Sensitivity":self.sensitivity,
                    "Demod 1": self.demod1,
                    "Demod 2": self.demod2,
                    "Frequency": self.freq,
                    "Amplitude": self.amp,
                    "Scan Param.":self.scanparams,
                    "Name": self.name}
        
        return exp_dict