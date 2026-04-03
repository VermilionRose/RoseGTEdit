# RoseGTEdit

A desktop GUI tool for bulk-editing animation storyboards designed in [StudioCoast GT Title Editor](https://www.vmix.com/products/vmix-gt-title-designer.aspx) files (`.gtzip` / `.gtxml`) for vMix.

Built with Python and PyQt6.

---

## Features

- **Open `.gtzip` and `.gtxml` files** — reads GT Title Editor's ZIP archive and raw XML formats, handling their UTF-8/UTF-16 encoding quirks transparently.
- **All element types supported** — TextBlock, Text3D, Image, Rectangle, Ellipse, RightTriangle, Triangle, Layer, and any future GT shape types.
- **Four storyboard slots per element** — Transition In, Transition Out, Data Change In, Data Change Out.
- **Full animation control** — animation type, delay (ms), duration (ms), easing curve, direction, and reverse toggle.
- **Collapsible cards** — expand/collapse individual element cards; Expand All / Collapse All buttons.
- **Filter by type** — show All, Text, Image, Color (shapes), or Layer elements.
- **Search by name** — live name filter across all elements.
- **Selectable elements** — check any combination of element cards and use the **Bulk Edit** panel to apply all four storyboard rows (Transition In, Transition Out, Data Change In, Data Change Out) to all selected elements in one click.
- **Multiple files** — open several files simultaneously as tabs; dirty tabs are marked with `●`.
- **Unsaved-change highlighting** — cards with edits turn amber; a confirmation dialog guards against accidental closes.
- **In-place save** — overwrites the source `.gtzip` atomically (temp file + move), preserving all other archive members.
- **vMix integration** *(coming soon)* — auto-discover GT Title inputs from a running vMix instance via its Web API.

---

## Requirements

- Python 3.10 or newer
- [PyQt6](https://pypi.org/project/PyQt6/) ≥ 6.4.0
- [requests](https://pypi.org/project/requests/) ≥ 2.28.0

---

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/RoseGTEdit.git
cd RoseGTEdit

# (Optional) create a virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

```bash
python main.py
```

1. Click **Open File…** (or press `Ctrl+O`) to open a `.gtzip` or `.gtxml` file.
2. Browse the element cards. Use the filter buttons and the search box to narrow down the list.
3. Edit animation settings directly on any card.
4. To bulk-edit multiple elements at once:
   - Tick the **checkbox** in each element card's header to select it.
   - Use **☑ Select Visible** to select all currently visible cards in one click.
   - Configure any or all of the four storyboard rows in the **Bulk Edit** panel at the top of the list.
   - Click **▶ Apply to Selected** to push those settings to every selected card.
5. Press `Ctrl+S` (or click **💾 Save**) to write the changes back to the file.
6. Press `Ctrl+W` to close the current tab.

---

## File Format Notes

GT Title Editor stores animations as `<Storyboard>` elements inside `document.xml`:

| Storyboard type | XML attribute | Notes |
|---|---|---|
| TransitionIn | *(default, no `Type` attribute)* | All elements share one storyboard |
| TransitionOut | `Type="TransitionOut"` | All elements share one storyboard |
| DataChangeIn | `Type="DataChangeIn"` + `DataName="Elem.Text\|Source\|Color"` | One storyboard per element |
| DataChangeOut | `Type="DataChangeOut"` + `DataName="..."` | One storyboard per element |

Animation attributes: `Object` (element name), `Delay` (ms, integer), `Duration` (seconds, float), `Interpolation` (easing), `Direction`, `Reverse`.

RoseGTEdit displays Duration in milliseconds for convenience and converts to/from seconds on load/save.

---

## Project Structure

```
RoseGTEdit/
├── main.py            # PyQt6 GUI application
├── gtzip_handler.py   # File I/O: .gtzip / .gtxml read & write
├── vmix_client.py     # vMix Web API client (WIP)
└── requirements.txt
```

---

## License

MIT
