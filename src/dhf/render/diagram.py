"""Deterministic local component-grid PNG; no platform fonts or network renderer."""

import base64
import re
import struct
import zlib
from pathlib import Path

import yaml

from dhf.config import setting

LABEL_CHARS = 22  # glyphs that fit one component box line at scale 3
UNITS_SHOWN = 10  # unit lines per box; the rest are counted, keeping the figure bounded


def fit(label: str) -> str:
    """Shorten to one box line. Dotted identifiers abbreviate leading segments to initials
    (Ks.FleetMonitorService.Api → K.F.Api); names without spaces keep their distinctive
    end, and titles keep their start."""
    if len(label) <= LABEL_CHARS:
        return label
    parts = label.split(".")
    if len(parts) > 1 and all(re.fullmatch(r"[A-Za-z_]\w*", part) for part in parts):
        for index in range(len(parts) - 1):
            if len(".".join(parts)) <= LABEL_CHARS:
                break
            parts[index] = parts[index][:1]
        label = ".".join(parts)
    if len(label) <= LABEL_CHARS:
        return label
    if " " in label:
        return label[: LABEL_CHARS - 3] + "..."
    return "..." + label[3 - LABEL_CHARS :]


def diagram_layout(source: str) -> dict:
    """Mermaid source → grid layout. Units are allocation sources (or UNIT_ nodes),
    interfaces are EXT_ nodes and every other node is a component; boxes grow to fit the
    largest unit list, so documented architectures of any size lay out."""
    nodes = dict(re.findall(r'^\s+(\w+)\["([^"]+)"\]', source, re.M))
    allocations = re.findall(r"^\s+(\w+) -->\|allocated to\| (\w+)", source, re.M)
    units = {u for u, _ in allocations} | {id for id in nodes if id.startswith("UNIT_")}
    components = sorted(id for id in nodes if id not in units and not id.startswith("EXT_"))
    if not components:
        raise ValueError("Unsupported component diagram inventory")
    listed = {}
    for id in components:
        names = sorted(fit(nodes.get(u, u).rsplit(": ", 1)[-1]) for u, c in allocations if c == id)
        if len(names) > UNITS_SHOWN:
            names = names[: UNITS_SHOWN - 1] + [f"AND {len(names) - UNITS_SHOWN + 1} MORE"]
        listed[id] = names
    allocated = {u for u, c in allocations if c in components}
    # Unit lines start 83 px down, 27 px apart, 21 px tall; keep a 20 px bottom margin.
    box = max(235, 97 + max(len(v) for v in listed.values()) * 27)
    return {
        "width": 1600,
        "height": 300 + ((len(components) + 2) // 3) * (box + 35),
        "box_height": box,
        "components": [
            {
                "id": id,
                "label": nodes[id],
                "units": listed[id],
                "x": 70 + (i % 3) * 500,
                "y": 150 + (i // 3) * (box + 35),
            }
            for i, id in enumerate(components)
        ],
        "external": [label for id, label in nodes.items() if id.startswith("EXT_")],
        "unplaced": len(units - allocated),  # units without a software item, never silent
        "dependencies": [
            {"from": a, "to": b, "call": label}
            for a, label, b in re.findall(r"^\s+(\w+) -->\|([^|]+)\| (\w+)", source, re.M)
            if a in components and b in components
        ],
    }


def diagram_image(layout: dict) -> dict:
    """Pure JSON layout → base64 PNG and dimensions; glyph data is versioned config."""
    width, height = layout["width"], layout["height"]
    canvas = bytearray(bytes((255, 255, 255)) * width * height)
    font = yaml.safe_load(Path("specs/render/font5x7.yaml").read_text(encoding="utf-8"))

    def box(x: int, y: int, w: int, h: int, color: tuple) -> None:
        for yy in range(max(0, y), min(height, y + h)):
            start, end = max(0, x), min(width, x + w)
            if start < end:
                canvas[(yy * width + start) * 3 : (yy * width + end) * 3] = bytes(color) * (
                    end - start
                )

    def text(x: int, y: int, value: str, scale: int = 3) -> None:
        for i, char in enumerate(value.upper()):
            for row, bits in enumerate(font.get(char, font["?"])):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        box(
                            x + i * 6 * scale + col * scale,
                            y + row * scale,
                            scale,
                            scale,
                            (25, 48, 64),
                        )

    text(70, 35, setting("DHF_PRODUCT_NAME", "Kestrel") + " - SOFTWARE COMPONENTS AND UNITS", 4)
    text(
        70,
        90,
        "SOURCE ALLOCATIONS - CALL ARROWS FROM EXTRACTED CODE"
        if layout["dependencies"]
        else "SOURCE ALLOCATIONS",
        3,
    )
    if layout["unplaced"]:
        text(70, 118, f"{layout['unplaced']} UNITS NOT ALLOCATED TO A SOFTWARE ITEM", 3)
    positions = {c["id"]: c for c in layout["components"]}
    tall = layout["box_height"]
    for c in layout["components"]:
        x, y = c["x"], c["y"]
        box(x, y, 440, tall, (37, 75, 98))
        box(x + 3, y + 3, 434, tall - 6, (246, 249, 251))
        box(x + 3, y + 3, 434, 58, (219, 232, 240))
        text(x + 16, y + 15, fit(c["label"].split(": ", 1)[0]), 3)
        text(x + 16, y + 40, fit(c["label"].split(": ", 1)[-1]), 3)
        for i, unit in enumerate(c["units"]):
            text(x + 16, y + 83 + i * 27, unit, 3)
    # Orthogonal arrow path with a separately listed exact call label.
    for edge in layout["dependencies"]:
        a, b = positions[edge["from"]], positions[edge["to"]]
        x, y = a["x"] + 220, a["y"] + tall
        tx, ty = b["x"] + 220, b["y"]
        mid = y + 15
        box(x, y, 3, mid - y, (45, 118, 126))
        box(min(x, tx), mid, abs(tx - x) + 3, 3, (45, 118, 126))
        box(tx, min(mid, ty), 3, abs(ty - mid), (45, 118, 126))
        for i in range(10):
            box(tx - (9 - i), ty - 10 + i, 2 * (9 - i) + 3, 1, (45, 118, 126))
    bottom = height - 125
    for i, interface in enumerate(layout["external"]):
        text(70, bottom + i * 27, "DECLARED INTERFACE: " + interface, 3)
    for i, e in enumerate(layout["dependencies"]):
        text(
            70,
            height - 50 - i * 27,
            e["from"].replace("_", "-") + " -> " + e["to"].replace("_", "-") + ": " + e["call"],
            3,
        )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = b"".join(b"\0" + canvas[y * width * 3 : (y + 1) * width * 3] for y in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )
    return {"png_base64": base64.b64encode(png).decode(), "width": width, "height": height}


def diagram_bytes(source: str) -> bytes:
    return base64.b64decode(diagram_image(diagram_layout(source))["png_base64"])


def write_diagrams(doc: str, sections: list[dict], root: Path) -> list[dict]:
    import hashlib

    output = []
    for section in sections:
        if "diagram" not in section["facts"]:
            continue
        source = section["facts"]["diagram"] + "\n"
        for suffix, data, format in [
            ("mmd", source.encode(), "mermaid-source"),
            ("png", diagram_bytes(source), "local-png"),
        ]:
            name = doc + "." + section["id"] + "." + suffix
            (root / name).write_bytes(data)
            output.append(
                {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "format": format}
            )
    return output
