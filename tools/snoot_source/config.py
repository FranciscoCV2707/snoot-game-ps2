"""Perfiles del compilador directo de recursos Ren'Py de Snoot Game."""
from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = Path(os.environ.get("SNOOT_SOURCE", r"E:/snoot/snootgame/game")).resolve()
DATA = Path(os.environ.get("SNOOT_BUILD", str(ROOT / "build/source-psp"))).resolve()
if DATA == GAME or DATA.is_relative_to(GAME):
    raise ValueError("La salida del port no puede estar dentro del juego original")


@dataclass(frozen=True)
class SourceProfile:
    name: str = "psp"
    view: tuple[int, int] = (480, 272)
    text_size: int = 14
    text_width: int = 365
    choice_width: int = 444
    textscroll_scale: float = 1.0


PROFILES = {
    "psp": SourceProfile(),
    "ps2": SourceProfile(name="ps2", view=(640, 360), text_size=18, text_width=488,
                         choice_width=592, textscroll_scale=4 / 3),
    "vita": SourceProfile(name="vita", view=(960, 544), text_size=21, text_width=730,
                          choice_width=888, textscroll_scale=1.0),
}
PROFILE_NAME = os.environ.get("SNOOT_PROFILE", "psp").strip().lower() or "psp"
try:
    PROFILE = PROFILES[PROFILE_NAME]
except KeyError as exc:
    raise ValueError(f"perfil fuente no soportado: {PROFILE_NAME}") from exc
