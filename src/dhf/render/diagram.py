"""Deterministic local component-grid PNG; no platform fonts or network renderer."""

import base64
import re
import struct
import zlib
from pathlib import Path

import yaml

from dhf.config import setting


def diagram_layout(source: str) -> dict:
    nodes = dict(re.findall(r'^\s+(\w+)\["([^"]+)"\]', source, re.M))
    allocations = re.findall(r"(UNIT_\w+) -->\|allocated to\| (COMP_\d+)", source)
    components = sorted(id for id in nodes if id.startswith("COMP_"))
    if not components or len(components) > 12:
        raise ValueError("Unsupported component diagram inventory")
    return {
        "width": 1600,
        "height": 300 + ((len(components) + 2) // 3) * 270,
        "components": [
            {
                "id": id,
                "label": nodes[id],
                "units": sorted(nodes[u].split(": ", 1)[1] for u, c in allocations if c == id),
                "x": 70 + (i % 3) * 500,
                "y": 150 + (i // 3) * 270,
            }
            for i, id in enumerate(components)
        ],
        "external": [label for id, label in nodes.items() if id.startswith("EXT_")],
        "dependencies": [
            {"from": a, "to": b, "call": label}
            for a, label, b in re.findall(r"(COMP_\d+) -->\|([^|]+)\| (COMP_\d+)", source)
        ],
    }


def diagram_image(layout: dict) -> dict:
    """Pure JSON layout → base64 PNG and dimensions; glyph data is versioned config."""
    width, height = layout["width"], layout["height"]
    canvas = bytearray(bytes((255, 255, 255)) * width * height)
    font = yaml.safe_load(Path("specs/render/font5x7.yaml").read_text())

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
    text(70, 90, "SOURCE ALLOCATIONS - CALL ARROWS FROM EXTRACTED CODE", 3)
    positions = {c["id"]: c for c in layout["components"]}
    for c in layout["components"]:
        x, y = c["x"], c["y"]
        box(x, y, 440, 235, (37, 75, 98))
        box(x + 3, y + 3, 434, 229, (246, 249, 251))
        box(x + 3, y + 3, 434, 58, (219, 232, 240))
        text(x + 16, y + 15, c["label"].split(": ", 1)[0], 3)
        text(x + 16, y + 40, c["label"].split(": ", 1)[1], 3)
        for i, unit in enumerate(c["units"]):
            text(x + 16, y + 83 + i * 27, unit, 3)
    # Orthogonal arrow path with a separately listed exact call label.
    for edge in layout["dependencies"]:
        a, b = positions[edge["from"]], positions[edge["to"]]
        x, y = a["x"] + 220, a["y"] + 235
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
