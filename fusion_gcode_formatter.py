"""
structured_formatter.py
-----------------------
Structured G-code cleaner that:
- Adds standard startup and shutdown blocks
- Removes unwanted setup codes (G80, G54, G50)
- Removes pre-tool G-codes before first T line
- Keeps only machining-relevant lines
- Ensures single % at end
"""

from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog


# ------------------------
# File Utilities
# ------------------------

def read_file(file_path):
    return Path(file_path).read_text().splitlines()

def write_file(file_path, lines):
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).write_text("\n".join(lines))
    print(f"✅ Saved cleaned file to: {file_path}")


# ------------------------
# Filtering Functions
# ------------------------

def keep_relevant_lines(lines):
    kept = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if (
            stripped.startswith(("G", "N", "T", "O"))
            or stripped == "%"
            or stripped == "M99"
        ):
            kept.append(stripped)
        else:
            removed += 1
    print(f"🔹 Kept {len(kept)} lines, removed {removed}.")
    return kept


def tidy_spacing(lines):
    tidy = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                tidy.append("")
            prev_blank = True
        else:
            tidy.append(line)
            prev_blank = False

    final = []
    for line in tidy:
        if line.startswith("T") and final and final[-1] != "":
            final.append("")
        final.append(line)
    return final


def remove_unwanted_gcodes(lines):
    """Remove unwanted setup G-codes that Fusion inserts in tool blocks."""
    banned = ("G80", "G54", "G50", "G90", "G95", "G18")
    filtered = []
    removed = 0

    for line in lines:
        if any(code in line for code in banned):
            removed += 1
            continue
        filtered.append(line)

    return filtered


def strip_preamble(lines):
    cleaned = []
    program_number = None
    found_tool = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "%":
            continue
        if stripped.startswith("O") and stripped[1:].isdigit():
            program_number = stripped
        if stripped.startswith("T") and stripped[1:3].isdigit():
            found_tool = True
        if found_tool:
            cleaned.append(stripped)

    if not program_number:
        program_number = "O0000"
    return program_number, cleaned


def insert_standard_blocks(program_number, lines):
    header = [
        "START",
        "%",
        program_number,
        "N01G50S2000",
        "N02G28U0",
        "N03G28W0",
        "N04M00",
        ""
    ]

    footer = [
        "",
        "G97G30U0W0",
        "M01",
        "M05S1500",
        "G28U0W0M40",
        "M99",
        "%"
    ]
    return header + lines + footer


# ------------------------
# Main Program
# ------------------------

def main():
    root = tk.Tk()
    root.withdraw()

    input_dir = Path("Input")
    initial_dir = input_dir if input_dir.exists() else Path.cwd()

    input_file = filedialog.askopenfilename(
        title="Select Fusion Output File (.nc)",
        initialdir=initial_dir,
        filetypes=[("G-code files", "*.nc"), ("All files", "*.*")]
    )
    if not input_file:
        print("❌ No file selected. Exiting.")
        return

    lines = read_file(input_file)
    filtered = keep_relevant_lines(lines)
    filtered = tidy_spacing(filtered)
    filtered = remove_unwanted_gcodes(filtered)
    program_number, stripped = strip_preamble(filtered)
    final_lines = insert_standard_blocks(program_number, stripped)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    job_name = Path(input_file).stem
    output_dir = Path("Output")
    output_file = output_dir / f"{job_name}_cleaned_{timestamp}.nc"

    write_file(output_file, final_lines)

    print("\n🎯 Preview of cleaned output:")
    for l in final_lines[:20]:
        print(" ", l)
    if len(final_lines) > 20:
        print("  ...")

    print("\n✅ Done!")


# ------------------------
# Run
# ------------------------

if __name__ == "__main__":
    main()
