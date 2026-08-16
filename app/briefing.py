"""Briefing de arranque: datos ya cacheados, sin LLM."""
from .personalidad import slug_activo


def _tramo(hora):
    if hora < 12:
        return "Buenos días"
    if hora < 20:
        return "Buenas tardes"
    return "Buenas noches"


def _inicio(hora, slug):
    tramo = _tramo(hora)
    if slug == "fermin":
        return f"{tramo}, ¿eh?"
    if slug == "kratos":
        if hora < 12:
            return "El día empieza."
        if hora < 20:
            return "La tarde sigue."
        return "La noche cae."
    if slug == "tobey":
        return f"{tramo}."
    if slug == "amador":
        return "Venga, al lío."
    if slug == "saul":
        return "Qué pasa, bro."
    if slug == "sergio":
        return "Qué pasa, brother."
    return f"{tramo}, señor."


def texto_briefing(status: dict, hora: int) -> str:
    slug = slug_activo()
    bits = [_inicio(hora, slug)]
    w = (status or {}).get("weather") or {}
    if w.get("temp") is not None:
        bits.append(f"Hace {int(w['temp'])} grados.")
    if (status or {}).get("cerebro") == "apagado":
        bits.append("Hermes no responde.")
    else:
        bits.append("Sistemas en orden.")
    return " ".join(bits)
