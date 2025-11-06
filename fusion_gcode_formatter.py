"""
FusionFormatter
---------------
- Adds standard header/footer
- Removes unwanted setup codes (G80, G54, G50, G90, G95, G18) and Fusion's G96/G97 lines
- Uses tools.json to inject per-tool header:
    Nxx0 (<display>)
    G30U0W0
    Txxxx
    G140M08
    G99<type>S<speed>F<feed>
- Places G30U0W0 + M01 AFTER each tool's machining path
- Derives N-number from tool number (T0700 -> N700, T0300 -> N300)
- Robust TOOL_KEY parsing (handles spaces/variants) and detection before/after tool line
"""

from pathlib import Path
from datetime import datetime
from tkinter import Tk, filedialog
import json
import re


# ----------------------------- IO -----------------------------

def read_file(file_path: Path) -> list[str]:
    return Path(file_path).read_text().splitlines()

def write_file(file_path: Path, lines: list[str]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).write_text("\n".join(lines))
    print(f"✅ Saved cleaned file to: {file_path}")

def load_tool_data(path: str = "tools.json") -> dict:
    """Load tool data and normalise keys to lowercase."""
    p = Path(path)
    if p.exists():
        with p.open("r") as f:
            data = json.load(f)
        return {str(k).strip().lower(): v for k, v in data.items()}
    print("⚠️ No tools.json found — continuing without tool data.")
    return {}


# -------------------------- Cleaning --------------------------

def keep_relevant_lines(lines: list[str]) -> list[str]:
    """Keep machining-relevant lines (let M30/M99 pass; we'll suppress later)."""
    kept, removed = [], 0
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith(("G", "N", "T", "O", "(")) or s in {"%", "M99", "M30"}:
            kept.append(s)
        else:
            removed += 1
    if removed:
        print(f"🔹 Kept {len(kept)} lines, removed {removed}.")
    return kept

def tidy_spacing(lines: list[str]) -> list[str]:
    tidy = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                tidy.append("")
            prev_blank = True
        else:
            tidy.append(line)
            prev_blank = False
    return tidy

def remove_unwanted_gcodes(lines: list[str]) -> list[str]:
    """
    Remove setup/redundant lines that START with these codes.
    IMPORTANT: We only strip lines that START with G96/G97 so our generated 'G99G96...' line remains.
    """
    banned_prefixes = ("G80", "G54", "G50", "G90", "G95", "G18", "G96", "G97")
    filtered, removed = [], 0
    for line in lines:
        s = line.strip()
        if any(s.startswith(code) for code in banned_prefixes):
            removed += 1
            continue
        filtered.append(line)
    if removed:
        print(f"⚙️ Removed {removed} unwanted or redundant lines (start-with filter).")
    return filtered

def strip_preamble(lines: list[str]) -> tuple[str, list[str]]:
    """Strip everything before first tool; return program number."""
    cleaned = []
    program_number = None
    found_tool = False
    for line in lines:
        s = line.strip()
        if not s or s == "%":
            continue
        if s.startswith("O") and s[1:].isdigit():
            program_number = s
        if s.startswith("T") and s[1:3].isdigit():
            found_tool = True
        if found_tool:
            cleaned.append(s)
    if not program_number:
        program_number = "O0000"
    return program_number, cleaned


# ----------------------- Tool Utilities -----------------------

tool_re = re.compile(r"^T(\d+)")
key_regex = re.compile(r"(?i)tool[\s_\-]*key\s*[:=]\s*(.+)")

def n_from_tool(tool_line: str) -> str:
    """Build N-number from the first two digits of the tool number."""
    m = tool_re.match(tool_line)
    if not m:
        return "N100"
    digits = m.group(1)
    try:
        num = int(digits[:2]) if len(digits) >= 2 else int(digits)
    except ValueError:
        num = 1
    return f"N{num * 100}"

def parse_tool_key(raw: str) -> str:
    """
    Accepts lines like:
      (TOOL_KEY=UDRILL50)
      (TOOL_KEY = UDRILL50)
      (UDRILL50)
      (Tool Key: UDRILL50)
    Returns the parsed key in lowercase with surrounding spaces removed.
    """
    content = raw.strip().strip("()").strip()
    m = key_regex.search(content)
    if m:
        key = m.group(1).strip()
    else:
        key = content
    return key.lower()

def build_tool_block(tool_number: str, tool_key: str, tool_data: dict) -> list[str]:
    """Build the per-tool header (no trailing G30/M01 here)."""
    key_lc = tool_key.lower()
    info = tool_data.get(key_lc)
    if not info:
        print(f"⚠️ TOOL_KEY '{tool_key}' not found in JSON.")
        return [
            f"{n_from_tool(tool_number)} (UNKNOWN TOOL)",
            "G30U0W0",
            tool_number,
            "G140M08"
        ]

    display = info.get("display", "(UNKNOWN TOOL)")
    tool_type = info.get("type", "G96")
    speed = info.get("speed", "200")
    feed = info.get("feed", ".25")

    return [
        f"{n_from_tool(tool_number)} {display}",
        "G30U0W0",
        tool_number,
        "G140M08",
        f"G99{tool_type}S{speed}F{feed}",
    ]


# --------------------- Header / Footer ------------------------

def insert_standard_blocks(program_number: str, body: list[str]) -> list[str]:
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
        "M05S1500",
        "G28U0W0M40",
        "M99",
        "%"
    ]
    return header + body + footer


# --------------------------- Main -----------------------------

def main():
    # Pick a file
    Tk().withdraw()
    input_file = filedialog.askopenfilename(
        title="Select Fusion Output File (.nc)",
        initialdir=Path.cwd(),
        filetypes=[("G-code files", "*.nc"), ("All files", "*.*")]
    )
    if not input_file:
        print("❌ No file selected. Exiting.")
        return

    # Load & pre-clean
    lines = read_file(input_file)
    lines = keep_relevant_lines(lines)
    lines = tidy_spacing(lines)
    lines = remove_unwanted_gcodes(lines)
    program_number, lines = strip_preamble(lines)

    tool_data = load_tool_data()

    final = []
    current_tool_key = None     # last seen key (normalised to lowercase)
    active_tool = False         # are we inside a toolpath?

    i = 0
    L = len(lines)

    while i < L:
        s = lines[i].strip()

        # Capture TOOL_KEY comments anywhere; store for next tool
        if s.startswith("(") and s.endswith(")"):
            parsed = parse_tool_key(s)
            if parsed:
                current_tool_key = parsed
            i += 1
            continue

        # Tool change
        if s.startswith("T") and s[1:3].isdigit():
            tool_line = s

            # Close previous toolpath
            if active_tool:
                final.append("G30U0W0")
                final.append("M01")
                final.append("")
                active_tool = False

            # Prefer most recent key; if absent, look around
            key = current_tool_key

            # Look ahead up to 30 lines for a key
            if not key:
                for j in range(i + 1, min(i + 31, L)):
                    probe = lines[j].strip()
                    if probe.startswith("(") and probe.endswith(")"):
                        k = parse_tool_key(probe)
                        if k:
                            key = k
                            break

            # If still not found, look backward up to 15 lines
            if not key and i > 0:
                for j in range(i - 1, max(i - 16, -1), -1):
                    probe = lines[j].strip()
                    if probe.startswith("(") and probe.endswith(")"):
                        k = parse_tool_key(probe)
                        if k:
                            key = k
                            break

            # Build tool header
            final.extend(build_tool_block(tool_line, key or "", tool_data))
            active_tool = True
            current_tool_key = None
            i += 1
            continue

        # End-of-program markers: close active tool, do NOT emit M30/M99 (footer handles end)
        if s in {"M99", "M30"}:
            if active_tool:
                final.append("G30U0W0")
                final.append("M01")
                final.append("")
                active_tool = False
            i += 1
            continue  # suppress M30/M99 from body

        # Pass-through normal lines
        final.append(s)
        i += 1

    # File ended mid-tool
    if active_tool:
        final.append("G30U0W0")
        final.append("M01")

    # Wrap header/footer and save
    output_lines = insert_standard_blocks(program_number, final)
    ts = datetime.now().strftime("%H-%M-%S_%d-%m-%Y")
    out_path = Path("Output") / f"{Path(input_file).stem}_cleaned_{ts}.nc"
    write_file(out_path, output_lines)

    # Preview
    print("\n🎯 Preview (first 30 lines):")
    for line in output_lines[:30]:
        print(" ", line)
    if len(output_lines) > 30:
        print("  ...")
    print("✅ Done.")


if __name__ == "__main__":
    main()
