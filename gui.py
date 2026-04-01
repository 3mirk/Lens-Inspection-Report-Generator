"""
gui.py

PyQt6 desktop interface for the GenAcc Report Tool.
Spotify-inspired dark theme with card-based layout.

    python gui.py
"""

import os
import re

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QHeaderView,
    QTreeWidgetItem,
    QTextEdit,
    QLabel,
    QFrame,
    QSplitter,
    QStyledItemDelegate,
    QGraphicsDropShadowEffect,
    QSizePolicy,
    QSpacerItem,
    QScrollArea,
)
from PyQt6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QSize,
    QTimer,
    QThread,
    QPoint,
    pyqtSignal,
    QRect,
)
from PyQt6.QtGui import QColor, QFont, QPen, QPalette

from lens_processing import (
    LENS_TYPES,
    LENS_DISPLAY_NAMES,
    parse_ddf_file,
    find_lens_file,
    process_lab_folder,
)
from report_generator import generate_enhanced_pdf_report


# ──────────────────────────────────────────────
# Design Tokens
# ──────────────────────────────────────────────
class Theme:
    """Spotify-inspired dark palette with warm accents."""

    # Backgrounds — layered depth
    BG_BASE = "#0a0a0a"
    BG_SURFACE = "#141414"
    BG_CARD = "#1a1a1a"
    BG_CARD_HOVER = "#212121"
    BG_ELEVATED = "#242424"
    BG_OVERLAY = "#2a2a2a"

    # Accent — Spotify green
    ACCENT = "#1DB954"
    ACCENT_HOVER = "#1ed760"
    ACCENT_MUTED = "#1a7a3a"

    # Semantic
    SUCCESS = "#1DB954"
    WARNING = "#F5A623"
    ERROR = "#E85D5D"
    INFO = "#4A9FD9"

    # Text
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B3B3B3"
    TEXT_TERTIARY = "#727272"
    TEXT_DISABLED = "#535353"

    # Borders
    BORDER_SUBTLE = "#282828"
    BORDER_DEFAULT = "#333333"
    BORDER_STRONG = "#444444"

    # Misc
    SCROLLBAR_THUMB = "#535353"
    SCROLLBAR_HOVER = "#727272"

    # Radius
    RADIUS_SM = "6px"
    RADIUS_MD = "10px"
    RADIUS_LG = "16px"
    RADIUS_PILL = "50px"


# ──────────────────────────────────────────────
# Global Stylesheet
# ──────────────────────────────────────────────
GLOBAL_STYLESHEET = f"""
    * {{
        font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
    }}

    QMainWindow {{
        background-color: {Theme.BG_BASE};
    }}

    QToolTip {{
        background-color: {Theme.BG_OVERLAY};
        color: {Theme.TEXT_PRIMARY};
        border: 1px solid {Theme.BORDER_DEFAULT};
        border-radius: {Theme.RADIUS_SM};
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* ── Scrollbar ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {Theme.SCROLLBAR_THUMB};
        border-radius: 4px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {Theme.SCROLLBAR_HOVER};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 2px 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {Theme.SCROLLBAR_THUMB};
        border-radius: 4px;
        min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {Theme.SCROLLBAR_HOVER};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: none;
        width: 0px;
    }}
"""


# ──────────────────────────────────────────────
# Helper: Card shadow
# ──────────────────────────────────────────────
def apply_shadow(widget, blur=20, offset_y=4, opacity=80):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset_y)
    shadow.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(shadow)


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
class SidebarButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.full_text = text
        self.short_text = text[:3] if len(text) > 3 else text
        self._expanded = False

        self.setFixedHeight(44)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.size_anim = QPropertyAnimation(self, b"minimumWidth")
        self.size_anim.setDuration(300)
        self.size_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._base_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-radius: 8px;
                padding: 0px 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_PRIMARY};
                font-weight: bold;
            }}
        """
        self.setStyleSheet(self._base_style)
        self.setText(self.short_text)
        self.setFixedWidth(44)

    def set_status_color(self, color_hex):
        """Apply a left accent bar to indicate status."""
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-left: 3px solid {color_hex};
                border-radius: 0px 8px 8px 0px;
                padding: 0px 12px 0px 9px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_PRIMARY};
                font-weight: bold;
            }}
        """)

    def collapse(self):
        if self._expanded:
            self._expanded = False
            self.setText(self.short_text)
            self.size_anim.setStartValue(self.width())
            self.size_anim.setEndValue(44)
            self.size_anim.start()

    def expand(self):
        if not self._expanded:
            self._expanded = True
            self.setText(self.full_text)
            width = self.fontMetrics().boundingRect(self.full_text).width() + 50
            target_width = max(180, width)
            self.size_anim.setStartValue(self.width())
            self.size_anim.setEndValue(target_width)
            self.size_anim.start()


class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self.animation = None
        self.buttons = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 12, 8, 16)
        self._layout.setSpacing(4)

        # Small "Labs" section label
        self.section_label = QLabel("Labs")
        self.section_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.section_label.setStyleSheet(f"""
            color: {Theme.TEXT_TERTIARY};
            padding: 4px 8px 2px 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        self._layout.addWidget(self.section_label)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {Theme.BORDER_SUBTLE};")
        self._layout.addWidget(divider)
        self._layout.addSpacing(6)

        self._button_spacer = None

        self.setFixedWidth(60)
        self.setStyleSheet(f"""
            Sidebar {{
                background-color: {Theme.BG_SURFACE};
                border-right: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)

        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self._do_collapse)

    def add_button(self, text, callback):
        button = SidebarButton(text)
        button.setCheckable(True)
        button.clicked.connect(callback)
        if self._button_spacer is None:
            self._layout.addWidget(button)
        else:
            idx = self._layout.indexOf(self._button_spacer)
            self._layout.insertWidget(idx, button)
        self.buttons.append(button)

        if self._button_spacer is None:
            self._button_spacer = QSpacerItem(
                0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
            self._layout.addSpacerItem(self._button_spacer)

        return button

    def expand(self):
        if not self._expanded:
            self._expanded = True
            self.animate_size(60, 220)
            for button in self.buttons:
                button.expand()

    def collapse(self):
        if self._expanded:
            self._expanded = False
            self.animate_size(220, 60)
            for button in self.buttons:
                button.collapse()

    def animate_size(self, start, end):
        if self.animation:
            self.animation.stop()
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.start()

    def enterEvent(self, event):
        self.collapse_timer.stop()
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.collapse_timer.start(300)
        super().leaveEvent(event)

    def _do_collapse(self):
        self.collapse()


# ──────────────────────────────────────────────
# Card Container
# ──────────────────────────────────────────────
class Card(QFrame):
    """A rounded card container with subtle shadow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            Card {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG};
            }}
        """)
        apply_shadow(self, blur=16, offset_y=2, opacity=50)


# ──────────────────────────────────────────────
# Fast Tool Card (individual FT card for side-by-side layout)
# ──────────────────────────────────────────────
class FastToolCard(QFrame):
    """Card for a single fast tool's lens status grid."""

    def __init__(self, ft_name, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            FastToolCard {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG};
            }}
        """)
        apply_shadow(self, blur=12, offset_y=2, opacity=40)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)

        # Card title
        title = QLabel(ft_name)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        self._layout.addWidget(title)

        # Column headers row
        header_row = QHBoxLayout()
        header_row.setSpacing(0)
        for col_text in ["Lens", "RTC", "DBP", "PMF"]:
            lbl = QLabel(col_text)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl.setStyleSheet(f"""
                color: {Theme.TEXT_TERTIARY};
                padding: 2px 0px;
            """)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if col_text == "Lens":
                lbl.setFixedWidth(90)
            else:
                lbl.setFixedWidth(56)
            header_row.addWidget(lbl)
        header_row.addStretch()
        self._layout.addLayout(header_row)

        # Divider under headers
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {Theme.BORDER_SUBTLE};")
        self._layout.addWidget(div)

        # Rows container
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(4)
        self._layout.addLayout(self.rows_layout)
        self._layout.addStretch()

        # Tracking counts
        self.missing_count = 0
        self.dbp_missing_count = 0
        self.pmf_missing_count = 0

    def add_lens_row(self, lens_display_name, rtc_ok, dbp_ok, pmf_ok):
        """Add a row for one lens type. True=pass, False=fail, None=error."""
        row = QHBoxLayout()
        row.setSpacing(0)

        # Lens name
        name_lbl = QLabel(lens_display_name)
        name_lbl.setFont(QFont("Segoe UI", 10))
        name_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; padding: 4px 0px;")
        name_lbl.setFixedWidth(90)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(name_lbl)

        # Status cells
        for ok_val in [rtc_ok, dbp_ok, pmf_ok]:
            cell = QLabel()
            cell.setFixedSize(56, 28)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

            if ok_val is True:
                cell.setText("\u2713")
                cell.setStyleSheet(f"""
                    QLabel {{
                        background-color: {Theme.SUCCESS};
                        color: white;
                        border-radius: 6px;
                    }}
                """)
            elif ok_val is False:
                cell.setText("\u2014")
                cell.setStyleSheet(f"""
                    QLabel {{
                        background-color: {Theme.ERROR};
                        color: white;
                        border-radius: 6px;
                    }}
                """)
            else:  # None = error
                cell.setText("Err")
                cell.setStyleSheet(f"""
                    QLabel {{
                        background-color: {Theme.WARNING};
                        color: black;
                        border-radius: 6px;
                    }}
                """)
            row.addWidget(cell)

        row.addStretch()
        self.rows_layout.addLayout(row)


# ──────────────────────────────────────────────
# PDF Generator Thread
# ──────────────────────────────────────────────
class PDFGeneratorThread(QThread):
    progress = pyqtSignal(str)       # log message
    count_update = pyqtSignal(int, int, int)  # (completed, failed, total)
    finished = pyqtSignal(int, int)  # (success_count, fail_count)

    def __init__(self, input_directory, selected_pdfs):
        super().__init__()
        self.input_directory = input_directory
        self.selected_pdfs = selected_pdfs

    def run(self):
        total = len(self.selected_pdfs)
        success_count = 0
        fail_count = 0

        for lab_folder, fast_tool in self.selected_pdfs:
            lab_path = os.path.join(self.input_directory, lab_folder)
            try:
                match = re.match(r"(\d+)\.([^.]+)\.(\d+)", lab_folder)
                if not match:
                    fail_count += 1
                    self.progress.emit(
                        f"  Skipped (bad folder name): {lab_folder}"
                    )
                    self.count_update.emit(success_count, fail_count, total)
                    continue

                lab_number = match.group(1)
                lab_name = match.group(2)
                generator_sn = match.group(3)

                fast_tool_path = os.path.join(lab_path, fast_tool)
                self.progress.emit(f"Processing: {lab_folder} — {fast_tool}")

                results, pmf_data = process_lab_folder(lab_path, fast_tool_path)

                output_dir = "output"
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(
                    output_dir, f"{lab_folder}_{fast_tool}_report.pdf"
                )
                generate_enhanced_pdf_report(
                    results,
                    output_file,
                    f"{lab_number}. {lab_name}",
                    generator_sn,
                    fast_tool,
                    pmf_data,
                )

                success_count += 1
                self.progress.emit(f"  Saved: {output_file}")
                self.count_update.emit(success_count, fail_count, total)

            except Exception as e:
                fail_count += 1
                self.progress.emit(f"  Error: {lab_folder} — {str(e)}")
                self.count_update.emit(success_count, fail_count, total)

        self.finished.emit(success_count, fail_count)


# ──────────────────────────────────────────────
# Lab Tab — now uses side-by-side FT cards
# ──────────────────────────────────────────────
class LabTab(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable area for the FT cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.cards_layout = QHBoxLayout(self.scroll_content)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(16)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.scroll_content)
        outer.addWidget(scroll)

        self.ft_cards = []


# ──────────────────────────────────────────────
# Main Window
# ──────────────────────────────────────────────
class ModernLensQualityGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GenAcc Report Tool")
        self.setGeometry(100, 100, 1280, 820)
        self.setStyleSheet(GLOBAL_STYLESHEET)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Content area
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(f"background-color: {Theme.BG_BASE};")
        content_outer = QVBoxLayout(content_wrapper)
        content_outer.setContentsMargins(24, 20, 24, 20)
        content_outer.setSpacing(0)

        # ── Header bar ──
        header_bar = QWidget()
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(0, 0, 0, 16)

        title_label = QLabel("GenAcc Report Tool")
        title_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        subtitle = QLabel("Generator Acceptance  ·  Internal Reports")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setStyleSheet(f"color: {Theme.TEXT_TERTIARY};")
        header_layout.addWidget(subtitle)

        content_outer.addWidget(header_bar)

        # ── Splitter: main content | right panel ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Theme.BORDER_SUBTLE};
                margin: 40px 12px;
            }}
        """)

        # Left: lab tabs area
        left_wrapper = QWidget()
        left_wrapper.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_wrapper)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(12)

        # Lab name label (updates when tab switches)
        self.lab_title = QLabel("")
        self.lab_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lab_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; padding: 0 4px;")
        left_layout.addWidget(self.lab_title)

        # Sub-label
        self.lab_subtitle = QLabel("File presence by fast tool")
        self.lab_subtitle.setFont(QFont("Segoe UI", 11))
        self.lab_subtitle.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; padding: 0 4px 4px 4px;")
        left_layout.addWidget(self.lab_subtitle)

        # Tab content container
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        left_layout.addWidget(self.content_widget, 1)

        splitter.addWidget(left_wrapper)

        # Right: PDF generation panel
        right_panel = QWidget()
        right_panel.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 0, 0, 0)
        self.setup_right_panel(right_panel, right_layout)
        splitter.addWidget(right_panel)

        splitter.setSizes([720, 360])
        content_outer.addWidget(splitter)

        # ── Status bar ──
        self.status_bar = QLabel("Ready")
        self.status_bar.setFont(QFont("Segoe UI", 10))
        self.status_bar.setStyleSheet(f"""
            color: {Theme.TEXT_TERTIARY};
            padding: 8px 0px 0px 0px;
        """)
        content_outer.addWidget(self.status_bar)

        main_layout.addWidget(content_wrapper)

        self.tabs = {}
        self.current_tab = None
        self.load_folder_structure()

    def load_folder_structure(self):
        input_directory = "input"
        if not os.path.exists(input_directory):
            self.status_bar.setText(
                'No "input" folder found. Place lab folders in ./input/'
            )
            return

        lab_count = 0
        for lab_folder in sorted(os.listdir(input_directory)):
            lab_path = os.path.join(input_directory, lab_folder)
            if os.path.isdir(lab_path):
                tab = LabTab(lab_folder)
                self.tabs[lab_folder] = tab

                button = self.sidebar.add_button(
                    lab_folder,
                    lambda checked, lf=lab_folder: self.show_tab(lf),
                )
                self.populate_lab_cards(tab, lab_path, button)

                tab.hide()
                self.content_layout.addWidget(tab)
                lab_count += 1

        self.content_layout.addStretch()

        if self.tabs:
            first_lab = next(iter(self.tabs))
            self.show_tab(first_lab)
            self.status_bar.setText(
                f"Loaded {lab_count} lab(s) from ./input/"
            )

        self.populate_pdf_list()

    def populate_lab_cards(self, tab, lab_path, button):
        """Build side-by-side FastToolCards instead of a tree widget."""
        fast_tool_folders = sorted([
            f for f in os.listdir(lab_path)
            if os.path.isdir(os.path.join(lab_path, f))
        ])

        total_missing_count = 0
        total_dbp_missing_count = 0
        total_pmf_missing_count = 0

        for fast_tool in fast_tool_folders:
            card = FastToolCard(fast_tool)
            fast_tool_path = os.path.join(lab_path, fast_tool)

            ft_missing = 0
            ft_dbp_missing = 0
            ft_pmf_missing = 0

            for lens_type in LENS_TYPES:
                ddf_file = find_lens_file(fast_tool_path, lens_type, ".ddf")

                rtc_ok = False
                dbp_ok = False
                pmf_ok = False
                is_error = False

                if ddf_file:
                    try:
                        rtc_data, dbp_data = parse_ddf_file(ddf_file)

                        if rtc_data:
                            rtc_ok = True
                        else:
                            ft_missing += 1

                        if dbp_data:
                            dbp_ok = True
                        else:
                            ft_dbp_missing += 1

                    except Exception:
                        is_error = True
                        ft_missing += 1
                else:
                    ft_missing += 1

                pmf_file = find_lens_file(fast_tool_path, lens_type, ".pmf")
                if pmf_file:
                    pmf_ok = True
                else:
                    ft_pmf_missing += 1

                if is_error:
                    card.add_lens_row(LENS_DISPLAY_NAMES[lens_type], None, None, None)
                else:
                    card.add_lens_row(
                        LENS_DISPLAY_NAMES[lens_type], rtc_ok, dbp_ok, pmf_ok
                    )

            card.missing_count = ft_missing
            card.dbp_missing_count = ft_dbp_missing
            card.pmf_missing_count = ft_pmf_missing

            total_missing_count += ft_missing
            total_dbp_missing_count += ft_dbp_missing
            total_pmf_missing_count += ft_pmf_missing

            tab.cards_layout.addWidget(card)
            tab.ft_cards.append(card)

        # Sidebar button status accent
        if total_missing_count > 1:
            button.set_status_color(Theme.ERROR)
        elif (
            total_missing_count > 0
            or total_dbp_missing_count > 0
            or total_pmf_missing_count > 0
        ):
            button.set_status_color(Theme.WARNING)
        else:
            button.set_status_color(Theme.SUCCESS)

    def show_tab(self, lab_folder):
        if self.current_tab:
            self.tabs[self.current_tab].hide()
            idx = list(self.tabs.keys()).index(self.current_tab)
            self.sidebar.buttons[idx].setChecked(False)

        self.current_tab = lab_folder
        tab = self.tabs[lab_folder]
        tab.show()
        idx = list(self.tabs.keys()).index(lab_folder)
        self.sidebar.buttons[idx].setChecked(True)

        # Update header
        self.lab_title.setText(lab_folder)

    def setup_right_panel(self, right_panel, right_layout):
        # Section header
        pdf_header = QLabel("Report Generation")
        pdf_header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        pdf_header.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            padding-bottom: 8px;
        """)
        right_layout.addWidget(pdf_header)

        # PDF list card
        pdf_card = Card()
        pdf_card_layout = QVBoxLayout(pdf_card)
        pdf_card_layout.setContentsMargins(12, 12, 12, 12)

        self.pdf_list = QTreeWidget()
        self.pdf_list.setHeaderHidden(False)
        self.pdf_list.setHeaderLabels(["Select reports to generate"])
        self.pdf_list.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.pdf_list.setAnimated(True)
        self.pdf_list.setStyleSheet(f"""
            QTreeWidget {{
                background: transparent;
                color: {Theme.TEXT_PRIMARY};
                border: none;
                font-size: 12px;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 5px 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: {Theme.BG_CARD_HOVER};
                border-radius: 4px;
            }}
            QTreeWidget::indicator {{
                width: 16px;
                height: 16px;
            }}
            QTreeWidget::indicator:unchecked {{
                border: 2px solid {Theme.TEXT_TERTIARY};
                border-radius: 3px;
                background: transparent;
            }}
            QTreeWidget::indicator:checked {{
                border: 2px solid {Theme.ACCENT};
                border-radius: 3px;
                background-color: {Theme.ACCENT};
            }}
            QHeaderView::section {{
                background-color: transparent;
                color: {Theme.TEXT_TERTIARY};
                border: none;
                border-bottom: 1px solid {Theme.BORDER_SUBTLE};
                padding: 6px 4px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
        pdf_card_layout.addWidget(self.pdf_list)

        # Select / Deselect buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self.select_all_pdfs)
        select_all_button.setStyleSheet(self._ghost_button_style())
        select_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(select_all_button)

        deselect_all_button = QPushButton("Deselect All")
        deselect_all_button.clicked.connect(self.deselect_all_pdfs)
        deselect_all_button.setStyleSheet(self._ghost_button_style())
        deselect_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(deselect_all_button)

        pdf_card_layout.addLayout(btn_row)
        right_layout.addWidget(pdf_card)

        right_layout.addSpacing(12)

        # Log / output area
        log_label = QLabel("Output Log")
        log_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        log_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; padding-bottom: 4px;")
        right_layout.addWidget(log_label)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("Consolas", 10))
        self.text_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_SECONDARY};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_MD};
                padding: 10px;
                min-height: 80px;
            }}
        """)
        right_layout.addWidget(self.text_area)

        right_layout.addSpacing(12)

        # Generate button — primary action
        self.generate_button = QPushButton("Generate PDF Reports")
        self.generate_button.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.generate_button.setFixedHeight(48)
        self.generate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: {Theme.BG_BASE};
                border: none;
                border-radius: {Theme.RADIUS_PILL};
                padding: 0px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT_MUTED};
            }}
            QPushButton:disabled {{
                background-color: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_DISABLED};
            }}
        """)
        self.generate_button.clicked.connect(self.generate_reports)
        right_layout.addWidget(self.generate_button)

    def _ghost_button_style(self):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: 1px solid {Theme.BORDER_DEFAULT};
                border-radius: {Theme.RADIUS_PILL};
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border-color: {Theme.BORDER_STRONG};
            }}
            QPushButton:pressed {{
                background-color: {Theme.BG_ELEVATED};
            }}
        """

    def populate_pdf_list(self):
        self.pdf_list.clear()
        input_directory = "input"
        if not os.path.exists(input_directory):
            return

        for lab_folder in sorted(os.listdir(input_directory)):
            lab_path = os.path.join(input_directory, lab_folder)
            if os.path.isdir(lab_path):
                lab_item = QTreeWidgetItem(self.pdf_list)
                lab_item.setText(0, lab_folder)
                lab_item.setFont(0, QFont("Segoe UI", 11, QFont.Weight.Medium))
                lab_item.setFlags(
                    lab_item.flags()
                    | Qt.ItemFlag.ItemIsAutoTristate
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                lab_item.setCheckState(0, Qt.CheckState.Checked)

                fast_tool_folders = sorted([
                    f for f in os.listdir(lab_path)
                    if os.path.isdir(os.path.join(lab_path, f))
                ])
                for fast_tool in fast_tool_folders:
                    ft_item = QTreeWidgetItem(lab_item)
                    ft_item.setText(0, fast_tool)
                    ft_item.setFlags(
                        ft_item.flags() | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    ft_item.setCheckState(0, Qt.CheckState.Checked)

    def select_all_pdfs(self):
        for i in range(self.pdf_list.topLevelItemCount()):
            item = self.pdf_list.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)

    def deselect_all_pdfs(self):
        for i in range(self.pdf_list.topLevelItemCount()):
            item = self.pdf_list.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)

    def get_selected_pdfs(self):
        selected = []
        for i in range(self.pdf_list.topLevelItemCount()):
            lab_item = self.pdf_list.topLevelItem(i)
            lab_folder = lab_item.text(0)
            for j in range(lab_item.childCount()):
                ft_item = lab_item.child(j)
                if ft_item.checkState(0) == Qt.CheckState.Checked:
                    fast_tool = ft_item.text(0)
                    selected.append((lab_folder, fast_tool))
        return selected

    def generate_reports(self):
        self.text_area.clear()
        self.generate_button.setEnabled(False)
        self.generate_button.setText("Generating...")

        selected_pdfs = self.get_selected_pdfs()
        if not selected_pdfs:
            self.text_area.append("No reports selected.")
            self.generate_button.setEnabled(True)
            self.generate_button.setText("Generate PDF Reports")
            return

        self._pdf_total = len(selected_pdfs)
        self.status_bar.setText(f"0/{self._pdf_total} PDFs generated...")

        self.pdf_thread = PDFGeneratorThread("input", selected_pdfs)
        self.pdf_thread.progress.connect(self.text_area.append)
        self.pdf_thread.count_update.connect(self._on_count_update)
        self.pdf_thread.finished.connect(self._on_generation_complete)
        self.pdf_thread.start()

    def _on_count_update(self, success, failed, total):
        done = success + failed
        self.status_bar.setText(f"{done}/{total} PDFs generated...")
        self.generate_button.setText(f"Generating... ({done}/{total})")

    def _on_generation_complete(self, success, failed):
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate PDF Reports")

        total = success + failed
        if failed == 0:
            self.status_bar.setText(
                f"{success}/{total} PDFs generated. Completed."
            )
            self.text_area.append(
                f"\n{success}/{total} PDFs generated. Completed."
            )
        else:
            self.status_bar.setText(
                f"{success}/{total} PDFs generated. {failed} failed."
            )
            self.text_area.append(
                f"\n{success}/{total} PDFs generated. {failed} failed."
            )


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
def main():
    app = QApplication([])

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Theme.BG_BASE))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Theme.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Theme.BG_CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(Theme.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Theme.BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Theme.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Theme.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Theme.BG_BASE))
    app.setPalette(palette)

    window = ModernLensQualityGUI()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
