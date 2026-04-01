"""
report_generator.py

PDF report generation for lens quality data.
Dark-mode styled reports with DDF tables and PMF heatmaps.

Layout per lens: 2 rows (RTC top, DBP bottom) × 3 cols (DDF table, Cyl error, Dpt error)
Plus a title page and acceptance summary table.

    python report_generator.py
    python report_generator.py --input ./input --output ./reports
"""

import os
import re
import argparse
import math

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patheffects as path_effects

from lens_processing import (
    LENS_TYPES,
    LENS_DISPLAY_NAMES,
    CRITERIA_SHORT_NAMES,
    DESIGN_CRITERIA,
    process_lab_folder,
    compute_overall_result,
)


# ──────────────────────────────────────────────
# Dark mode theme for matplotlib
# ──────────────────────────────────────────────
DARK_BG = "#1a1a1a"
DARK_CARD = "#242424"
DARK_TEXT = "#e0e0e0"
DARK_MUTED = "#888888"
GREEN = "#1DB954"
RED = "#E85D5D"
ORANGE = "#F5A623"
BLUE = "#4A9FD9"


def _setup_dark_style():
    """Apply dark theme to matplotlib."""
    matplotlib.rcParams.update({
        "figure.facecolor": DARK_BG,
        "axes.facecolor": DARK_CARD,
        "axes.edgecolor": "#444444",
        "axes.labelcolor": DARK_TEXT,
        "text.color": DARK_TEXT,
        "xtick.color": DARK_MUTED,
        "ytick.color": DARK_MUTED,
        "grid.color": "#333333",
        "savefig.facecolor": DARK_BG,
        "savefig.edgecolor": DARK_BG,
        "font.family": "sans-serif",
        "font.size": 10,
    })


# ──────────────────────────────────────────────
# Visualization: powermap heatmap
# ──────────────────────────────────────────────
def visualize_powermap(ax, powermap, title, v_max=0.3, v_min=-0.3):
    """Draw a contourf heatmap on the given axes."""
    ax.set_title(title, fontsize=12, color=DARK_TEXT, pad=8)
    ax.set_xlabel("X position, mm", fontsize=9, color=DARK_MUTED)
    ax.set_ylabel("Y position, mm", fontsize=9, color=DARK_MUTED)

    x_axis = np.linspace(-20, 20, powermap.shape[1])
    y_axis = np.linspace(-20, 20, powermap.shape[0])
    X, Y = np.meshgrid(x_axis, y_axis)
    masked = np.ma.masked_where(np.isnan(powermap), powermap)

    contour = ax.contourf(
        X, Y, masked,
        levels=np.linspace(v_min, v_max, 25),
        cmap="nipy_spectral",
        extend="both",
    )
    cbar = plt.colorbar(contour, ax=ax, shrink=0.85)
    cbar.set_label("Power, dpt", fontsize=8, color=DARK_MUTED)
    cbar.ax.tick_params(labelsize=7, colors=DARK_MUTED)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2)
    return contour


# ──────────────────────────────────────────────
# Visualization: DDF criteria table
# ──────────────────────────────────────────────
def draw_ddf_table(ax, section_data, section_label):
    """Draw a color-coded pass/fail table for one DDF section (RTC or DBP)."""
    ax.axis("off")
    ax.set_title(f"{section_label} Go/No-Go", fontsize=12, color=DARK_TEXT, pad=8)

    if section_data is None:
        ax.text(
            0.5, 0.5, f"No {section_label} Data",
            ha="center", va="center", fontsize=14, color=DARK_MUTED,
            transform=ax.transAxes,
        )
        return

    criteria_order = ["DBP Tx", "DBP Ty", "DBP Rz", "FLGMC", "CGMC", "CPA"]
    col_labels = ["Criteria", "Status", "Value", "Tolerance"]

    table_data = []
    cell_colors = []

    for crit in criteria_order:
        if crit in section_data:
            d = section_data[crit]
            passed = d["passed"]
            value = d["value"]
            tolerance = d["tolerance"]

            status = "PASS" if passed else "FAIL"
            val_str = f"{value:.3f}" if not math.isnan(value) else "—"
            tol_str = f"{tolerance:.3f}" if not math.isnan(tolerance) else "—"

            if passed:
                row_color = [(0.11, 0.72, 0.33, 0.35)] * 4  # green tint
            else:
                row_color = [(0.91, 0.36, 0.36, 0.35)] * 4  # red tint
        else:
            status = "N/A"
            val_str = "—"
            tol_str = "—"
            row_color = [(0.3, 0.3, 0.3, 0.3)] * 4

        short = CRITERIA_SHORT_NAMES.get(crit, crit)
        table_data.append([short, status, val_str, tol_str])
        cell_colors.append(row_color)

    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        cellColours=cell_colors,
        colWidths=[0.28, 0.2, 0.26, 0.26],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)

    # Style header row
    for j in range(4):
        cell = table[0, j]
        cell.set_text_props(color=DARK_TEXT, fontweight="bold", fontsize=9)
        cell.set_facecolor(DARK_CARD)
        cell.set_edgecolor("#444444")

    # Style data rows
    for i in range(len(table_data)):
        for j in range(4):
            cell = table[i + 1, j]
            cell.set_text_props(color=DARK_TEXT, fontsize=9)
            cell.set_edgecolor("#333333")


# ──────────────────────────────────────────────
# Visualization: acceptance summary table
# ──────────────────────────────────────────────
def draw_acceptance_summary(lens_results, overall_verdict, pass_count, total):
    """Create a full-page acceptance summary figure."""
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor(DARK_BG)

    fig.text(
        0.5, 0.92, "Acceptance Summary",
        ha="center", va="center", fontsize=22, color=DARK_TEXT,
        fontweight="bold",
    )

    ax = fig.add_subplot(111)
    ax.axis("off")

    # Build table data
    col_labels = ["Lens", "Verdict", "RTC Failures", "DBP Failures", "Notes"]
    table_data = []
    cell_colors = []

    for r in lens_results:
        verdict = r["verdict"]
        rtc_fail_str = ", ".join(r["rtc_failed"]) if r["rtc_failed"] else "—"
        dbp_fail_str = ", ".join(r["dbp_failed"]) if r["dbp_failed"] else "—"
        notes = r["notes"] or "—"

        if verdict == "Pass":
            row_color = [(0.11, 0.72, 0.33, 0.3)] * 5
        elif verdict == "Fail":
            row_color = [(0.91, 0.36, 0.36, 0.3)] * 5
        elif verdict == "Missing":
            row_color = [(0.5, 0.5, 0.5, 0.3)] * 5
        else:
            row_color = [(0.96, 0.65, 0.14, 0.3)] * 5

        table_data.append([r["display"], verdict, rtc_fail_str, dbp_fail_str, notes])
        cell_colors.append(row_color)

    # Overall row
    if overall_verdict == "Pass":
        ov_color = [(0.11, 0.72, 0.33, 0.5)] * 5
    else:
        ov_color = [(0.91, 0.36, 0.36, 0.5)] * 5

    table_data.append([
        "OVERALL", overall_verdict, f"{pass_count}/{total} passed", "", ""
    ])
    cell_colors.append(ov_color)

    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        cellColours=cell_colors,
        colWidths=[0.12, 0.1, 0.22, 0.22, 0.34],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.5)

    # Style headers
    for j in range(5):
        cell = table[0, j]
        cell.set_text_props(color=DARK_TEXT, fontweight="bold", fontsize=11)
        cell.set_facecolor(DARK_CARD)
        cell.set_edgecolor("#444444")

    # Style data rows
    for i in range(len(table_data)):
        for j in range(5):
            cell = table[i + 1, j]
            cell.set_text_props(color=DARK_TEXT, fontsize=10)
            cell.set_edgecolor("#333333")

    return fig


# ──────────────────────────────────────────────
# Main PDF report generation
# ──────────────────────────────────────────────
def generate_enhanced_pdf_report(
    lens_results, output_file, lab_name, generator_sn, fast_tool, pmf_data=None
):
    """Generate a dark-mode PDF report.

    Each lens gets a page with:
        Row 0 (RTC): DDF table | Cylinder Error | Diopter Error
        Row 1 (DBP): DDF table | Cylinder Error | Diopter Error
    """
    _setup_dark_style()
    pdf = PdfPages(output_file)

    # ── Title page ──
    title_fig = plt.figure(figsize=(11, 8.5))
    title_fig.patch.set_facecolor(DARK_BG)
    title_text = (
        f"Generator Acceptance Internal Report\n\n"
        f"Lab {lab_name}\n"
        f"Generator {generator_sn}, {fast_tool}"
    )
    title_fig.text(
        0.5, 0.5, title_text,
        ha="center", va="center", fontsize=20, color=DARK_TEXT,
        fontweight="bold", linespacing=1.8,
    )
    pdf.savefig(title_fig)
    plt.close(title_fig)

    # ── Acceptance summary page ──
    overall_verdict, pass_count, total = compute_overall_result(lens_results)
    summary_fig = draw_acceptance_summary(
        lens_results, overall_verdict, pass_count, total
    )
    pdf.savefig(summary_fig)
    plt.close(summary_fig)

    # ── Per-lens pages ──
    for result in lens_results:
        lens_type = result["lens"].lower()
        display = result["display"]
        verdict = result["verdict"]
        rtc_data = result["rtc_data"]
        dbp_data = result["dbp_data"]

        fig, axes = plt.subplots(2, 3, figsize=(21, 11))
        fig.patch.set_facecolor(DARK_BG)

        # Suptitle with verdict color
        if verdict == "Pass":
            verdict_color = GREEN
        elif verdict == "Fail":
            verdict_color = RED
        elif verdict == "Missing":
            verdict_color = DARK_MUTED
        else:
            verdict_color = ORANGE

        fig.suptitle(
            f"{display}  —  {verdict.upper()}",
            fontsize=20, color=verdict_color, fontweight="bold", y=0.97,
        )

        # Row labels
        fig.text(0.02, 0.72, "RTC", fontsize=28, color=DARK_MUTED,
                 rotation=90, va="center", fontweight="bold")
        fig.text(0.02, 0.28, "DBP", fontsize=28, color=DARK_MUTED,
                 rotation=90, va="center", fontweight="bold")

        if verdict in ("Missing", "Error"):
            for row in axes:
                for ax in row:
                    ax.axis("off")
            fig.text(
                0.5, 0.5,
                f"{'Missing data' if verdict == 'Missing' else 'Error processing'} for {display}",
                ha="center", va="center", fontsize=24, color=DARK_MUTED,
            )
            pdf.savefig(fig)
            plt.close(fig)
            continue

        # Get PMF maps for this lens
        lens_pmf = pmf_data.get(lens_type, {}) if pmf_data else {}

        for row_idx, (section_label, section_data, pmf_section) in enumerate([
            ("RTC", rtc_data, lens_pmf.get("RTC", {})),
            ("DBP", dbp_data, lens_pmf.get("DBP", {})),
        ]):
            # Column 0: DDF table
            draw_ddf_table(axes[row_idx, 0], section_data, section_label)

            # Column 1: Cylinder Error
            cyl_key = f"{section_label}_TCE"
            if cyl_key in pmf_section:
                visualize_powermap(
                    axes[row_idx, 1],
                    pmf_section[cyl_key],
                    title=f"{section_label} Cylinder Error",
                    v_max=0.3, v_min=-0.3,
                )
            else:
                axes[row_idx, 1].axis("off")
                axes[row_idx, 1].text(
                    0.5, 0.5, f"No {section_label}\nCylinder Error Map",
                    ha="center", va="center", fontsize=11, color=DARK_MUTED,
                    transform=axes[row_idx, 1].transAxes,
                )

            # Column 2: Diopter Error
            dpt_key = f"{section_label}_TDE"
            if dpt_key in pmf_section:
                visualize_powermap(
                    axes[row_idx, 2],
                    pmf_section[dpt_key],
                    title=f"{section_label} Diopter Error",
                    v_max=0.25, v_min=-0.25,
                )
            else:
                axes[row_idx, 2].axis("off")
                axes[row_idx, 2].text(
                    0.5, 0.5, f"No {section_label}\nDiopter Error Map",
                    ha="center", va="center", fontsize=11, color=DARK_MUTED,
                    transform=axes[row_idx, 2].transAxes,
                )

        fig.subplots_adjust(left=0.08, right=0.97, bottom=0.05, top=0.90,
                            hspace=0.35, wspace=0.3)
        pdf.savefig(fig)
        plt.close(fig)

    pdf.close()


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────
def run_batch(input_directory, output_directory):
    """Walk every lab/fast-tool folder and generate PDF reports."""
    if not os.path.exists(input_directory):
        print(f"Input directory not found: {input_directory}")
        return

    os.makedirs(output_directory, exist_ok=True)

    for lab_folder in sorted(os.listdir(input_directory)):
        lab_path = os.path.join(input_directory, lab_folder)
        if not os.path.isdir(lab_path):
            continue

        match = re.match(r"(\d+)\.([^.]+)\.(\d+)", lab_folder)
        if not match:
            print(f"Skipping (invalid folder name format): {lab_folder}")
            continue

        lab_number = match.group(1)
        lab_name = match.group(2)
        generator_sn = match.group(3)

        fast_tool_folders = sorted([
            f for f in os.listdir(lab_path)
            if os.path.isdir(os.path.join(lab_path, f))
        ])

        for fast_tool in fast_tool_folders:
            fast_tool_path = os.path.join(lab_path, fast_tool)
            print(f"Processing: {lab_folder} / {fast_tool}")

            try:
                lens_results, pmf_data = process_lab_folder(lab_path, fast_tool_path)

                output_file = os.path.join(
                    output_directory,
                    f"{lab_folder}_{fast_tool}_report.pdf",
                )
                generate_enhanced_pdf_report(
                    lens_results,
                    output_file,
                    f"{lab_number}. {lab_name}",
                    generator_sn,
                    fast_tool,
                    pmf_data,
                )
                print(f"  -> {output_file}")

            except Exception as e:
                print(f"  Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate lens quality PDF reports from DDF/PMF data."
    )
    parser.add_argument(
        "--input", default="input",
        help="Root directory containing lab folders (default: ./input)",
    )
    parser.add_argument(
        "--output", default="output",
        help="Directory for generated PDF reports (default: ./output)",
    )
    args = parser.parse_args()

    run_batch(args.input, args.output)


if __name__ == "__main__":
    main()
