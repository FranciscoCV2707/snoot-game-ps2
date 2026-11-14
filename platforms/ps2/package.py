"""Empaqueta el build de PS2 para consola: carpeta para memoria USB (uLaunchELF/FreeMcBoot) e ISO (OPL o disco).

  dist/ps2/usb/SNOOT/snoot.elf + DATA/   -> copiar la carpeta SNOOT a la raiz de una memoria USB FAT32
  dist/ps2/SnootGame-PS2.iso             -> SYSTEM.CNF + SNOT_000.01 + DATA/
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "ps2dev/ps2dev@sha256:5476fdfbf34d35eb644fde0a6f6533fb554a4a8171ce53dad7cd1df6077dfb05"
BOOT_NAME = "SNOT_000.01"   # OPL solo lista discos cuyo ejecutable tiene forma de codigo de juego
TEST_FILES = ("AUTOTEST.BIN", "shot_names.txt", "TRACE.TXT")


def package(iso: bool = True) -> Path:
    elf = ROOT / "build" / "ps2" / "snoot.elf"
    data = ROOT / "build" / "ps2-source" / "DATA"
    out = ROOT / "dist" / "ps2"
    usb = out / "usb" / "SNOOT"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(data, usb / "DATA", ignore=shutil.ignore_patterns(*TEST_FILES))
    shutil.copy2(elf, usb / "snoot.elf")
    if iso:
        root = out / "iso-root"
        shutil.copytree(usb / "DATA", root / "DATA")
        shutil.copy2(elf, root / BOOT_NAME)
        (root / "SYSTEM.CNF").write_bytes(f"BOOT2 = cdrom0:\\{BOOT_NAME};1\r\nVER = 1.00\r\nVMODE = NTSC\r\n".encode())
        subprocess.run([
            "docker", "run", "--rm", "-v", f"{out.as_posix()}:/out", IMAGE, "sh", "-c",
            "apk add --no-cache xorriso >/tmp/apk.log 2>&1 && xorriso -as mkisofs -l -sysid PLAYSTATION "
            "-V SNOOTGAME -o /out/SnootGame-PS2.iso /out/iso-root",
        ], check=True)
        shutil.rmtree(root)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-iso", action="store_true")
    print(package(not parser.parse_args().no_iso))
