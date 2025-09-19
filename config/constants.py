"""
Central place for GUI defaults, lock-in maps, and app constants.
Adjust values as needed for your hardware/workflow.
"""

# ---- Lock-in mappings (examples: tune to your SR7265 maps) ----
DICT_TC = {"5ms":"8","10ms":"9","20ms":"10","50ms":"11","100ms":"12","500ms":"13","1s":"14"}
DICT_SENS = {  # example current sensitivities; swap with your exact table
    "1pA": 15, "2pA": 16, "5pA": 17, "10pA": 18,
    "20pA": 19, "50pA": 20, "100pA": 21, "200pA": 22
}

DICT_DEMOD_OPTIONS = {"X":"X.","Y":"Y.","Phase":"PHA.","R":"MAG."}

DICT_TC_TO_SEC = {"5ms":0.005,"10ms":0.01,"20ms":0.02,"50ms":.050,"100ms":.100,"500ms":.500,"1s":1}


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