"""Empaqueta el EBOOT y los datos del fuente para PSP y PSP Go, sin entradas de autotest."""
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]


def verify_source_manifest(manifest: dict) -> int:
    source_root = Path(manifest["source"]).resolve(strict=True)
    hashes = manifest.get("source_files_sha256")
    if not isinstance(hashes, dict) or manifest.get("source_file_count") != len(hashes):
        raise ValueError("El manifiesto no contiene un inventario completo del fuente original")

    current = {p.relative_to(source_root).as_posix(): p for p in source_root.rglob("*") if p.is_file()}
    if set(current) != set(hashes):
        raise ValueError("El árbol fuente cambió después de compilarse; regenere los datos PSP")
    for name, expected in hashes.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError(f"Ruta fuente inválida en el manifiesto: {name}")
        path = current[name]
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source_root):
            raise ValueError(f"Archivo fuente fuera del árbol original: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"El archivo fuente cambió después de compilarse: {name}")

    scripts = manifest.get("scripts_sha256", {})
    for name, expected in scripts.items():
        relative = name.replace("\\", "/")
        if hashes.get(relative) != expected:
            raise ValueError(f"El hash de guion no coincide con el inventario fuente: {name}")
    return len(hashes)


def sync_extracted(files: list[tuple[Path, str]], readme: str, hashes: dict[str, str]) -> Path:
    target = ROOT / "dist/SnootGame-PSP-fuente-preview"
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve(strict=True)
    dist = (ROOT / "dist").resolve(strict=True)
    if target.parent != dist:
        raise ValueError(f"directorio extraido fuera de dist: {target}")

    hash_text = json.dumps(hashes, ensure_ascii=False, indent=2) + "\n"
    expected = {name for _, name in files} | {"LEEME.txt", "SHA256.json"}

    def output_path(name: str) -> Path:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError(f"ruta insegura en el paquete: {name}")
        output = target.joinpath(*relative.parts)
        if not output.resolve().is_relative_to(target):
            raise ValueError(f"ruta fuera del paquete extraido: {name}")
        return output

    for source, name in files:
        output = output_path(name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(source.read_bytes())
    output_path("LEEME.txt").write_text(readme, encoding="utf-8", newline="")
    output_path("SHA256.json").write_text(hash_text, encoding="utf-8", newline="")

    for current in target.rglob("*"):
        if current.is_symlink():
            raise ValueError(f"enlace inesperado en el paquete extraido: {current}")
        if current.is_file() and current.relative_to(target).as_posix() not in expected:
            if not current.resolve().is_relative_to(target):
                raise ValueError(f"archivo obsoleto fuera del paquete extraido: {current}")
            current.unlink()
    for directory in sorted((p for p in target.rglob("*") if p.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    return target


def main() -> None:
    data = ROOT / "build/psp-data/DATA"
    manifest = json.loads((ROOT / "build/psp-data/manifest.json").read_text(encoding="utf-8"))
    source_count = verify_source_manifest(manifest)
    if manifest["language"] != "es" or not manifest["lewd"] or manifest["audio_pending"]:
        raise ValueError("Los datos no corresponden a la configuración PSP del fuente")
    if any(data.glob("*.XA")) or any(data.glob("*.SPU")):
        raise ValueError("El paquete PSP no admite recursos de audio del port PS1")
    files = [(ROOT / "build/psp/EBOOT.PBP", "PSP/GAME/SNOOT/EBOOT.PBP"),
             (ROOT / "build/psp-data/manifest.json", "FUENTE.json")]
    files += [(p, f"PSP/GAME/SNOOT/DATA/{p.name}") for p in sorted(data.iterdir())
              if p.is_file() and p.name.lower() != "shot_names.txt"
              and (p.suffix.upper() in {".IMG", ".OGG", ".PCM", ".VNB", ".TXT", ".AUD", ".JSON"}
                   or p.name in {"FONT.BIN", "GAME.BIN", "GALLERY.BIN"})]
    game_root = Path(manifest["source"]).parent
    for name in ("LICENSE", "CC-BY-SA-4.0.txt", "GNU Affero General Public License Version Three.txt", "GPL-Exception"):
        if (game_root / name).is_file():
            files.append((game_root / name, f"LICENCIAS/{name}"))
    readme = (
        "Snoot Game — vista previa nativa para PSP y PSP Go (controles y audio corregidos)\n\n"
        "Copia PSP/GAME/SNOOT a la raíz de la Memory Stick (ms0:) o de la memoria interna de PSP Go (ef0:).\n"
        "Abre Snoot Game desde Juegos. Español es el único idioma; las imágenes opcionales están activadas.\n"
        "En PPSSPP, copia SNOOT dentro de PSP/GAME de su Memory Stick configurada.\n"
        "En una instalación portátil, esa raíz puede ser la carpeta memstick junto al ejecutable de PPSSPP.\n"
        "Abre EBOOT.PBP desde esa ubicación; extraer el ZIP en dist no instala el juego en la Memory Stick.\n"
        "X: aceptar/avanzar. O: volver. Cruceta/stick: elegir. START: pausa. R: saltar texto leído.\n\n"
        "Juego, arte, música y traducción: Cavemanon y sus colaboradores. Port: Pako Tako.\n"
        "El paquete se genera del fuente Ren'Py; no contiene audio XA/SPU ni imágenes del CD PS1.\n"
        "Conserva la lógica portátil del intérprete. Las pantallas principales y especiales se adaptaron al perfil de PSP.\n"
        "Algunos efectos se sustituyen por equivalentes compatibles y pueden diferir del PC; la fidelidad píxel a píxel no está garantizada.\n"
        "El menú mantiene Comenzar, Continuar, Capítulos extra, Galería y Opciones.\n"
        "Galería: cruceta para elegir, L/R para categoría, X para abrir, cuadrado para ampliar y O para volver.\n"
        "Al ampliar, la cruceta desplaza y L/R cambia de imagen. Animaciones reproduce el clip a 23.976 fps.\n"
        "En Opciones, izquierda/derecha cambia valores; X en Volver o O sale.\n"
        "Opciones permite ajustar volumen, velocidad de texto (instantáneo o 20/35/50/70/100 cps) y autoavance (apagado o 5/10/15/20/30 s).\n"
        "Pruebas en PPSSPP; falta validar PSP y PSP Go reales.\n"
    )
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for path, name in files}
    target = ROOT / "dist/SnootGame-PSP-fuente-preview.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path, name in files:
            archive.writestr(ZipInfo(name, (2026, 1, 1, 0, 0, 0)), path.read_bytes(), compress_type=ZIP_DEFLATED)
        archive.writestr(ZipInfo("LEEME.txt", (2026, 1, 1, 0, 0, 0)), readme, compress_type=ZIP_DEFLATED)
        archive.writestr(ZipInfo("SHA256.json", (2026, 1, 1, 0, 0, 0)),
                         json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", compress_type=ZIP_DEFLATED)
    extracted = sync_extracted(files, readme, hashes)
    print(f"{target}: {len(files)} archivos; {target.stat().st_size} bytes; fuente original {source_count} archivos verificados; "
          f"EBOOT {hashes['PSP/GAME/SNOOT/EBOOT.PBP']}")
    print(f"Directorio extraido sincronizado: {extracted}")


if __name__ == "__main__":
    main()
