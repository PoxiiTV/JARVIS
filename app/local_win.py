"""Acciones reales de este Windows. Sin fingir resultados."""
import os
import re
import webbrowser

_HTTP = re.compile(r"^https?://", re.I)


def url_permitida(url: str) -> bool:
    u = (url or "").strip()
    if not u or len(u) > 2000:
        return False
    if not _HTTP.match(u):
        return False
    if re.search(r"[\s<>\"]", u):
        return False
    return True


def abrir_url(url: str) -> dict:
    if not url_permitida(url):
        return {"ok": False, "error": "URL no permitida"}
    webbrowser.open(url)
    return {"ok": True}


def captura_pantalla() -> dict:
    try:
        from PIL import ImageGrab
    except ImportError:
        return {"error": "Sin captura en este PC"}
    try:
        img = ImageGrab.grab()
    except Exception:
        return {"error": "Sin captura en este PC"}
    escritorio = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(escritorio):
        escritorio = os.path.join(os.path.expanduser("~"), "Escritorio")
    if not os.path.isdir(escritorio):
        return {"error": "No encuentro el escritorio de este PC"}
    ruta = os.path.join(escritorio, "jarvis-captura.png")
    img.save(ruta)
    return {"ok": True, "ruta": ruta}
