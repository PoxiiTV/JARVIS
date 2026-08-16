"""Recibo de tool: una linea para el HUD, nunca para el TTS."""
import re

_REC = re.compile(r"(?im)^RECIBO:\s+(ok|fail)\s+(\S+)\s+(.+)$")
_WROTE = re.compile(r"(?i)(?:wrote|created|creado|escrito)\s+(\S+)")
_PING = re.compile(r"(?i)(\d+(?:[.,]\d+)?)\s*ms")
_REC_LINE = re.compile(r"(?im)^RECIBO:\s+\S+\s+\S+\s+.+\s*")


def parse_recibo(blob: str) -> dict:
    blob = blob or ""
    m = _REC.search(blob)
    if m:
        return {
            "ok": m.group(1).lower() == "ok",
            "machine": "linux",
            "tool": m.group(2).lower(),
            "detail": m.group(3).strip(),
        }
    m = _WROTE.search(blob)
    if m:
        path = m.group(1).rstrip(".,;")
        nombre = path.replace("\\", "/").split("/")[-1]
        detail = "Escritorio, " + nombre if "scritorio" in path.lower() else nombre
        return {
            "ok": True,
            "machine": "linux",
            "tool": "write",
            "detail": detail,
        }
    if "ping" in blob.lower() and _PING.search(blob):
        return {
            "ok": True,
            "machine": "linux",
            "tool": "ping",
            "detail": _PING.search(blob).group(0).replace(",", ".") + " a la red",
        }
    return {"ok": False, "machine": "linux", "tool": "unknown", "detail": ""}


def formatear_recibo(r: dict) -> str:
    if not r or not r.get("ok"):
        return "Sin recibo de tool."
    return r.get("detail") or r.get("tool") or "ok"


def recortar_recibo(text: str) -> str:
    return _REC_LINE.sub("", text or "").strip()
