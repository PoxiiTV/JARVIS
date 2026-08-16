"""Tono del turno según el ajuste PERSONALIDAD. Las acciones no cambian."""
import json
import unicodedata
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "personalidades"

_CABECERA = (
    "PERSONAJE ACTIVO: pisas el tono de mayordomo y el tratamiento señor. "
    "NO pisas VERDAD, tools, Hermes, Spotify, Tuya ni RECIBO. "
    "NUNCA inventes que has enviado un Telegram, un correo o un archivo. "
    "Si la tool no devolvió ok, dilo. Acciones iguales; solo cambia cómo hablas.\n\n"
)

_NOMBRES = {
    "fermin": "Fermín",
    "kratos": "Kratos",
    "tobey": "Tobey",
    "amador": "Amador",
    "saul": "Saul",
    "sergio": "Sergio",
}


def _norm(s):
    if not s:
        return ""
    t = unicodedata.normalize("NFD", str(s).strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _mapa():
    p = DIR / "mapa.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _slugs_con_ficha():
    return [s for s in _mapa() if (DIR / f"{s}.md").is_file()]


def slug_de(nombre):
    n = _norm(nombre)
    if not n:
        return None
    padded = f" {n} "
    for slug, aliases in _mapa().items():
        if not isinstance(aliases, list):
            continue
        for a in aliases:
            an = _norm(a)
            if not an:
                continue
            if an == n or f" {an} " in padded:
                return str(slug)
    return None


def slug_activo(valor=None):
    if valor is None:
        from .config import Config
        valor = getattr(Config, "PERSONALIDAD", "") or ""
    n = _norm(valor)
    if not n or n in ("jarvis", "-", "none"):
        return None
    if n in _slugs_con_ficha():
        return n
    via = slug_de(valor)
    if via in _slugs_con_ficha():
        return via
    return None


def opciones():
    out = [{"slug": "jarvis", "nombre": "JARVIS"}]
    for slug in _mapa():
        if slug not in _slugs_con_ficha():
            continue
        out.append({"slug": slug, "nombre": _NOMBRES.get(slug, slug.capitalize())})
    return out


def bloque(clave=None):
    slug = slug_activo() if clave is None else slug_activo(clave)
    if not slug:
        return None
    path = DIR / f"{slug}.md"
    if not path.is_file():
        return None
    cuerpo = path.read_text(encoding="utf-8").strip()
    if not cuerpo:
        return None
    tics = DIR / f"{slug}.tics.txt"
    if tics.is_file():
        lista = tics.read_text(encoding="utf-8").strip()
        if lista:
            cuerpo += (
                "\n\nTICS: abusa de estos en CASI CADA frase (1 o 2). "
                "Van en el habla, el dato en medio y corto. "
                "No el mismo tic dos turnos seguidos. "
                "Los gags de COLETILLAS no son tics: esos solo si pega el momento. "
                "Si la tool no dio ok, dilo igual, con tics.\n"
                + lista
            )
    dichos = DIR / f"{slug}.dichos.txt"
    if dichos.is_file():
        pares = dichos.read_text(encoding="utf-8").strip()
        if pares:
            cuerpo += (
                "\n\nDISLEXIA Y DICHOS AL REVÉS: un poco de dislexia al hablar "
                "(palabras largas trocadas). TODO refrán, dicho o cierre de risa "
                "se dice MAL, nunca bien. Cruzas las palabras que suenan parecido. "
                "Patrón: moco de pavo se dice poco de pato. Nunca el dicho bien. "
                "Inventa tropezones nuevos igual. NUNCA troces el dato de la tool "
                "(escritorio, grados, nombres de archivo, Hermes).\n"
                + pares
            )
    historia = DIR / f"{slug}.historia.md"
    if historia.is_file():
        vida = historia.read_text(encoding="utf-8").strip()
        if vida:
            cuerpo += (
                "\n\nMEMORIA DEL PERSONAJE: esto es TU vida, todas las temporadas. "
                "La has vivido. Primera persona si sale el tema. "
                "NO recites ficha ni temporadas si no te preguntan. "
                "En una orden (HTML, Spotify, luz, Hermes) cero biografía. "
                "No inventes capítulos que no estén aquí. Si no está escrito, dilo.\n"
                + vida
            )
    return _CABECERA + cuerpo
