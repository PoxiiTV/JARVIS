"""Casa Tuya en este Windows. Sin Hermes y sin LLM."""
import json
import os
import re
import threading
import unicodedata

from .config import Config

# Nombres y tipo. Los IDs van en tuya.json (no se sube al git).
APARATOS = {
    "dormitorio": {"kind": "switch", "nombre": "Luz Dormitorio"},
    "luces_salon": {"kind": "switch", "nombre": "Luces Salon"},
    "tele": {"kind": "ir", "nombre": "Tele"},
    "aire": {"kind": "ir", "nombre": "Aire acondicionado"},
}

_DEVICE_RE = (
    ("luces_salon", re.compile(
        r"(?:luces|luz|leds?)\s+(?:del\s+)?salon", re.I)),
    ("dormitorio", re.compile(
        r"(?:luz\s+)?dormitorio|habitacion|\bcuarto\b", re.I)),
    ("aire", re.compile(r"aire(?:\s+acondicionado)?", re.I)),
    ("tele", re.compile(
        r"\b(?:la\s+)?(?:tele|television|\btv\b|samsung)\b", re.I)),
)

_SALON_O_LUCES = re.compile(r"\b(?:luces|salon)\b", re.I)
_ON = re.compile(
    r"\b(?:encien\w*|encied\w*|encend\w*|prend\w*|activ\w*)\b", re.I)
_OFF = re.compile(r"\b(?:apag\w*|desactiv\w*)\b", re.I)
_PON = re.compile(r"\bpon(?:me|las|los|la|el)?\b", re.I)

_lock = threading.Lock()
_nube = None


def orden_tuya(text):
    """Si pide luces, tele o aire: dict. Si no, None."""
    t = _preparar(text)
    if not t:
        return None
    device = _dispositivo(t)
    if not device:
        return None
    if _ON.search(t):
        return {"device": device, "on": True}
    if _OFF.search(t):
        return {"device": device, "on": False}
    if _PON.search(t):
        return {"device": device, "on": True}
    return None


def _preparar(text):
    """Typos y lo que Whisper suele oír en vez de luces/enciende."""
    t = _norm(text or "")
    t = re.sub(r"\benciede\b", "enciende", t)
    t = re.sub(r"\bencende\b", "enciende", t)
    t = re.sub(r"\bensiende\b", "enciende", t)
    t = re.sub(r"\ben\s+(?:siende|ciende)\b", "enciende", t)
    t = re.sub(
        r"\b(?:lets?|les|the|net|ned|ledz|leds?)\s+(?:del\s+)?salon\b",
        "luces salon",
        t,
    )
    t = re.sub(r"\blights?\b", "luces", t)
    return t


def cumplir_tuya(text):
    """Ejecuta la orden en Tuya. None si no es de casa."""
    o = orden_tuya(text)
    if not o:
        return None
    nombre = (APARATOS.get(o["device"]) or {}).get("nombre") or o["device"]
    try:
        _enviar(o["device"], o["on"])
    except Exception as e:
        msg = str(e).strip() or "Tuya falló"
        return msg if msg.endswith(".") else msg + "."
    if o["device"] == "luces_salon":
        estado = "encendidas" if o["on"] else "apagadas"
    elif o["device"] == "aire":
        estado = "encendido" if o["on"] else "apagado"
    else:
        estado = "encendida" if o["on"] else "apagada"
    return f"{nombre} {estado}."


def _dispositivo(t):
    for key, rx in _DEVICE_RE:
        if rx.search(t):
            return key
    if _SALON_O_LUCES.search(t) and (_ON.search(t) or _OFF.search(t) or _PON.search(t)):
        return "luces_salon"
    return None


def _ir_hub():
    return str(_mapa_local().get("ir_hub") or "").strip()


def _id_de(device):
    local = ((_mapa_local().get("devices") or {}).get(device) or {})
    if local.get("id"):
        return str(local["id"])
    return ""


def _enviar(device, on):
    local = ((_mapa_local().get("devices") or {}).get(device) or {})
    kind = (APARATOS.get(device) or {}).get("kind") or "switch"
    if kind != "ir" and local.get("id") and local.get("key") and local.get("ip"):
        _lan_switch(local, on)
        return
    if not (getattr(Config, "TUYA_ACCESS_ID", "") and getattr(Config, "TUYA_ACCESS_SECRET", "")):
        raise RuntimeError("Falta la clave Tuya en Ajustes, señor")
    if kind == "ir":
        _nube_ir(device, on)
        return
    _nube_switch(device, on)


def _mapa_local():
    ruta = getattr(Config, "TUYA_FILE", "tuya.json") or "tuya.json"
    if not os.path.isabs(ruta):
        ruta = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ruta
        )
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _lan_switch(dev, on):
    import tinytuya
    d = tinytuya.OutletDevice(str(dev["id"]), str(dev["ip"]), str(dev["key"]))
    d.set_version(float(dev.get("ver") or 3.3))
    d.set_socketTimeout(2)
    if on:
        d.turn_on()
    else:
        d.turn_off()


def _cloud():
    global _nube
    import tinytuya
    with _lock:
        if _nube is not None:
            return _nube
        kwargs = {
            "apiRegion": (getattr(Config, "TUYA_REGION", None) or "eu").strip() or "eu",
            "apiKey": Config.TUYA_ACCESS_ID,
            "apiSecret": Config.TUYA_ACCESS_SECRET,
        }
        did = (getattr(Config, "TUYA_DEVICE_ID", "") or "").strip()
        if did:
            kwargs["apiDeviceID"] = did
        _nube = tinytuya.Cloud(**kwargs)
        return _nube


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _ok_nube(res, que):
    if not isinstance(res, dict):
        return
    if res.get("success") is False:
        raise RuntimeError(res.get("msg") or res.get("message") or que)
    err = res.get("Error") or res.get("Err")
    if err:
        extra = str(res.get("Payload") or "")
        extra = extra.replace("Error from Tuya Cloud:", "").strip(" '")
        raise RuntimeError(extra or str(err))


def _codigo_onoff(status):
    """Leds usan switch_led; enchufes, switch_1."""
    codes = []
    result = status.get("result") if isinstance(status, dict) else None
    if isinstance(result, list):
        codes = [x.get("code") for x in result if isinstance(x, dict)]
    for c in ("switch_led", "switch_1", "switch"):
        if c in codes:
            return c
    return "switch_1"


def _nube_switch(device, on):
    c = _cloud()
    did = _id_de(device)
    nombre = (APARATOS.get(device) or {}).get("nombre") or device
    if not did:
        raise RuntimeError(f"No encuentro {nombre} en Tuya")
    online = c.getconnectstatus(did)
    if online is False or (
        isinstance(online, dict) and online.get("result") is False
    ):
        raise RuntimeError(f"{nombre} no tiene conexión")
    st = c.getstatus(did)
    _ok_nube(st, "Tuya no respondió el estado")
    code = _codigo_onoff(st)
    res = c.sendcommand(did, {"commands": [{"code": code, "value": bool(on)}]})
    _ok_nube(res, "Tuya rechazó el interruptor")


def _nube_ir(kind, on):
    c = _cloud()
    rid = _id_de(kind)
    hub = _ir_hub()
    if not rid or not hub:
        raise RuntimeError("Falta el mando IR en tuya.json")
    if kind == "aire":
        res = c.cloudrequest(
            f"/v2.0/infrareds/{hub}/air-conditioners/{rid}/command",
            action="POST",
            post={"code": "power", "value": 1 if on else 0},
        )
        if isinstance(res, dict) and (
            res.get("success") is False or res.get("Error")
        ):
            res = c.cloudrequest(
                f"/v2.0/infrareds/{hub}/remotes/{rid}/command",
                action="POST",
                post={"category_id": 5, "key": "Power"},
            )
    else:
        res = c.cloudrequest(
            f"/v2.0/infrareds/{hub}/remotes/{rid}/command",
            action="POST",
            post={"category_id": 2, "key": "Power"},
        )
    _ok_nube(res, "Tuya no pudo mandar el mando IR")
