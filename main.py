"""
GT Title Animation Editor
Bulk-edit GT Title Editor animation storyboards.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QCheckBox,
    QScrollArea, QFileDialog, QMessageBox, QFrame, QSizePolicy,
    QLineEdit, QStatusBar, QToolBar, QTabWidget, QButtonGroup,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

from gtzip_handler import (
    GTFileHandler, GTElement, AnimationEntry,
    ANIMATION_TYPES, EASING_TYPES, DIRECTIONS,
)
import vmix_client


# ─── Colour palette ───────────────────────────────────────────────────────────
DARK_BG      = "#1e1e2e"
CARD_BG      = "#2a2a3e"
CARD_DIRTY   = "#2d2a18"
HEADER_BG    = "#313150"
ACCENT       = "#7c6af7"
ACCENT_HOVER = "#9580ff"
TEXT_PRIMARY = "#cdd6f4"
TEXT_DIM     = "#6c7086"
TEXT_TI      = "#a6e3a1"
TEXT_TO      = "#f38ba8"
TEXT_DCI     = "#89b4fa"
TEXT_DCO     = "#fab387"
BORDER       = "#45475a"
BORDER_DIRTY = "#f9e2af"

STORYBOARD_COLORS = {
    "TransitionIn":  TEXT_TI,
    "TransitionOut": TEXT_TO,
    "DataChangeIn":  TEXT_DCI,
    "DataChangeOut": TEXT_DCO,
}
STORYBOARD_LABELS = {
    "TransitionIn":  "Transition In",
    "TransitionOut": "Transition Out",
    "DataChangeIn":  "Data Change In",
    "DataChangeOut": "Data Change Out",
}
STORYBOARD_SHORT = {
    "TransitionIn": "TI", "TransitionOut": "TO",
    "DataChangeIn": "DCI", "DataChangeOut": "DCO",
}

# Filter button labels (order determines display order)
TYPE_FILTER_LABELS = ["All", "Text", "Image", "Color", "Layer"]

# Colour and short label shown in each element card's header badge.
# Anything not listed falls back to ("Color", TEXT_DCO).
BADGE_INFO: dict[str, tuple[str, str]] = {
    "TextBlock":     (TEXT_TI,  "Text"),
    "Text3D":        (TEXT_TI,  "Text3D"),
    "Image":         (TEXT_DCI, "Image"),
    "Layer":         (TEXT_TO,  "Layer"),
}


def element_category(element_type: str) -> str:
    """Map a raw element_type tag to one of the filter categories."""
    if element_type in ("TextBlock", "Text3D"):
        return "Text"
    if element_type == "Image":
        return "Image"
    if element_type == "Layer":
        return "Layer"
    return "Color"   # Rectangle, Ellipse, RightTriangle, Triangle, …

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}}
QScrollArea {{ border: none; background-color: {DARK_BG}; }}
QScrollBar:vertical {{
    background: {CARD_BG}; width: 10px; border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {ACCENT}; border-radius: 5px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {CARD_BG}; height: 10px; border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: {ACCENT}; border-radius: 5px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QComboBox {{
    background-color: {HEADER_BG}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 3px 8px; color: {TEXT_PRIMARY}; min-width: 90px;
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{
    background-color: {HEADER_BG}; border: 1px solid {ACCENT};
    color: {TEXT_PRIMARY}; selection-background-color: {ACCENT};
}}
QSpinBox {{
    background-color: {HEADER_BG}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 3px 6px; color: {TEXT_PRIMARY};
}}
QSpinBox:hover {{ border-color: {ACCENT}; }}
QCheckBox {{ color: {TEXT_PRIMARY}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid {BORDER};
    border-radius: 3px; background: {HEADER_BG};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QPushButton {{
    background-color: {ACCENT}; color: white; border: none;
    border-radius: 5px; padding: 6px 16px; font-weight: bold;
}}
QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton:disabled {{ background-color: {TEXT_DIM}; color: {BORDER}; }}
QPushButton#secondary {{
    background-color: {HEADER_BG}; border: 1px solid {BORDER}; color: {TEXT_PRIMARY};
}}
QPushButton#secondary:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#toggle {{
    background-color: transparent; border: 1px solid {BORDER};
    color: {TEXT_DIM}; border-radius: 4px;
    padding: 0px; font-size: 11px; font-weight: bold;
}}
QPushButton#toggle:hover {{ border-color: {ACCENT}; color: {TEXT_PRIMARY}; }}
QPushButton#filterBtn {{
    background-color: {HEADER_BG}; border: 1px solid {BORDER};
    color: {TEXT_DIM}; border-radius: 4px;
    padding: 3px 10px; font-size: 12px; font-weight: normal;
}}
QPushButton#filterBtn:hover {{ border-color: {ACCENT}; color: {TEXT_PRIMARY}; }}
QPushButton#filterBtn:checked {{
    background-color: {ACCENT}; border-color: {ACCENT};
    color: white; font-weight: bold;
}}
QFrame#bulkCard {{
    background-color: #1e1a36;
    border: 2px solid {ACCENT};
    border-radius: 6px;
}}
QFrame#bulkHeader {{
    background-color: #27204a;
    border-radius: 4px 4px 0 0;
}}
QPushButton#applyAll {{
    background-color: {ACCENT}; color: white;
    border: none; border-radius: 4px;
    padding: 5px 14px; font-weight: bold;
}}
QPushButton#applyAll:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton#applyAll:disabled {{ background-color: {TEXT_DIM}; color: {BORDER}; }}
QLineEdit {{
    background-color: {HEADER_BG}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 4px 8px; color: {TEXT_PRIMARY};
}}
QFrame#separator {{
    background-color: {BORDER}; max-height: 1px;
}}
QFrame#cardFrame {{
    background-color: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 6px;
}}
QFrame#cardFrame[dirty="true"] {{
    background-color: {CARD_DIRTY}; border: 2px solid {BORDER_DIRTY};
}}
QFrame#cardHeader {{
    background-color: {HEADER_BG}; border-radius: 5px 5px 0 0;
}}
QFrame#cardHeader[dirty="true"] {{
    background-color: #3a3518;
}}
QFrame#cardFrame[selected="true"] {{
    border: 2px solid {ACCENT};
}}
QFrame#cardFrame[dirty="true"][selected="true"] {{
    background-color: {CARD_DIRTY}; border: 2px solid {ACCENT};
}}
QFrame#cardHeader[selected="true"] {{
    background-color: #272040;
}}
QFrame#cardHeader[dirty="true"][selected="true"] {{
    background-color: #38302a;
}}
QStatusBar {{
    background-color: {HEADER_BG}; color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QToolBar {{
    background-color: {HEADER_BG}; border-bottom: 1px solid {BORDER};
    spacing: 8px; padding: 4px 8px;
}}
QTabWidget::pane {{
    border: none; background: {DARK_BG};
}}
QTabBar::tab {{
    background: {CARD_BG}; color: {TEXT_DIM};
    padding: 6px 18px 6px 12px; border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px; font-size: 12px;
}}
QTabBar::tab:selected {{
    background: {HEADER_BG}; color: {TEXT_PRIMARY};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{ color: {TEXT_PRIMARY}; }}
QTabBar::close-button {{
    subcontrol-position: right;
}}
"""


# ─── Tab data ─────────────────────────────────────────────────────────────────
@dataclass
class TabData:
    filepath: str
    handler: GTFileHandler
    elements: list
    cards: list
    dirty_elements: set = field(default_factory=set)


# ─── vMix poller ──────────────────────────────────────────────────────────────
class VMixPoller(QThread):
    titles_updated = pyqtSignal(list)
    connection_changed = pyqtSignal(bool)

    def __init__(self, host="localhost", port=8088):
        super().__init__()
        self.host, self.port = host, port
        self._running = True
        self._last_connected = None

    def run(self):
        while self._running:
            try:
                titles = vmix_client.fetch_titles(self.host, self.port)
                connected = True
                self.titles_updated.emit(titles)
            except Exception:
                connected = False
                self.titles_updated.emit([])
            if connected != self._last_connected:
                self._last_connected = connected
                self.connection_changed.emit(connected)
            self.msleep(3000)

    def stop(self):
        self._running = False
        self.quit()


# ─── Storyboard row ───────────────────────────────────────────────────────────
class StoryboardRow(QWidget):
    """Controls for a single storyboard slot (TransitionIn, etc.)."""
    changed = pyqtSignal()

    def __init__(self, sb_type: str, data_name: str, parent=None):
        super().__init__(parent)
        self.sb_type   = sb_type
        self.data_name = data_name
        self._loading  = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(6)

        color = STORYBOARD_COLORS[self.sb_type]
        lbl   = QLabel(STORYBOARD_LABELS[self.sb_type])
        lbl.setFixedWidth(118)
        lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
        layout.addWidget(lbl)

        # DataName hint — always a real widget of the same width so that
        # Qt's inter-item spacing is applied identically in every row and
        # the Animation column stays perfectly vertical.
        is_dc = self.sb_type in ("DataChangeIn", "DataChangeOut")
        self._dn_lbl = QLabel(f"({self.data_name})" if is_dc else "")
        self._dn_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        self._dn_lbl.setFixedWidth(158)
        layout.addWidget(self._dn_lbl)

        # Animation type
        self.anim_combo = QComboBox()
        self.anim_combo.addItems(ANIMATION_TYPES)
        self.anim_combo.setFixedWidth(106)
        layout.addWidget(self.anim_combo)

        # Delay (label is in the column header above)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 30000)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setFixedWidth(90)
        layout.addWidget(self.delay_spin)

        # Duration (stored in seconds in XML, displayed/edited in ms)
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(0, 60000)
        self.dur_spin.setSuffix(" ms")
        self.dur_spin.setSpecialValueText("default")
        self.dur_spin.setFixedWidth(90)
        layout.addWidget(self.dur_spin)

        # Easing
        self.easing_combo = QComboBox()
        self.easing_combo.addItems(EASING_TYPES)
        self.easing_combo.setFixedWidth(158)
        layout.addWidget(self.easing_combo)

        # Direction
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["(none)" if d == "" else d for d in DIRECTIONS])
        self.dir_combo.setFixedWidth(106)
        layout.addWidget(self.dir_combo)

        # Reverse
        self.reverse_check = QCheckBox("Rev")
        self.reverse_check.setFixedWidth(52)
        layout.addWidget(self.reverse_check)
        layout.addStretch()

        # Wire enable/disable and change signals
        self.anim_combo.currentTextChanged.connect(self._on_type_changed)
        self.anim_combo.currentIndexChanged.connect(self._emit_changed)
        self.delay_spin.valueChanged.connect(self._emit_changed)
        self.dur_spin.valueChanged.connect(self._emit_changed)
        self.easing_combo.currentIndexChanged.connect(self._emit_changed)
        self.dir_combo.currentIndexChanged.connect(self._emit_changed)
        self.reverse_check.stateChanged.connect(self._emit_changed)

        self._on_type_changed(self.anim_combo.currentText())

    @staticmethod
    def _dim(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        return lbl

    def _on_type_changed(self, anim_type: str):
        enabled = anim_type != "None"
        for w in (self.delay_spin, self.dur_spin, self.easing_combo,
                  self.dir_combo, self.reverse_check):
            w.setEnabled(enabled)

    def update_data_label(self, text: str):
        """Update the DataName hint label (used by BulkEditCard)."""
        self._dn_lbl.setText(text)

    def _emit_changed(self):
        if not self._loading:
            self.changed.emit()

    def load_entry(self, entry: AnimationEntry):
        self._loading = True
        idx = self.anim_combo.findText(entry.anim_type)
        self.anim_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.delay_spin.setValue(entry.delay)
        # GT stores Duration in seconds; we display in ms
        self.dur_spin.setValue(int(round(entry.duration * 1000)))
        ei = self.easing_combo.findText(entry.interpolation)
        self.easing_combo.setCurrentIndex(ei if ei >= 0 else 0)
        dd = "(none)" if entry.direction == "" else entry.direction
        di = self.dir_combo.findText(dd)
        self.dir_combo.setCurrentIndex(di if di >= 0 else 0)
        self.reverse_check.setChecked(entry.reverse)
        self._loading = False

    def get_entry(self) -> AnimationEntry:
        dd = self.dir_combo.currentText()
        return AnimationEntry(
            anim_type=self.anim_combo.currentText(),
            delay=self.delay_spin.value(),
            duration=self.dur_spin.value() / 1000.0,  # ms → seconds for XML
            interpolation=self.easing_combo.currentText(),
            direction="" if dd == "(none)" else dd,
            reverse=self.reverse_check.isChecked(),
        )

    def apply_entry(self, entry: AnimationEntry):
        """
        Set widget values from entry AND emit changed (for programmatic bulk apply).
        Unlike load_entry, this marks the owning card dirty.
        """
        self._loading = True
        idx = self.anim_combo.findText(entry.anim_type)
        self.anim_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.delay_spin.setValue(entry.delay)
        self.dur_spin.setValue(int(round(entry.duration * 1000)))
        ei = self.easing_combo.findText(entry.interpolation)
        self.easing_combo.setCurrentIndex(ei if ei >= 0 else 0)
        dd = "(none)" if entry.direction == "" else entry.direction
        di = self.dir_combo.findText(dd)
        self.dir_combo.setCurrentIndex(di if di >= 0 else 0)
        self.reverse_check.setChecked(entry.reverse)
        self._loading = False
        self.changed.emit()   # intentionally triggers dirty propagation

    def summary(self) -> str:
        atype = self.anim_combo.currentText()
        return atype if atype != "None" else "—"


# ─── Element card ─────────────────────────────────────────────────────────────
class ElementCard(QFrame):
    """Collapsible card with 4 storyboard rows for one element."""
    changed = pyqtSignal(str)           # emits element name
    selection_changed = pyqtSignal(str, bool)  # name, is_selected

    def __init__(self, element: GTElement, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.element_name = element.name
        self.element_type = element.element_type
        self._rows: dict[str, StoryboardRow] = {}
        self._collapsed  = False
        self._is_dirty   = False
        self._selected   = False
        self._build_ui(element)

    def _build_ui(self, element: GTElement):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        self._header = QFrame()
        self._header.setObjectName("cardHeader")
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(8, 5, 8, 5)
        hl.setSpacing(8)

        self._select_check = QCheckBox()
        self._select_check.setFixedSize(18, 18)
        self._select_check.setToolTip("Select for bulk editing")
        self._select_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_check.stateChanged.connect(self._on_select_changed)
        hl.addWidget(self._select_check)

        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setObjectName("toggle")
        self._toggle_btn.setFixedSize(22, 22)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        hl.addWidget(self._toggle_btn)

        name_lbl = QLabel(element.name)
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        name_lbl.setFont(f)
        hl.addWidget(name_lbl)

        cat = element_category(element.element_type)
        default_color = {
            "Text": TEXT_TI, "Image": TEXT_DCI,
            "Color": TEXT_DCO, "Layer": TEXT_TO,
        }.get(cat, TEXT_DIM)
        badge_color, badge_text = BADGE_INFO.get(
            element.element_type, (default_color, cat)
        )
        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"color:{badge_color}; background:{DARK_BG};"
            f"border-radius:3px; padding:1px 6px; font-size:11px;"
        )
        badge.setFixedSize(56, 18)
        hl.addWidget(badge)

        # Summary shown only when collapsed
        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        self._summary_lbl.hide()
        hl.addWidget(self._summary_lbl)

        hl.addStretch()
        outer.addWidget(self._header)

        # ── Rows container ───────────────────────────────────────────────────
        self._body = QWidget()
        bl = QVBoxLayout(self._body)
        bl.setContentsMargins(8, 4, 8, 8)
        bl.setSpacing(2)

        # Column header row
        ch = QHBoxLayout()
        ch.setContentsMargins(4, 0, 0, 0)  # match the 4 px left margin inside StoryboardRow
        ch.setSpacing(6)
        for txt, w in [
            ("Storyboard / DataName", 282), ("Animation", 106), ("Delay", 90),
            ("Duration", 90), ("Easing", 158), ("Direction", 106), ("Rev", 52),
        ]:
            cl = QLabel(txt)
            cl.setFixedWidth(w)
            cl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
            ch.addWidget(cl)
        ch.addStretch()
        bl.addLayout(ch)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        bl.addWidget(sep)

        # Storyboard rows — connect AFTER load_entry to avoid false dirty
        data_name = element.data_name
        for slot, entry in [
            ("TransitionIn",  element.transition_in),
            ("TransitionOut", element.transition_out),
            ("DataChangeIn",  element.data_change_in),
            ("DataChangeOut", element.data_change_out),
        ]:
            row = StoryboardRow(slot, data_name)
            row.load_entry(entry)
            row.changed.connect(self._on_row_changed)
            bl.addWidget(row)
            self._rows[slot] = row

            if slot != "DataChangeOut":
                s2 = QFrame()
                s2.setObjectName("separator")
                s2.setFrameShape(QFrame.Shape.HLine)
                bl.addWidget(s2)

        outer.addWidget(self._body)

    # ── Collapse ───────────────────────────────────────────────────────────────
    def _toggle_collapse(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._body.setVisible(not collapsed)
        self._toggle_btn.setText("▶" if collapsed else "▼")
        self._summary_lbl.setVisible(collapsed)
        if collapsed:
            self._refresh_summary()

    def _refresh_summary(self):
        parts = [
            f"{STORYBOARD_SHORT[s]}:{self._rows[s].summary()}"
            for s in ("TransitionIn", "TransitionOut", "DataChangeIn", "DataChangeOut")
        ]
        self._summary_lbl.setText("   ".join(parts))

    # ── Dirty tracking ────────────────────────────────────────────────────────
    def _on_row_changed(self):
        if not self._is_dirty:
            self._is_dirty = True
        self._update_style()
        if self._collapsed:
            self._refresh_summary()
        self.changed.emit(self.element_name)

    def _update_style(self):
        sel = "true" if self._selected else "false"
        drt = "true" if self._is_dirty else "false"
        self.setProperty("dirty", drt)
        self.setProperty("selected", sel)
        self._header.setProperty("dirty", drt)
        self._header.setProperty("selected", sel)
        for w in (self, self._header):
            w.style().unpolish(w)
            w.style().polish(w)

    def mark_clean(self):
        self._is_dirty = False
        self._update_style()

    # ── Selection ─────────────────────────────────────────────────────────────
    def _on_select_changed(self, state: int):
        self._selected = self._select_check.isChecked()
        self._update_style()
        self.selection_changed.emit(self.element_name, self._selected)

    @property
    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool):
        self._select_check.blockSignals(True)
        self._select_check.setChecked(selected)
        self._select_check.blockSignals(False)
        self._selected = selected
        self._update_style()
        self.selection_changed.emit(self.element_name, selected)

    # ── Data ──────────────────────────────────────────────────────────────────
    def apply_data_changes(self, dci: AnimationEntry, dco: AnimationEntry):
        """Bulk-apply DataChangeIn and DataChangeOut from the pseudo card."""
        self._rows["DataChangeIn"].apply_entry(dci)
        self._rows["DataChangeOut"].apply_entry(dco)

    def apply_all_animations(self, ti: AnimationEntry, to_: AnimationEntry,
                              dci: AnimationEntry, dco: AnimationEntry):
        """Bulk-apply all four storyboard rows from the BulkEditCard."""
        self._rows["TransitionIn"].apply_entry(ti)
        self._rows["TransitionOut"].apply_entry(to_)
        self._rows["DataChangeIn"].apply_entry(dci)
        self._rows["DataChangeOut"].apply_entry(dco)

    def get_element(self) -> GTElement:
        el = GTElement(name=self.element_name, element_type=self.element_type)
        el.transition_in   = self._rows["TransitionIn"].get_entry()
        el.transition_out  = self._rows["TransitionOut"].get_entry()
        el.data_change_in  = self._rows["DataChangeIn"].get_entry()
        el.data_change_out = self._rows["DataChangeOut"].get_entry()
        return el


# ─── Bulk-edit pseudo card ────────────────────────────────────────────────────
# Maps a filter category to the DataName suffix used by elements in that group.
_BULK_DC_SUFFIX: dict[str, str] = {
    "Text":  ".Text",
    "Image": ".Source",
    "Color": ".Color",
    "Layer": "",   # Layers have no data-property suffix; DataName will be omitted
}


class BulkEditCard(QFrame):
    """
    A pseudo-element that appears at the top of the element list.
    Lets the user configure DataChangeIn / DataChangeOut once and
    push those values to every selected element card with one click.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bulkCard")
        self._selected_cards: list[ElementCard] = []
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setObjectName("bulkHeader")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(10, 7, 10, 7)
        hl.setSpacing(8)

        icon = QLabel("◈")
        icon.setStyleSheet(f"color:{ACCENT}; font-size:17px; background:transparent;")
        hl.addWidget(icon)

        self._title_lbl = QLabel("Bulk Edit")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        self._title_lbl.setFont(f)
        self._title_lbl.setStyleSheet("background:transparent;")
        hl.addWidget(self._title_lbl)

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        hl.addWidget(self._count_lbl)

        hl.addStretch()

        hint = QLabel("Applies all four storyboard rows to selected elements →")
        hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        hl.addWidget(hint)

        self._apply_btn = QPushButton("▶  Apply to Selected")
        self._apply_btn.setObjectName("applyAll")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply)
        hl.addWidget(self._apply_btn)

        outer.addWidget(hdr)

        # ── Body: two storyboard rows ────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background:transparent;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(8, 4, 8, 8)
        bl.setSpacing(3)

        # Column header (mirrors ElementCard column header)
        ch = QHBoxLayout()
        ch.setContentsMargins(4, 0, 0, 0)  # match the 4 px left margin inside StoryboardRow
        ch.setSpacing(6)
        for txt, w in [
            ("Storyboard / DataName", 282), ("Animation", 106), ("Delay", 90),
            ("Duration", 90), ("Easing", 158), ("Direction", 106), ("Rev", 52),
        ]:
            cl = QLabel(txt)
            cl.setFixedWidth(w)
            cl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
            ch.addWidget(cl)
        ch.addStretch()
        bl.addLayout(ch)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        bl.addWidget(sep)

        # TransitionIn row
        self._ti_row = StoryboardRow("TransitionIn", "")
        bl.addWidget(self._ti_row)

        sep_ti = QFrame()
        sep_ti.setObjectName("separator")
        sep_ti.setFrameShape(QFrame.Shape.HLine)
        bl.addWidget(sep_ti)

        # TransitionOut row
        self._to_row = StoryboardRow("TransitionOut", "")
        bl.addWidget(self._to_row)

        sep_to = QFrame()
        sep_to.setObjectName("separator")
        sep_to.setFrameShape(QFrame.Shape.HLine)
        bl.addWidget(sep_to)

        # DataChangeIn row (data_name label updated by sync())
        self._dci_row = StoryboardRow("DataChangeIn", "")
        bl.addWidget(self._dci_row)

        sep_dci = QFrame()
        sep_dci.setObjectName("separator")
        sep_dci.setFrameShape(QFrame.Shape.HLine)
        bl.addWidget(sep_dci)

        # DataChangeOut row
        self._dco_row = StoryboardRow("DataChangeOut", "")
        bl.addWidget(self._dco_row)

        outer.addWidget(body)

    # ── Public API ────────────────────────────────────────────────────────────
    def sync(self, selected_cards: list):
        """Called whenever selection changes. Updates labels and button state."""
        self._selected_cards = selected_cards
        n = len(selected_cards)
        self._count_lbl.setText(f"({n} selected)")
        self._apply_btn.setEnabled(n > 0)

        # Compute a DataName hint from the selected elements' categories
        if n == 0:
            label = "(—)"
        else:
            cats = {element_category(c.element_type) for c in selected_cards}
            if len(cats) == 1:
                cat = next(iter(cats))
                suffix = _BULK_DC_SUFFIX.get(cat, "")
                label = f"(all{suffix})" if suffix else "(all)"
            else:
                label = "(mixed)"

        self._dci_row.update_data_label(label)
        self._dco_row.update_data_label(label)

    # ── Apply ─────────────────────────────────────────────────────────────────
    def _apply(self):
        ti  = self._ti_row.get_entry()
        to_ = self._to_row.get_entry()
        dci = self._dci_row.get_entry()
        dco = self._dco_row.get_entry()
        for card in self._selected_cards:
            card.apply_all_animations(ti, to_, dci, dco)


# ─── Main window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GT Title Animation Editor")
        self.setMinimumSize(1100, 680)
        self.resize(1440, 900)

        # key: tab content QWidget → TabData
        self._tabs: dict[QWidget, TabData] = {}
        self._vmix_titles: list = []

        self._build_ui()
        self.setStyleSheet(STYLESHEET)
        self._setup_shortcuts()
        # self._start_vmix_polling()   # vMix integration — disabled for now

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Main toolbar ──────────────────────────────────────────────────────
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._vmix_dot = QLabel("●")
        self._vmix_dot.setStyleSheet(f"color:{TEXT_DIM}; font-size:18px; padding:0 4px;")
        tb.addWidget(self._vmix_dot)

        self._vmix_status_lbl = QLabel("vMix: not connected")
        self._vmix_status_lbl.setStyleSheet(f"color:{TEXT_DIM};")
        tb.addWidget(self._vmix_status_lbl)

        tb.addSeparator()

        vl = QLabel("vMix Title:")
        vl.setStyleSheet(f"color:{TEXT_DIM};")
        tb.addWidget(vl)

        self._vmix_combo = QComboBox()
        self._vmix_combo.setMinimumWidth(260)
        self._vmix_combo.setPlaceholderText("— no GT titles —")
        tb.addWidget(self._vmix_combo)

        load_vmix_btn = QPushButton("Load")
        load_vmix_btn.setObjectName("secondary")
        load_vmix_btn.setFixedWidth(56)
        load_vmix_btn.clicked.connect(self._load_from_vmix)
        tb.addWidget(load_vmix_btn)

        tb.addSeparator()

        open_btn = QPushButton("Open File…")
        open_btn.setObjectName("secondary")
        open_btn.clicked.connect(self._open_file_dialog)
        tb.addWidget(open_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._save_btn = QPushButton("💾  Save")
        self._save_btn.setFixedWidth(110)
        self._save_btn.clicked.connect(self._save)
        tb.addWidget(self._save_btn)

        # ── Tab widget ────────────────────────────────────────────────────────
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.tabCloseRequested.connect(self._close_tab)
        self._tab_widget.currentChanged.connect(self._on_tab_switched)

        # Placeholder shown when no tabs are open
        self._placeholder = QLabel(
            "Open a .gtzip / .gtxml file  —  or select a vMix GT title above"
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:15px; padding:80px;"
        )

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self._placeholder)
        cl.addWidget(self._tab_widget)
        self._tab_widget.hide()
        self.setCentralWidget(central)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_file_dialog)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        QShortcut(QKeySequence("Ctrl+W"), self, self._close_current_tab)

    # ── vMix ──────────────────────────────────────────────────────────────────
    def _start_vmix_polling(self):
        self._poller = VMixPoller()
        self._poller.titles_updated.connect(self._on_vmix_titles)
        self._poller.connection_changed.connect(self._on_vmix_connection)
        self._poller.start()

    def _on_vmix_connection(self, connected: bool):
        if connected:
            self._vmix_dot.setStyleSheet("color:#a6e3a1; font-size:18px; padding:0 4px;")
            self._vmix_status_lbl.setText("vMix: connected")
            self._vmix_status_lbl.setStyleSheet("color:#a6e3a1;")
        else:
            self._vmix_dot.setStyleSheet(f"color:{TEXT_DIM}; font-size:18px; padding:0 4px;")
            self._vmix_status_lbl.setText("vMix: not connected")
            self._vmix_status_lbl.setStyleSheet(f"color:{TEXT_DIM};")

    def _on_vmix_titles(self, titles: list):
        self._vmix_titles = titles
        prev = self._vmix_combo.currentText()
        self._vmix_combo.blockSignals(True)
        self._vmix_combo.clear()
        for t in titles:
            self._vmix_combo.addItem(f"[{t.number}] {t.title}", userData=t)
        idx = self._vmix_combo.findText(prev)
        if idx >= 0:
            self._vmix_combo.setCurrentIndex(idx)
        self._vmix_combo.blockSignals(False)

    def _load_from_vmix(self):
        idx = self._vmix_combo.currentIndex()
        if idx < 0:
            self._status.showMessage("No vMix GT title selected.")
            return
        title = self._vmix_combo.itemData(idx)
        if not title or not title.filepath:
            QMessageBox.warning(self, "Error", "Could not determine file path for this title.")
            return
        self._load_file(title.filepath)

    # ── File operations ────────────────────────────────────────────────────────
    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open GT Title File", "",
            "GT Title Files (*.gtzip *.gtxml);;All Files (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, filepath: str):
        # If already open, just switch to that tab
        for tw, data in self._tabs.items():
            if data.filepath == filepath:
                self._tab_widget.setCurrentWidget(tw)
                return

        try:
            handler  = GTFileHandler(filepath)
            elements = handler.load()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load:\n{e}")
            return

        # ── Build tab content ────────────────────────────────────────────────
        tab_widget = QWidget()
        tl = QVBoxLayout(tab_widget)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)

        # Info / sub-toolbar bar
        info_bar = QFrame()
        info_bar.setStyleSheet(
            f"background:{HEADER_BG}; border-bottom:1px solid {BORDER};"
        )
        ib = QHBoxLayout(info_bar)
        ib.setContentsMargins(10, 4, 10, 4)
        ib.setSpacing(10)

        path_lbl = QLabel(f"  {filepath}")
        path_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        ib.addWidget(path_lbl)

        count_lbl = QLabel()
        count_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        ib.addWidget(count_lbl)

        ib.addStretch()

        # ── Type filter buttons ──────────────────────────────────────────────
        # Parent=info_bar keeps QButtonGroup alive (prevents Python GC from
        # destroying it when _load_file returns, which would drop signals).
        btn_group = QButtonGroup(info_bar)
        btn_group.setExclusive(True)

        for label in TYPE_FILTER_LABELS:
            fb = QPushButton(label)
            fb.setObjectName("filterBtn")
            fb.setCheckable(True)
            fb.setChecked(label == "All")
            btn_group.addButton(fb)
            ib.addWidget(fb)

        # Separator + Select / Deselect buttons
        vsep_sel = QFrame()
        vsep_sel.setFrameShape(QFrame.Shape.VLine)
        vsep_sel.setStyleSheet(f"color:{BORDER};")
        ib.addWidget(vsep_sel)

        select_all_btn = QPushButton("☑ Select Visible")
        select_all_btn.setObjectName("secondary")
        select_all_btn.setFixedWidth(115)
        deselect_btn = QPushButton("☐ Deselect All")
        deselect_btn.setObjectName("secondary")
        deselect_btn.setFixedWidth(108)
        ib.addWidget(select_all_btn)
        ib.addWidget(deselect_btn)

        # Vertical separator
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setStyleSheet(f"color:{BORDER};")
        ib.addWidget(vsep)

        # ── Name search ──────────────────────────────────────────────────────
        search = QLineEdit()
        search.setPlaceholderText("Search by name…")
        search.setFixedWidth(180)
        ib.addWidget(search)

        vsep2 = QFrame()
        vsep2.setFrameShape(QFrame.Shape.VLine)
        vsep2.setStyleSheet(f"color:{BORDER};")
        ib.addWidget(vsep2)

        expand_btn = QPushButton("Expand All")
        expand_btn.setObjectName("secondary")
        expand_btn.setFixedWidth(90)
        collapse_btn = QPushButton("Collapse All")
        collapse_btn.setObjectName("secondary")
        collapse_btn.setFixedWidth(95)
        ib.addWidget(expand_btn)
        ib.addWidget(collapse_btn)

        tl.addWidget(info_bar)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        cards_widget = QWidget()
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(10, 10, 10, 10)
        cards_layout.setSpacing(8)

        # ── Bulk pseudo card (always visible) ────────────────────────────────
        bulk_card = BulkEditCard()
        cards_layout.addWidget(bulk_card)

        selected_cards: set[ElementCard] = set()

        cards: list[ElementCard] = []
        for el in elements:
            card = ElementCard(el)
            card.changed.connect(
                lambda name, tw=tab_widget: self._on_element_changed(name, tw)
            )
            card.selection_changed.connect(
                lambda name, sel, c=card: _on_selection_changed(c, sel)
            )
            cards_layout.addWidget(card)
            cards.append(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_widget)
        tl.addWidget(scroll)

        # ── Shared filter state (defined before apply_filter so closure works)─
        filter_state = {"text": "", "type": "All"}

        def _on_selection_changed(card: ElementCard, selected: bool):
            if selected:
                selected_cards.add(card)
            else:
                selected_cards.discard(card)
            bulk_card.sync(list(selected_cards))

        select_all_btn.clicked.connect(
            lambda _=False: [c.set_selected(True) for c in cards if c.isVisible()]
        )
        deselect_btn.clicked.connect(
            lambda _=False: [c.set_selected(False) for c in cards]
        )

        # ── Filter function ───────────────────────────────────────────────────
        def apply_filter():
            lo  = filter_state["text"].lower()
            cat = filter_state["type"]
            n_vis = 0
            for card in cards:
                name_ok = not lo or lo in card.element_name.lower()
                type_ok = cat == "All" or element_category(card.element_type) == cat
                card.setVisible(name_ok and type_ok)
                if name_ok and type_ok:
                    n_vis += 1
            count_lbl.setText(
                f"  {n_vis} of {len(cards)} element(s)"
                if n_vis != len(cards) else f"  {len(cards)} element(s)"
            )

        def on_type_btn(btn):
            filter_state["type"] = btn.text()
            apply_filter()

        btn_group.buttonClicked.connect(on_type_btn)
        search.textChanged.connect(
            lambda txt: (filter_state.update({"text": txt}), apply_filter())
        )
        expand_btn.clicked.connect(
            lambda _=False, c=cards: [card.set_collapsed(False) for card in c]
        )
        collapse_btn.clicked.connect(
            lambda _=False, c=cards: [card.set_collapsed(True) for card in c]
        )

        # Initial sync
        bulk_card.sync([])

        # Set initial count
        count_lbl.setText(f"  {len(cards)} element(s)")

        # Store tab data (keyed by the tab content widget)
        tab_data = TabData(
            filepath=filepath,
            handler=handler,
            elements=elements,
            cards=cards,
        )
        self._tabs[tab_widget] = tab_data

        # Add tab
        tab_name = Path(filepath).name
        self._tab_widget.addTab(tab_widget, tab_name)
        self._tab_widget.setCurrentWidget(tab_widget)

        # Show tab widget, hide placeholder
        self._placeholder.hide()
        self._tab_widget.show()

        self._status.showMessage(
            f"Loaded {len(elements)} element(s) from {Path(filepath).name}"
        )

    # ── Tab management ────────────────────────────────────────────────────────
    def _on_tab_switched(self, idx: int):
        widget = self._tab_widget.widget(idx)
        if widget and widget in self._tabs:
            data = self._tabs[widget]
            n = len(data.dirty_elements)
            self._status.showMessage(
                f"{Path(data.filepath).name}  —  {len(data.elements)} element(s)"
                + (f"  —  {n} unsaved change(s)" if n else "")
            )

    def _close_tab(self, idx: int):
        widget = self._tab_widget.widget(idx)
        data   = self._tabs.get(widget)
        if data and data.dirty_elements:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"{Path(data.filepath).name} has unsaved changes.\nClose anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        if widget in self._tabs:
            del self._tabs[widget]
        self._tab_widget.removeTab(idx)
        if self._tab_widget.count() == 0:
            self._tab_widget.hide()
            self._placeholder.show()

    def _close_current_tab(self):
        idx = self._tab_widget.currentIndex()
        if idx >= 0:
            self._close_tab(idx)

    # ── Dirty tracking ────────────────────────────────────────────────────────
    def _on_element_changed(self, element_name: str, tab_widget: QWidget):
        data = self._tabs.get(tab_widget)
        if not data:
            return
        data.dirty_elements.add(element_name)
        # Update tab title
        idx = self._tab_widget.indexOf(tab_widget)
        name = Path(data.filepath).name
        self._tab_widget.setTabText(idx, f"● {name}")
        self._status.showMessage(
            f"Unsaved changes in {name}  —  {len(data.dirty_elements)} element(s) modified"
        )

    # ── Save ──────────────────────────────────────────────────────────────────
    def _save(self):
        widget = self._tab_widget.currentWidget()
        if widget not in self._tabs:
            QMessageBox.information(self, "Nothing to save", "No file is currently open.")
            return
        data = self._tabs[widget]
        try:
            updated = [card.get_element() for card in data.cards]
            data.handler.save(updated)
            # Mark all cards clean
            for card in data.cards:
                card.mark_clean()
            data.dirty_elements.clear()
            # Restore plain tab title
            idx = self._tab_widget.indexOf(widget)
            self._tab_widget.setTabText(idx, Path(data.filepath).name)
            self._status.showMessage(
                f"Saved {len(updated)} element(s) → {data.handler.filepath.name}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        # Check for any tabs with unsaved changes
        dirty = [
            Path(d.filepath).name
            for d in self._tabs.values()
            if d.dirty_elements
        ]
        if dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"Unsaved changes in:\n" + "\n".join(dirty) + "\n\nQuit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        # if hasattr(self, "_poller"):   # vMix integration — disabled for now
        #     self._poller.stop()
        #     self._poller.wait(2000)
        event.accept()


# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
