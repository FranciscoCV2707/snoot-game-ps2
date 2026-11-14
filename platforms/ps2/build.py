"""Compila Snoot con el toolchain y SDL2 de PS2SDK dentro de Docker."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "ps2dev/ps2dev@sha256:5476fdfbf34d35eb644fde0a6f6533fb554a4a8171ce53dad7cd1df6077dfb05"
SOURCE_DIRS = ("engine/core", "engine/app", "engine/modules", "games/snoot", "platforms/sdl")
INCLUDE_DIRS = ("engine/core", "engine/platform", "engine/app", "engine/modules", "games/snoot", "platforms/sdl")
SOURCE = Path(os.environ.get("SNOOT_SOURCE", r"E:/snoot/snootgame/game"))
DATA_OUT = ROOT / "build" / "ps2-source"


def ensure_source_data(rebuild: bool = False) -> Path:
    """Construye o reutiliza datos cotejados directamente con Snoot Game para PC."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.snoot_source.__main__ import hash_source_tree

    manifest_path = DATA_OUT / "manifest.json"
    if not rebuild and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = SOURCE.resolve(strict=True)
        menu_path = DATA_OUT / "DATA" / "PS2_MENU.json"
        menu_valid = False
        if menu_path.is_file():
            menu_manifest = json.loads(menu_path.read_text(encoding="utf-8"))
            menu_valid = (menu_manifest.get("size") == [640, 448]
                          and any(entry.get("name") == "SYSTEM_MENU.IMG" for entry in menu_manifest.get("files", [])))
        if (manifest.get("source") == str(source) and manifest.get("profile") == "ps2"
                and manifest.get("language") == "es" and manifest.get("lewd") is True
                and manifest.get("audio_pending") is False
                and manifest.get("source_files_sha256") == hash_source_tree(source) and menu_valid):
            return DATA_OUT / "DATA"

    subprocess.run([
        sys.executable, "-m", "tools.snoot_source", "--game", str(SOURCE), "--out", str(DATA_OUT),
        "--profile", "ps2",
    ], cwd=ROOT, check=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("profile") != "ps2" or manifest.get("source_files_sha256") != hash_source_tree(SOURCE):
        raise RuntimeError("Los datos PS2 no corresponden al estado actual del fuente original")
    return DATA_OUT / "DATA"


def prepare_sources(out: Path, trace: bool) -> Path:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    source = out / "src"
    if source.exists():
        shutil.rmtree(source)
    source.mkdir(parents=True)
    sources = []
    for folder in SOURCE_DIRS:
        for path in sorted((ROOT / folder).glob("*.c")):
            name = folder.replace("/", "_") + "_" + path.name
            target = source / name
            shutil.copy2(path, target)
            sources.append(name)

    # decodificador Vorbis en float (vorbis_stb.h): stb_vorbis.c solo se compila a traves de vorbis_stb.c
    for name in ("stb_vorbis.c", "vorbis_stb.c", "vorbis_stb.h"):
        shutil.copy2(ROOT / "platforms" / "ps2" / name, source / name)
    sources.append("vorbis_stb.c")

    generated = source / "generated"
    generated.mkdir()
    (generated / "game_config.h").write_text(
        '#pragma once\n#define VN_SEEN_BYTES 2048\n#define VN_SAVE_TITLE "SNOOT GAME"\n'
        '#define VN_SAVE_PREFIX "BASLUS-99999SNOOT"\n#define VN_SAVE_MAGIC "SNS1"\n',
        encoding="utf-8",
        newline="\n",
    )
    from platforms.ps2.icon import write_header

    write_header(SOURCE.parent / "icon.ico", generated / "ps2_icon.h")
    (source / "Makefile").write_text(makefile(sources, trace), encoding="utf-8", newline="\n")
    return source


def makefile(sources: list[str], trace: bool) -> str:
    flags = "-DVN_TRACE" if trace else ""
    # p. ej. VN_PS2_EXTRA_FLAGS=-DVN_PS2_SAVE_MC para probar la memory card con un build de traza
    flags += " " + os.environ.get("VN_PS2_EXTRA_FLAGS", "")
    flags += " -DSCREEN_W=640 -DSCREEN_H=448 -DVIEW_Y=44 -DVIEW_H=360 -DVN_PS2_NATIVE_MENU"
    # Cache de imagenes: hasta 48 entradas y 6 MiB de texturas (cota de img_memory_bound); pasado eso se desaloja lo que no
    # esta en pantalla. Con 16 entradas fijas, una animacion de mas cuadros (la cola de Fang: 38) releia cada uno.
    flags += " -DSDL_TARGET_RES_CACHE=48 -DSDL_TARGET_RES_BYTES=6291456u -DSDL_TARGET_RES_SOFT_BYTES"
    flags += " -DVN_NATIVE_AUDIO"
    # -iquote: nuestros "input.h" y compania antes que los del SDK (ps2sdk trae su propio input.h en ee/include)
    includes = " ".join(f"-iquote /src/{path}" for path in INCLUDE_DIRS)
    includes += " -Igenerated -I$(PS2SDK)/ports/include"
    objects = " ".join(path.removesuffix(".c") + ".o" for path in sources)
    return (
        "EE_BIN = /src/build/ps2/snoot.elf\n"
        f"EE_OBJS = {objects}\n"
        f"EE_INCS = {includes}\n"
        "EE_CFLAGS = -std=c99 -Wall -Wextra -Wno-unused-parameter -pedantic -O2 "
        f"{flags}\n"
        "EE_LDFLAGS = -L$(PS2SDK)/ports/lib -L$(PS2DEV)/gsKit/lib\n"
        "EE_LIBS = -lSDL2main -lSDL2 -lpad -lmc -lm -lpatches -lgskit -ldmakit -lps2_drivers -lfileXio\n"
        "all: $(EE_BIN)\n"
        "include $(PS2SDK)/samples/Makefile.pref\n"
        "include $(PS2SDK)/samples/Makefile.eeglobal\n"
    )


def build(trace: bool = False, rebuild_data: bool = False) -> Path:
    ensure_source_data(rebuild_data)
    out = ROOT / "build" / "ps2"
    out.mkdir(parents=True, exist_ok=True)
    prepare_sources(out, trace)
    command = [
        "docker", "run", "--rm", "-v", f"{ROOT.as_posix()}:/src", "-w", "/src/build/ps2/src",
        IMAGE, "sh", "-c", "apk add --no-cache make >/tmp/apk.log 2>&1 && make",
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    return out / "snoot.elf"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--rebuild-data", action="store_true", help="regenerar los recursos desde el fuente original")
    args = parser.parse_args()
    print(build(args.trace, args.rebuild_data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
