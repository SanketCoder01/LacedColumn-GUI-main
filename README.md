# Osdag – Laced Column GUI Module

This repository contains the code for the **Laced Column GUI module** developed for [Osdag](https://osdag.fossee.in/) (Open Source Design and Analysis of Steel Structures). The module enables clause-based design of **welded laced compression members** as per **IS 800:2007**, and is fully integrated into the Osdag GUI environment.

---

## ✅ Overview

The Laced Column module supports:

- Input of cross-section, spacing, and lacing details
- Clause-based compressive strength and slenderness calculations
- Full integration with Osdag’s GUI (PyQt-based)
- Export and display of all results including:
  - Effective lengths (yy & zz)
  - Slenderness ratios
  - Design compressive strengths (fcd_yy, fcd_zz)
  - Section classification and utilization ratio (UR)
  - Tie plate and lacing spacing dimensions

---

## ▶️ How to Run

In **PowerShell**, execute:

$env:PYTHONPATH = "src"
python -m osdag.osdagMainPage

 
 * Modified Files

| File                                                       | Purpose                                                    |
| ---------------------------------------------------------- | ---------------------------------------------------------- |
| `src/osdag/compression_member/laced_column/lacedcolumn.py` | Laced column design logic and calculation engine           |
| `UI.template`                                              | GUI layout for input/output fields and navigation          |
| `design_preference.ui`                                     | Preferences panel for lacing pattern/configuration options |
| `osdagMainPage.py`                                         | Registered module into the Osdag main interface            |
| `common.py`                                                | Parameter handling and input utilities                     |
| `is800_2007exp.py`                                         | Clause-based methods from IS 800:2007                      |


| Issue            | Clicking the **Design** button sometimes triggers the **"Are you sure you want to quit?"** confirmation dialog                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Cause            | The `closeEvent()` in `ui_template.py` triggers the dialog when `.close()` is called, even after design                                 |
| Tried Fix        | Setting `self._programmatic_close = True` before `.close()` inside design functions (e.g. `save_parameters()`, `start_loadingWindow()`) |
| ❌ Current Status | **Partially fixed**, but issue **still appears intermittently**, especially in preference or input dialogs                              |
| 🚧 Next Steps    | Continue tracing all `.close()` calls and window instances; ensure all dialogs set `_programmatic_close` before calling `.close()`      |


References Used
column.py
is800_2007exp.py


