
# Non-breaking reorganization (requested)

- Moved GUI tabs into `tabs/`: {
  "calibrationtab.py": "tabs/calibrationtab.py",
  "exptab.py": "tabs/exptab.py",
  "lockintab.py": "tabs/lockintab.py",
  "sweeptab.py": "tabs/sweeptab.py"
}
- Moved lock-in APIs and helpers into `controllers/`: {
  "kputils.py": "controllers/kputils.py",
  "kelvinprobe.py": "controllers/kelvinprobe.py"
}
- Added `styles/dark.qss` and applied it from `main.py` (purely aesthetic).
- All features (poller, live plots, all buttons) are preserved. No class names or signatures changed.
- Added `__init__.py` to new folders to make imports work cleanly.
