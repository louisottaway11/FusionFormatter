# 🌀 FusionFormatter

**FusionFormatter** is a structured G-code cleaner that standardises and simplifies Fusion 360 post-processed NC programs for CNC lathes using FANUC-style controls.  
It automatically applies your preferred start/end blocks, removes redundant setup codes, and outputs a clean, production-ready `.nc` file.

---

## 🚀 Features

- Adds consistent **startup and shutdown blocks**
- Removes redundant setup codes
- Strips pre-tool preamble and keeps only machining-relevant lines
- Ensures a **single `%`** at the end of the file
- Outputs cleaned files to a dedicated `Output/` folder
- Cross-platform: works on **Windows** and **macOS**

---

## ⚙️ How to Use

1. Run the formatter:
   ```bash
   python fusion_gcode_formatter.py
