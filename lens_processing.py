"""
lens_processing.py

Core parsing, evaluation, and file-discovery logic for ophthalmic lens
DDF / PMF quality data.  No GUI or plotting dependencies.

PMF key format:  {RTC|DBP}_{power}_{type}
    power: T=transmission, F=front reflection
    type combinations: CE=cylinder error, DE=diopter error,
                       CM=cylinder measure, DM=diopter measure, etc.
    Example: "RTC_TCE" = RTC transmission cylinder error
"""

import os
import re
import csv

import numpy as np


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
OFFICIAL_CRITERIA = {
    "DBP Tx":  r"dbp.*best.*fit.*tx",
    "DBP Ty":  r"dbp.*best.*fit.*ty",
    "DBP Rz":  r"dbp.*best.*fit.*rz",
    "FLGMC":   r"full.?lens.?gmc",
    "CGMC":    r"center.?gmc",
    "CPA":     r"center.?power.?(average|avg)",
}

# Short display names for report tables
CRITERIA_SHORT_NAMES = {
    "DBP Tx": "DBP Tx",
    "DBP Ty": "DBP Ty",
    "DBP Rz": "DBP Rz",
    "FLGMC":  "FLGMC",
    "CGMC":   "CGMC",
    "CPA":    "CPA",
}

# Design criteria — these get the RTC-fail-but-DBP-pass exemption
DESIGN_CRITERIA = ["FLGMC", "CGMC", "CPA"]

LENS_TYPES = ["ver0", "ver1", "verc", "verd1", "verd2", "verd3"]

LENS_DISPLAY_NAMES = {
    "ver0": "Lens 0",
    "ver1": "Lens 1",
    "verc": "Lens C",
    "verd1": "Lens D1",
    "verd2": "Lens D2",
    "verd3": "Lens D3",
}


# ──────────────────────────────────────────────
# PMF Processing
# ──────────────────────────────────────────────
class PmfProcessor:
    """Parse PMF files and extract powermap arrays.

    Keys are structured as: "{RTC|DBP}_{front_or_trans}{power}{measure}"
    e.g.  "RTC_TCE" = RTC, Transmission, Cylinder, Error
          "DBP_TDE" = DBP, Transmission, Diopter, Error
    """

    def __init__(self):
        self.powermaps = {}

    def parse_pmf_file(self, file_path):
        with open(file_path, "r") as csvfile:
            file_reader = csv.reader(csvfile, delimiter=";", lineterminator="\n")
            content = list(file_reader)

        # Preprocess: strip PP= prefixes and replace ? with nan
        for row in content:
            for i in range(len(row)):
                row[i] = row[i].replace("PP=", "")
                if row[i] == "?":
                    row[i] = "nan"

        powermaps = {}
        for i, row in enumerate(content):
            if not row or not row[0].startswith("PMFMT="):
                continue

            # Row format: PMFMT=;eye;front_trans;power;measure;xcols;ycols;...;...;...;...;rtc_dbp
            # Indices:      0     1      2         3     4      5     6    7  8  9  10   11
            try:
                x_count = int(row[5])
                y_count = int(row[6])
            except (IndexError, ValueError):
                continue

            # Determine RTC vs DBP from index 11
            try:
                rtc_or_dbp = "RTC" if row[11].strip() == "0" else "DBP"
            except IndexError:
                rtc_or_dbp = "RTC"

            # Build key: e.g. "RTC_TCE"
            front_trans = row[2]   # F or T
            power = row[3]         # C, D, A, S
            measure = row[4]       # M, T, E (measure, theoretical/reference, error)
            map_key = f"{rtc_or_dbp}_{front_trans}{power}{measure}"

            # Extract powermap data
            powermap_raw = []
            for j in range(x_count):
                if i + 1 + j >= len(content):
                    break
                row_data = content[i + 1 + j]
                try:
                    processed_row = [float(val) for val in row_data]
                except ValueError:
                    processed_row = []
                    for val in row_data:
                        try:
                            processed_row.append(float(val))
                        except ValueError:
                            processed_row.append(float("nan"))
                powermap_raw.append(processed_row)

            if len(powermap_raw) == x_count:
                powermaps[map_key] = np.array(powermap_raw)

        return powermaps


# ──────────────────────────────────────────────
# DDF Parsing
# ──────────────────────────────────────────────
def parse_ddf_file(file_path):
    """Parse a DDF file and return (rtc_data, dbp_data).

    Each is a dict keyed by criteria short name, with values:
        {"passed": int, "value": float, "tolerance": float}
    """
    with open(file_path, "r") as file:
        content = file.read()

    content = content.replace("PP=", "")

    rtc_section = re.search(
        r"DDFMT=1;R;8;0(.*?)(?:DDFMT=1;R;8;1|$)", content, re.DOTALL
    )
    dbp_section = re.search(
        r"DDFMT=1;R;8;1(.*?)$", content, re.DOTALL
    )

    if not rtc_section:
        raise ValueError(
            f"Invalid DDF file format: RTC section not found in {file_path}"
        )

    rtc_data = _parse_section(rtc_section.group(1))
    dbp_data = _parse_section(dbp_section.group(1)) if dbp_section else None
    return rtc_data, dbp_data


def _parse_section(section):
    """Parse one section (RTC or DBP) of a DDF file."""
    criteria = {}
    for line in section.strip().split("\n"):
        line = line.replace("PP=", "").replace("DD=", "")
        parts = line.split(";")
        if len(parts) < 6:
            continue

        name = parts[2].strip()
        passed = int(parts[3]) if parts[3].strip().isdigit() else 0

        try:
            value = float(parts[4]) if parts[4].strip() not in ("?", "") else float("nan")
        except ValueError:
            value = float("nan")

        try:
            tolerance = float(parts[5]) if parts[5].strip() not in ("?", "") else float("nan")
        except ValueError:
            tolerance = float("nan")

        for official_name, pattern in OFFICIAL_CRITERIA.items():
            if re.search(pattern, name, re.IGNORECASE):
                criteria[official_name] = {
                    "passed": passed,
                    "value": value,
                    "tolerance": tolerance,
                }
                break

    return criteria


# Keep backward compat alias
parse_section = _parse_section


# ──────────────────────────────────────────────
# Lens evaluation logic
# ──────────────────────────────────────────────
def evaluate_lens(rtc_data, dbp_data, lens_type):
    """Evaluate a single lens.

    Rules:
      - All 6 criteria must pass in RTC.
      - BUT if a design criterion (FLGMC, CGMC, CPA) fails in RTC
        but passes in DBP, the lens still passes.
      - For positioning lenses (ver0, ver1, verc), only design criteria
        are evaluated from RTC.

    Returns: (verdict, rtc_failed, dbp_failed, notes)
        verdict: "Pass", "Fail", or "Missing"
    """
    all_criteria = list(OFFICIAL_CRITERIA.keys())

    # Determine which criteria failed in RTC
    if lens_type.lower() in ["ver0", "ver1", "verc"]:
        # Only check design criteria for these lens types
        rtc_failed = [
            c for c in DESIGN_CRITERIA
            if c in rtc_data and not rtc_data[c]["passed"]
        ]
    else:
        rtc_failed = [
            c for c in all_criteria
            if c in rtc_data and not rtc_data[c]["passed"]
        ]

    if dbp_data is None:
        verdict = "Pass" if not rtc_failed else "Fail"
        return verdict, rtc_failed, [], "DBP Missing"

    # Check DBP for design criteria
    dbp_failed = [
        c for c in DESIGN_CRITERIA
        if c in dbp_data and not dbp_data[c]["passed"]
    ]

    # Apply the exemption: if a design criterion failed RTC but passed DBP,
    # it's not actually a failure
    true_failures = []
    for c in rtc_failed:
        if c in DESIGN_CRITERIA:
            # Check if DBP rescued it
            if c in dbp_data and dbp_data[c]["passed"]:
                continue  # Rescued by DBP — not a true failure
        true_failures.append(c)

    verdict = "Pass" if len(true_failures) == 0 else "Fail"
    notes = ""
    rescued = [c for c in rtc_failed if c not in true_failures]
    if rescued:
        notes = f"RTC fail rescued by DBP: {', '.join(rescued)}"

    return verdict, rtc_failed, dbp_failed, notes


def find_lens_file(folder, lens_type, extension=".ddf"):
    if not os.path.exists(folder):
        return None
    pattern = re.compile(f"{lens_type}", re.IGNORECASE)
    for filename in os.listdir(folder):
        if filename.lower().endswith(extension) and pattern.search(filename):
            return os.path.join(folder, filename)
    return None


# ──────────────────────────────────────────────
# Lab folder processing
# ──────────────────────────────────────────────
def process_lab_folder(lab_folder, fast_tool_folder):
    """Process all lens files in a fast tool folder.

    Returns: (lens_results, pmf_data)

    lens_results: list of dicts, one per lens:
        {
            "lens": "VERD1",
            "display": "Lens D1",
            "verdict": "Pass" | "Fail" | "Missing" | "Error",
            "rtc_data": {...} or None,
            "dbp_data": {...} or None,
            "rtc_failed": [...],
            "dbp_failed": [...],
            "notes": str,
        }

    pmf_data: dict keyed by lens_type, each containing:
        {
            "RTC": {"RTC_TCE": array, "RTC_TDE": array, ...},
            "DBP": {"DBP_TCE": array, "DBP_TDE": array, ...},
        }
    """
    if not os.path.exists(fast_tool_folder):
        raise FileNotFoundError(
            f"{fast_tool_folder} folder not found in {lab_folder}"
        )

    lens_results = []
    pmf_data = {}

    for lens_type in LENS_TYPES:
        result = {
            "lens": lens_type.upper(),
            "display": LENS_DISPLAY_NAMES[lens_type],
            "verdict": "Missing",
            "rtc_data": None,
            "dbp_data": None,
            "rtc_failed": [],
            "dbp_failed": [],
            "notes": "",
        }

        ddf_file = find_lens_file(fast_tool_folder, lens_type, ".ddf")

        if ddf_file:
            try:
                rtc_data, dbp_data = parse_ddf_file(ddf_file)
                verdict, rtc_failed, dbp_failed, notes = evaluate_lens(
                    rtc_data, dbp_data, lens_type
                )
                result.update({
                    "verdict": verdict,
                    "rtc_data": rtc_data,
                    "dbp_data": dbp_data,
                    "rtc_failed": rtc_failed,
                    "dbp_failed": dbp_failed,
                    "notes": notes,
                })
            except Exception as e:
                print(f"Error processing {ddf_file}: {e}")
                result["verdict"] = "Error"
                result["notes"] = str(e)

        # PMF data
        pmf_file = find_lens_file(fast_tool_folder, lens_type, ".pmf")
        if pmf_file:
            try:
                processor = PmfProcessor()
                maps = processor.parse_pmf_file(pmf_file)
                if maps:
                    rtc_maps = {k: v for k, v in maps.items() if k.startswith("RTC")}
                    dbp_maps = {k: v for k, v in maps.items() if k.startswith("DBP")}
                    pmf_data[lens_type] = {"RTC": rtc_maps, "DBP": dbp_maps}
            except Exception as e:
                print(f"Error processing PMF {pmf_file}: {e}")

        lens_results.append(result)

    return lens_results, pmf_data


def compute_overall_result(lens_results):
    """Compute overall test pass/fail from lens results.

    Returns: (verdict, pass_count, total)
    """
    verdicts = [r["verdict"] for r in lens_results]
    pass_count = sum(1 for v in verdicts if v == "Pass")
    missing_count = sum(1 for v in verdicts if v == "Missing")
    total = len(lens_results)

    if missing_count > 1:
        return "Too Many Missing", pass_count, total

    # Need at least 5 of 6 to pass
    verdict = "Pass" if pass_count >= 5 else "Fail"
    return verdict, pass_count, total
