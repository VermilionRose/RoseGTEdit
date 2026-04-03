"""
GT Title Editor file handler.
Supports .gtzip (ZIP archive containing document.xml) and .gtxml (raw XML).

GT Title Editor writes document.xml as UTF-8 bytes but declares
encoding="utf-16" in the XML header.  We detect the real encoding
via BOM / byte inspection, parse with ElementTree, and write back in
the same encoding so GT Title Editor is happy.
"""

import zipfile
import shutil
import tempfile
import copy
from pathlib import Path
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET


ANIMATION_TYPES = [
    "None", "Bounce", "Expand", "Fade", "Fly", "Hidden",
    "ImageSequence", "Reveal", "Rotate", "Scroll", "Zoom", "ZoomFade"
]

EASING_TYPES = [
    "Linear",
    "CubicEasingIn",  "CubicEasingOut",  "CubicEasingInOut",
    "QuadraticEasingIn", "QuadraticEasingOut", "QuadraticEasingInOut",
    "SineEasingIn",   "SineEasingOut",   "SineEasingInOut",
    "BounceEasingOut", "ElasticEasingOut",
    "BackEasingIn",   "BackEasingOut",
]

DIRECTIONS = [
    "", "Left", "Right", "Top", "Bottom",
    "TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center",
]

STORYBOARD_TYPES = ["TransitionIn", "TransitionOut", "DataChangeIn", "DataChangeOut"]


# ─── Encoding helpers ─────────────────────────────────────────────────────────

def _decode_xml_bytes(raw: bytes) -> tuple[str, str]:
    """
    Decode raw XML bytes to a Python str.

    GT Title Editor quirk: files are physically UTF-8 (or ASCII) but
    carry encoding="utf-16" in the XML declaration.  We detect the real
    encoding by BOM inspection and byte-order sniffing, ignoring the
    (potentially wrong) declaration.

    Returns (xml_str, encoding_used).
    """
    # UTF-16 BOM: FF FE (LE) or FE FF (BE)
    if raw[:2] == b'\xff\xfe':
        return raw.decode('utf-16-le', errors='replace'), 'utf-16-le'
    if raw[:2] == b'\xfe\xff':
        return raw.decode('utf-16-be', errors='replace'), 'utf-16-be'

    # UTF-8 BOM: EF BB BF
    if raw[:3] == b'\xef\xbb\xbf':
        return raw[3:].decode('utf-8'), 'utf-8-sig'

    # Heuristic: if first byte is a printable ASCII char the file is byte-oriented
    if raw and raw[0] < 0x80:
        for enc in ('utf-8', 'latin-1'):
            try:
                return raw.decode(enc), enc
            except UnicodeDecodeError:
                continue

    # Last resort: try utf-16 (relies on BOM which may be missing → will often fail)
    for enc in ('utf-16', 'utf-16-le', 'utf-16-be'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue

    raise ValueError("Cannot determine encoding of document.xml")


def _parse_xml_str(xml_str: str) -> ET.Element:
    """
    Parse an XML string into an ElementTree Element.

    Strips the <?xml … ?> declaration first so ElementTree doesn't
    choke on an encoding= attribute that no longer matches the string.
    """
    stripped = xml_str.lstrip()
    if stripped.startswith('<?xml'):
        end = stripped.index('?>') + 2
        stripped = stripped[end:].lstrip()
    return ET.fromstring(stripped)


def _serialize_root(root: ET.Element, source_encoding: str) -> bytes:
    """
    Serialize an ElementTree root back to bytes.

    We always write in the same physical encoding that was detected on
    load (preserving whatever GT Title Editor produced), but keep the
    original encoding="utf-16" declaration so GT Title Editor accepts it.
    """
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding='unicode')
    full = '<?xml version="1.0" encoding="utf-16"?>\r\n' + body

    # Physical encoding: map the detected encoding to what we write
    if source_encoding in ('utf-16-le', 'utf-16-be', 'utf-16'):
        return full.encode(source_encoding)
    else:
        # UTF-8, latin-1, utf-8-sig → write as UTF-8 (matches original)
        return full.encode('utf-8')


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class AnimationEntry:
    anim_type: str = "None"        # "None" means no animation
    delay: int = 0                 # milliseconds
    duration: float = 0.0          # seconds; 0 = let GT use its default
    interpolation: str = "Linear"
    direction: str = ""
    reverse: bool = False


@dataclass
class GTElement:
    name: str
    element_type: str              # "TextBlock" | "Image" | "Rectangle" | "Ellipse"
    transition_in:  AnimationEntry = field(default_factory=AnimationEntry)
    transition_out: AnimationEntry = field(default_factory=AnimationEntry)
    data_change_in: AnimationEntry = field(default_factory=AnimationEntry)
    data_change_out: AnimationEntry = field(default_factory=AnimationEntry)

    @property
    def data_name(self) -> str:
        """DataName string used in DataChangeIn/Out storyboards."""
        if self.element_type == "Image":
            suffix = "Source"
        elif self.element_type in ("TextBlock", "Text3D"):
            suffix = "Text"
        elif self.element_type == "Layer":
            # Layers don't participate in DataChange storyboards
            return ""
        else:
            # Rectangle, Ellipse, RightTriangle, Triangle, etc.
            suffix = "Color"
        return f"{self.name}.{suffix}"


# ─── XML node helpers ─────────────────────────────────────────────────────────

def _parse_animation_node(node: ET.Element) -> AnimationEntry:
    def _int(v, d=0):
        try: return int(v)
        except: return d

    def _float(v, d=0.0):
        try: return float(v)
        except: return d

    return AnimationEntry(
        anim_type=node.tag,
        delay=_int(node.get("Delay", "0")),
        duration=_float(node.get("Duration", "0")),
        interpolation=node.get("Interpolation", "Linear"),
        direction=node.get("Direction", ""),
        reverse=node.get("Reverse", "False").lower() == "true",
    )


def _build_animation_node(element_name: str, entry: AnimationEntry) -> ET.Element:
    node = ET.Element(entry.anim_type)
    node.set("Object", element_name)
    if entry.delay:
        node.set("Delay", str(entry.delay))
    if entry.duration:
        v = entry.duration
        node.set("Duration", str(int(v)) if v == int(v) else str(v))
    if entry.interpolation and entry.interpolation != "Linear":
        node.set("Interpolation", entry.interpolation)
    if entry.direction:
        node.set("Direction", entry.direction)
    if entry.reverse:
        node.set("Reverse", "True")
    return node


# ─── Parse ────────────────────────────────────────────────────────────────────

def _extract_elements(root: ET.Element) -> list[GTElement]:
    """
    Walk the composition tree and collect every named animatable element.

    Rules:
    - "Layer" elements are collected by Name AND their inner Composition
      is recursed into (so child elements are also collected).
    - Any other XML element whose tag contains no "." and that has a
      non-empty Name attribute is treated as animatable.  This catches
      TextBlock, Text3D, Image, Rectangle, Ellipse, RightTriangle,
      Triangle, and any future GT shape types without needing an
      explicit whitelist.
    - Sub-property elements (TextBlock.Fill, Rectangle.Stroke, etc.)
      are skipped because their tags contain ".".
    """
    elements_by_name: dict[str, GTElement] = {}
    order: list[str] = []

    def _walk(comp: ET.Element):
        for child in comp:
            tag  = child.tag
            name = child.get("Name", "")
            if tag == "Layer":
                # Layers are animatable AND contain child elements
                if name and name not in elements_by_name:
                    elements_by_name[name] = GTElement(name=name, element_type="Layer")
                    order.append(name)
                inner = child.find("Layer.Composition/Composition")
                if inner is not None:
                    _walk(inner)
            elif "." not in tag and name:
                # Any other named, non-dotted element (TextBlock, Image,
                # Rectangle, Ellipse, RightTriangle, Triangle, Text3D …)
                if name not in elements_by_name:
                    elements_by_name[name] = GTElement(name=name, element_type=tag)
                    order.append(name)

    _walk(root)

    # Populate animation entries from <Storyboard> nodes
    for sb in root.findall("Storyboard"):
        sb_type  = sb.get("Type") or "TransitionIn"
        data_name = sb.get("DataName", "")
        anims = sb.find("Storyboard.Animations")
        if anims is None:
            continue
        for anim_node in anims:
            obj = anim_node.get("Object", "")
            if obj not in elements_by_name:
                continue
            el    = elements_by_name[obj]
            entry = _parse_animation_node(anim_node)
            if sb_type == "TransitionIn":
                el.transition_in = entry
            elif sb_type == "TransitionOut":
                el.transition_out = entry
            elif sb_type == "DataChangeIn" and data_name == el.data_name:
                el.data_change_in = entry
            elif sb_type == "DataChangeOut" and data_name == el.data_name:
                el.data_change_out = entry

    return [elements_by_name[n] for n in order]


# ─── Write ────────────────────────────────────────────────────────────────────

def _rebuild_storyboards(root: ET.Element, elements: list[GTElement]):
    """Remove all existing <Storyboard> children, then rebuild from elements."""
    for sb in root.findall("Storyboard"):
        root.remove(sb)

    def _make_sb(sb_type: str, data_name: str = "") -> tuple[ET.Element, ET.Element]:
        sb_el = ET.SubElement(root, "Storyboard")
        if sb_type != "TransitionIn":
            sb_el.set("Type", sb_type)
        if data_name:
            sb_el.set("DataName", data_name)
        anims = ET.SubElement(sb_el, "Storyboard.Animations")
        return sb_el, anims

    # TransitionIn — all elements in one storyboard
    ti = [(el, el.transition_in) for el in elements if el.transition_in.anim_type != "None"]
    if ti:
        _, anims = _make_sb("TransitionIn")
        for el, entry in ti:
            anims.append(_build_animation_node(el.name, entry))

    # TransitionOut — all elements in one storyboard
    to_ = [(el, el.transition_out) for el in elements if el.transition_out.anim_type != "None"]
    if to_:
        _, anims = _make_sb("TransitionOut")
        for el, entry in to_:
            anims.append(_build_animation_node(el.name, entry))

    # DataChangeIn — one storyboard per element (each has its own DataName)
    for el in elements:
        if el.data_change_in.anim_type != "None":
            _, anims = _make_sb("DataChangeIn", el.data_name)
            anims.append(_build_animation_node(el.name, el.data_change_in))

    # DataChangeOut — one storyboard per element
    for el in elements:
        if el.data_change_out.anim_type != "None":
            _, anims = _make_sb("DataChangeOut", el.data_name)
            anims.append(_build_animation_node(el.name, el.data_change_out))


# ─── Public handler ───────────────────────────────────────────────────────────

class GTFileHandler:
    """Read and write .gtzip / .gtxml files."""

    def __init__(self, filepath: str):
        self.filepath      = Path(filepath)
        self.is_zip        = self.filepath.suffix.lower() == ".gtzip"
        self._root: ET.Element | None = None
        self._encoding: str = "utf-8"   # detected on load

    # ── load ──────────────────────────────────────────────────────────────────
    def load(self) -> list[GTElement]:
        raw = self._read_raw()
        xml_str, self._encoding = _decode_xml_bytes(raw)
        self._root = _parse_xml_str(xml_str)
        return _extract_elements(self._root)

    def _read_raw(self) -> bytes:
        if self.is_zip:
            with zipfile.ZipFile(self.filepath, "r") as zf:
                return zf.read("document.xml")
        return self.filepath.read_bytes()

    # ── save ──────────────────────────────────────────────────────────────────
    def save(self, elements: list[GTElement]):
        if self._root is None:
            raise RuntimeError("Call load() before save()")

        # Work on a deep copy so we don't mutate the live tree
        root_copy = copy.deepcopy(self._root)
        _rebuild_storyboards(root_copy, elements)
        new_bytes = _serialize_root(root_copy, self._encoding)

        if self.is_zip:
            self._save_zip(new_bytes)
        else:
            self.filepath.write_bytes(new_bytes)

    def _save_zip(self, new_doc_bytes: bytes):
        """Replace document.xml inside the gtzip archive, keeping everything else."""
        tmp = self.filepath.with_suffix(".tmp_save.gtzip")
        try:
            with zipfile.ZipFile(self.filepath, "r") as zin, \
                 zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                for info in zin.infolist():
                    if info.filename == "document.xml":
                        zout.writestr(info.filename, new_doc_bytes)
                    else:
                        zout.writestr(info, zin.read(info.filename))
            shutil.move(str(tmp), str(self.filepath))
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise
