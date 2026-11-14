"""Genera icon.sys y el icono 3D (.icn) de la partida en la memory card a partir del icono del juego de PC.

El icono es un cuadro plano con el icono original como textura de 128x128 (formato de iconos de PS2:
cabecera, vertices, animacion de un solo cuadro y textura A1B5G5R5 sin comprimir).
"""
from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image

ICON_FILE = "snoot.icn"
TITLE = "Snoot Game"
BACKGROUND = (104, 84, 150)   # morado del menu del juego; tambien rellena lo transparente del icono
HALF_WIDTH, HEIGHT, DEPTH = 4200, 8400, 300   # coordenadas del modelo: Y negativa hacia arriba, origen en la base


def icon_icn(source: Path) -> bytes:
    image = Image.open(source).convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)
    flat = Image.new("RGBA", image.size, BACKGROUND + (255,))
    flat.alpha_composite(image)
    texture = b"".join(struct.pack("<H", 0x8000 | (b >> 3) << 10 | (g >> 3) << 5 | (r >> 3))
                       for r, g, b, _ in flat.getdata())
    corners = {"tl": (-HALF_WIDTH, -HEIGHT, 0, 0), "tr": (HALF_WIDTH, -HEIGHT, 4096, 0),
               "bl": (-HALF_WIDTH, 0, 0, 4096), "br": (HALF_WIDTH, 0, 4096, 4096)}
    # Dos caras (frente y dorso, con el orden de vertices invertido): la lista del navegador y la vista de detalle
    # miran el icono desde lados distintos y una sola cara desaparece en una de las dos.
    out = struct.pack("<IIIII", 0x010000, 1, 0x07, 0x3F800000, 12)
    for order, z in ((("tl", "tr", "bl", "tr", "br", "bl"), -DEPTH), (("tl", "bl", "tr", "tr", "bl", "br"), DEPTH)):
        for name in order:
            x, y, u, v = corners[name]
            out += struct.pack("<hhhH", x, y, z, 1024)                  # posicion (una sola forma)
            out += struct.pack("<hhhH", 0, 0, -4096 if z < 0 else 4096, 0)  # normal
            out += struct.pack("<hh4B", u, v, 128, 128, 128, 128)
    out += struct.pack("<IIfII", 0x01, 1, 1.0, 0, 1)      # animacion: un cuadro
    out += struct.pack("<IIff", 0, 1, 1.0, 1.0)
    return out + texture


def icon_sys() -> bytes:
    wide = "".join(chr(0x3000) if c == " " else chr(ord(c) + 0xFEE0) for c in TITLE).encode("shift_jis")
    out = b"PS2D" + struct.pack("<HHII", 0, len(wide), 0, 0x60)
    for corner in (BACKGROUND, BACKGROUND, (40, 30, 70), (40, 30, 70)):
        out += struct.pack("<4i", *corner, 0)
    for direction in ((0.5, 0.5, 0.5), (0.0, -0.4, -0.1), (-0.5, -0.5, 0.5)):
        out += struct.pack("<4f", *direction, 0.0)
    for colour in ((0.5, 0.5, 0.5), (0.3, 0.3, 0.3), (0.3, 0.3, 0.3)):
        out += struct.pack("<4f", *colour, 0.0)
    out += struct.pack("<4f", 0.6, 0.6, 0.6, 0.0)
    out += wide.ljust(68, b"\0")
    out += ICON_FILE.encode().ljust(64, b"\0") * 3
    out += bytes(512)
    assert len(out) == 964
    return out


def c_array(name: str, data: bytes) -> str:
    rows = [",".join(str(b) for b in data[i:i + 32]) for i in range(0, len(data), 32)]
    return f"static const unsigned char {name}[{len(data)}] = {{\n" + ",\n".join(rows) + "\n};\n"


def write_header(source: Path, target: Path) -> None:
    target.write_text(
        f'#pragma once\n#define PS2_ICON_FILE "{ICON_FILE}"\n'
        + c_array("ps2_icon_sys", icon_sys()) + c_array("ps2_icon_icn", icon_icn(source)),
        encoding="utf-8", newline="\n")
