# Lens Inspection Report Generator

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-Desktop_GUI-41CD52?style=flat&logo=qt&logoColor=white)
![matplotlib](https://img.shields.io/badge/matplotlib-Visualizations-11557C?style=flat)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

A desktop tool for ophthalmic lens generator acceptance testing. Parses optical measurement data, evaluates pass/fail criteria with conformity logic, and generates PDF reports with heatmap visualizations and color-coded acceptance summaries.

---

## Features

- **Automated file discovery:** Scans input directories for expected files across multiple test sets.
- **Pass/Fail evaluation:** Applies acceptance logic including for design conformity criteria.
- **PDF Report Generation:** Each report includes a title page, color-coded acceptance summary, and per-lens detail pages with heatmaps
- **Side-by-Side Comparison:** GUI displays file presence status for Equipment subcomparments in parallel card layouts
- **Batch report generation:** Generate reports for multiple test sets with live progress tracking
- **CLI support:** Run `report_generator.py` standalone to batch-generate PDFs without the GUI

---

## Report LayouR

Each generated PDF contains:

1. **Title page:** Lab, Equipment, and Subcompartment identification
2. **Acceptance summary:** Color-coded table showing Pass/Fail Verdict for all lenses with failure mode details.
3. **Per-lens detail pages:** Heatmaps and Criteria Table per each individual lens.

---

## Project Structure

```
lens-inspection-report-generator/
├── gui.py                 # PyQt6 desktop interface
├── lens_processing.py     # Core parsing, evaluation, and file discovery
├── report_generator.py    # PDF report generation (also runs standalone)
├── input/                 # Place lab data folders here
│   └── 605.Technopark.28693/
│       ├── FT1/
│       │   ├── *.ddf
│       │   └── *.pmf
│       └── FT2/
│           ├── *.ddf
│           └── *.pmf
├── output/                # Generated PDF reports
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## Input Directory Format

Lab folders follow the naming convention: `{lab_number}.{lab_name}.{generator_serial}`

```
input/
└── 123.LabName.EquipmentSN/
    ├── Subcompartment 1/
    │   ├── [lens]_VER0_[...].ddf
    │   ├── [lens]_VER0_[...].pmf
    │   ├── [lens]_VER1_[...].ddf
    │   ├── [lens]_VER1_[...].pmf
    │   ├── [lens]_VERC_[...].ddf
    │   ├── [lens]_VERC_[...].pmf
    │   ├── [lens]_VERD1_[...].ddf
    │   ├── [lens]_VERD1_[...].pmf
    │   ├── [lens]_VERD2_[...].ddf
    │   ├── [lens]_VERD2_[...].pmf
    │   ├── [lens]_VERD3_[...].ddf
    │   └── [lens]_VERD3_[...].pmf
    └── Subcompartment 2/
        └── ...
```

---

## Installation

```bash
git clone https://github.com/yourusername/lens-inspection-report-generator.git
cd lens-inspection-report-generator
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

---

## Usage

### Desktop GUI

```bash
python gui.py
```

- Select labs from the sidebar
- Review file presence status in the side-by-side subcompartment cards
- Choose which reports to generate from the right panel
- Click **Generate PDF Reports**. Output goes to `./output/`

### Command Line

```bash
python report_generator.py
python report_generator.py --input ./input --output ./reports
```

---|

---

## Requirements

- Python 3.10+
- PyQt6
- numpy
- matplotlib
- reportlab

---

## License

MIT
