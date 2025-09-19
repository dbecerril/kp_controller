"""
Central place for GUI defaults, lock-in maps, and app constants.
Adjust values as needed for your hardware/workflow.
"""

# ---- Lock-in mappings (examples: tune to your SR7265 maps) ----
DICT_TC = {  # time constants shown in UI → instrument codes/seconds if needed
    "10us": 10e-6, "30us": 30e-6, "100us": 100e-6, "300us": 300e-6,
    "1ms": 1e-3, "3ms": 3e-3, "10ms": 10e-3, "30ms": 30e-3,
    "100ms": 0.1, "300ms": 0.3, "1s": 1.0, "3s": 3.0, "10s": 10.0
}
DICT_SENS = {  # example current sensitivities; swap with your exact table
    "1pA": 1e-12, "2pA": 2e-12, "5pA": 5e-12, "10pA": 1e-11,
    "20pA": 2e-11, "50pA": 5e-11, "100pA": 1e-10, "200pA": 2e-10
}

DICT_DEMOD_OPTIONS = {"X":"X.","Y":"Y.","Phase":"PHA.","R":"MAG."}

DICT_TC_TO_SEC = {"20ms":0.02,"50ms":.050,"100ms":.100,"500ms":.500,"1s":1}


LIST_VOLTSP = [  "+"+str(g) + str(h)+"."+str(i) + str(j) + str(k) for g in range(10) for h in range(10) for i in range(10) for j in range(10) for k in range(10)]
LIST_VOLTSN = [  "-"+str(g) + str(h)+"."+str(i) + str(j) + str(k) for g in range(9,-1,-1) for h in range(9,-1,-1) for i in range(9,-1,-1) for j in range(9,-1,-1) for k in range(9,-1,-1)]
LIST_VOLTS= LIST_VOLTSN + LIST_VOLTSP



# ---- App defaults used by tabs ----
DEFAULT_FREQ_HZ = 180.0
DEFAULT_AMP_V   = 0.5
DEFAULT_NAME    = " "
DEFAULT_SCAN    = [-0.300, 0.300, 0.01]  # start, stop, step
DEFAULT_NUMPASS = 1

# Any other constants your code expects from `constants.py`
DELAY_TIMER_MS = 500