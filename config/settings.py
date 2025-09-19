# config/settings.py
"""
VISA backend configuration.

Set VISA_LIBRARY to one of:
- "auto" (default): try environment variable, common Windows DLLs, NI backend "@py", then pyvisa default
- an explicit path, e.g. r"C:/Windows/System32/visa32.dll" or r"C:/Windows/System32/visa64.dll"
- a backend string like "@py" for PyVISA-py

Tip: You can also set the environment variable PYVISA_LIBRARY to override at runtime.
"""

VISA_LIBRARY = "C:/Windows/System32/visa64.dll"  # "auto" or r"C:/Windows/System32/visa64.dll", or "@py"
RS232_PORT_NAME = "ASRL7::INSTR"  # e.g. "ASRL5::INSTR"
BAUD_RATE = 9600  # e.g. 9600

## INITIAL SETTINGS FOR THE EXPERIMENT OBJECT
INITIAL_TIME_CONSTANT = "100ms" # e.g. "100ms"  
INITIAL_SENSITIVITY = "20pA"    # e.g. "20pA"
INITIAL_DEMOD1 = "X"            # e.g. "X"
INITIAL_DEMOD2 = "Phase"        # e.g. "Phase"
INITIAL_FREQ_HZ = 180           # e.g. 180
INITIAL_AMP_V = 0.25            # e.g. 0.25
INITIAL_SCAN_PARAMS = [-3.00, 3.00, 0.1]  # e.g. [-3.00, 3.00, 0.1] for start, stop, step