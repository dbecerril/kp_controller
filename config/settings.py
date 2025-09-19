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
