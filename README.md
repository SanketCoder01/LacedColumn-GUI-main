# Osdag – Laced Column GUI Module

This repository contains the code for the **Laced Column GUI module** developed for Osdag (Open Source Design and Analysis of Steel Structures).

---

## ⚠️ Important Note

If you **clone the repository using `git clone`**, you may face **database loading errors**.  
To avoid this, we recommend using the **ZIP download method** and following the steps below.

---

## ✅ How to Run the Project

### 1. 📦 Download the ZIP File

- Click the green **`Code`** button at the top of the repo.
- Select **`Download ZIP`**.
- Extract the ZIP to a directory (e.g., `C:\Downloads\LacedColumn-GUI`).

---

### 2. 🛠 Run Your IDE as Administrator

- Open your IDE (e.g., VS Code or PyCharm) **as Administrator**.
- This avoids the **OCC (OpenCascade) error** or database loading issues.
- Sometimes it works without admin rights, but it's more stable in admin mode.

---

### 3. 📁 Set the Correct Path

Before running, make sure you're in the correct path **just before the `src` folder**.

📌 **Example Path:**


Do **not** go inside the `src` folder. Stay in the main folder just before it.

---

### 4. ▶️ Run the Application

In **PowerShell**, use the following command to set the Python path and run Osdag:

$env:PYTHONPATH = "src"
python -m osdag.osdagMainPage

✅ Final Result
I followed the above steps, and I’m happy to share that:

✅ Everything is working properly

✅ The GUI for the Laced Column module runs smoothly

✅ All design calculations and validations are accurate as per IS 800:2007

✅ The module is now fully integrated into the Osdag framework

📝 Modified Files
During development and integration, I made changes to the following files:

1. src/osdag/compression_member/laced_column/lacedcolumn.py – Main logic and design calculation implementation

2. UI.template – GUI integration for inputs, outputs, and module navigation

3. design_preference.ui – Added lacing-related design preference options

4. osdagMainPage.py – Linked the new module to Osdag’s main UI

5. common.py – Utility functions and input parameter handling

6. is800_2007exp.py – Clause-based checks and calculations based on IS 800:2007

References Used
column.py

