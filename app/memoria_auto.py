"""Preferencias dichas en claro. No se scrapea la charla."""
import re

_REGLA = re.compile(
    r"(?i)\b(?:recuerda(?:\s+que)?|anota que|quiero que(?:\s+siempre)?|no me hables\s+de|odio que)\b"
)


def debe_recordar(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12 or len(t) > 240:
        return False
    return bool(_REGLA.search(t))


def nota_desde(text: str) -> str:
    t = re.sub(r"(?i)^\s*(?:oye\s+)?(?:jarvis|yarvis)[,:]?\s*", "", text or "")
    t = re.sub(r"(?i)^\s*recuerda(?:\s+que)?\s*", "", t)
    t = re.sub(r"(?i)^\s*anota que\s*", "", t)
    return t.strip(" .") or (text or "").strip()
