"""Servicios de datos del dashboard JARVIS: métricas, Docker/Portainer,
saldo DeepSeek, cronjobs, proxy, tiempo, fútbol y menú."""
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import ssl
import os
import hashlib
import secrets
import base64
import threading
import re

from .config import Config
from pathlib import Path

AVISOS_FILE = Path(Config.MEMORY_DIR) / "avisos.json"

# ---------------------------------------------------------------- helpers

def _http_json(url, headers=None, timeout=10, method="GET", data=None):
    """GET/POST JSON con urllib. Devuelve (status, dict|bytes|None)."""
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None
    except Exception as e:
        return 0, {"error": str(e)}


# ---------------------------------------------------------------- sistema

def system_metrics():
    """CPU / RAM / disco / uptime. Funciona en Windows y en Linux."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        # La raiz del disco depende del sistema: "/" en Linux, "C:\" en
        # Windows. psutil.disk_usage("/") revienta en Windows.
        raiz = os.path.abspath(os.sep)
        disk = psutil.disk_usage(raiz)
        # psutil.boot_time() es multiplataforma; /proc/uptime solo existe
        # en Linux (y ademas estaba escrito con barras invertidas).
        uptime_s = max(0.0, time.time() - psutil.boot_time())
        days = int(uptime_s // 86400)
        hours = int((uptime_s % 86400) // 3600)
        mins = int((uptime_s % 3600) // 60)
        if days:
            uptime = f"{days}d {hours}h {mins}m"
        elif hours:
            uptime = f"{hours}h {mins}m"
        else:
            uptime = f"{mins}m"
        ram_pct = round(mem.percent, 1)
        disk_pct = round(disk.percent, 1)
        return {
            "cpu": round(cpu, 1),
            "mem": ram_pct,
            "disk": disk_pct,
            "ram_used_gb": round((mem.total - mem.available) / 1e9, 1),
            "ram_total_gb": round(mem.total / 1e9, 1),
            "ram_pct": ram_pct,
            "disk_used_gb": round(disk.used / 1e9, 1),
            "disk_total_gb": round(disk.total / 1e9, 1),
            "disk_pct": disk_pct,
            "uptime": uptime,
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------- docker / portainer

def _portainer_get(path: str):
    """GET a la API de Portainer con la key (cert autofirmado ignorado)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        f"{Config.PORTAINER_URL}{path}", headers={"X-API-Key": Config.PORTAINER_KEY}
    )
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        return json.loads(r.read())


def _discover_endpoint_id():
    """Descubre el ID del endpoint Docker de Portainer (no siempre es 1)."""
    try:
        endpoints = _portainer_get("/api/endpoints")
        for ep in endpoints:
            if ep.get("Type") == 1:  # 1 = Docker local
                return ep["Id"]
        if endpoints:
            return endpoints[0]["Id"]
    except Exception:
        pass
    return None


def docker_status():
    """Contenedores: 1º socket Docker montado, 2º API de Portainer, 3º degradado."""
    # 1) Docker socket (el contenedor del dashboard lo monta)
    if os.path.exists(Config.DOCKER_SOCKET):
        try:
            import httpx
            transport = httpx.HTTPTransport(uds=Config.DOCKER_SOCKET)
            with httpx.Client(transport=transport, timeout=6) as client:
                r = client.get("http://docker/containers/json?all=1")
                if r.status_code == 200:
                    data = r.json()
                    containers = [
                        {
                            "name": (c.get("Names") or ["?"])[0].lstrip("/"),
                            "state": c.get("State", "?"),
                            "status": c.get("Status", ""),
                            "image": c.get("Image", "").split(":")[0],
                        }
                        for c in data
                    ]
                    running = sum(1 for c in containers if c["state"] == "running")
                    return {"available": True, "running": running, "total": len(containers), "containers": containers}
        except Exception as e:
            pass  # caer a Portainer
    # 2) Portainer API
    if not Config.PORTAINER_KEY:
        return {
            "available": False,
            "message": "Sin socket Docker ni API key de Portainer.",
            "containers": [],
        }
    endpoint_id = _discover_endpoint_id()
    if endpoint_id is None:
        return {
            "available": False,
            "message": "Portainer accesible pero sin endpoints Docker disponibles.",
            "containers": [],
        }
    url = f"{Config.PORTAINER_URL}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
    # Portainer por defecto tiene certificado autofirmado
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            url, headers={"X-API-Key": Config.PORTAINER_KEY}
        )
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            data = json.loads(r.read())
        containers = [
            {
                "name": (c.get("Names") or ["?"])[0].lstrip("/"),
                "state": c.get("State", "?"),
                "status": c.get("Status", ""),
                "image": c.get("Image", "").split(":")[0],
            }
            for c in data
        ]
        running = sum(1 for c in containers if c["state"] == "running")
        return {"available": True, "running": running, "total": len(containers), "containers": containers}
    except Exception as e:
        return {"available": False, "message": f"Portainer: {e}", "containers": []}


# ---------------------------------------------------------------- saldo deepseek

def deepseek_balance():
    if not Config.DEEPSEEK_API_KEY:
        return {"error": "Sin DEEPSEEK_API_KEY"}
    status, data = _http_json(
        f"{Config.DEEPSEEK_BASE_URL}/user/balance",
        headers={"Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}"},
        timeout=10,
    )
    if status == 200 and isinstance(data, dict) and data.get("balance_infos"):
        bi = data["balance_infos"][0]
        return {"balance": float(bi.get("total_balance", 0)), "currency": bi.get("currency", "USD")}
    return {"error": f"API balance HTTP {status}"}


# ---------------------------------------------------------------- cronjobs

def cron_status():
    """Lee /data/cron/jobs.json (montado RO) y resume los jobs."""
    try:
        with open(Config.CRON_JOBS_FILE) as f:
            jobs = json.load(f)
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs", [])
        out = []
        for j in jobs:
            out.append({
                "name": j.get("name", j.get("id", "?")),
                "schedule": j.get("schedule", ""),
                "enabled": j.get("enabled", False),
                "last_status": j.get("last_status", "-"),
                "last_run_at": j.get("last_run_at", None),
                "next_run_at": j.get("next_run_at", None),
            })
        ok = sum(1 for j in out if j["last_status"] == "ok")
        return {"available": True, "total": len(out), "ok": ok, "jobs": out}
    except FileNotFoundError:
        return {"available": False, "jobs": []}
    except Exception as e:
        return {"available": False, "message": str(e), "jobs": []}


# ---------------------------------------------------------------- proxy deepseek-cursor

def proxy_status():
    """Estado del proxy :9000 + URL del túnel cloudflared.
    Si el proxy no es accesible localmente (otro contenedor), se comprueba
    a través de su túnel público: si /v1/models responde 200, está VIVO."""
    tunnel = ""
    try:
        if os.path.exists(Config.TUNNEL_URL_FILE):
            tunnel = open(Config.TUNNEL_URL_FILE).read().strip()
    except Exception:
        pass
    status, _ = _http_json(f"{Config.PROXY_URL}/", timeout=5)
    up = status in (200, 404, 405)
    via = "local"
    if not up and tunnel:
        try:
            s2, _ = _http_json(f"{tunnel}/v1/models", timeout=10)
            if s2 == 200:
                up, via = True, "tunel"
        except Exception:
            pass
    return {"up": up, "status": status, "tunnel": tunnel, "via": via}


# ---------------------------------------------------------------- tiempo

def weather():
    """Tiempo actual + previsión vía Open-Meteo."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={Config.LAT}&longitude={Config.LON}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=Europe%2FMadrid&forecast_days=3"
    )
    status, data = _http_json(url, timeout=10)
    if status != 200 or not isinstance(data, dict):
        return {"error": f"Open-Meteo HTTP {status}"}
    cur = data.get("current", {})
    daily = data.get("daily", {})
    days = []
    if daily:
        for i, day in enumerate(daily.get("time", [])[:3]):
            days.append({
                "date": day,
                "code": daily["weather_code"][i],
                "tmax": daily["temperature_2m_max"][i],
                "tmin": daily["temperature_2m_min"][i],
            })
    return {
        "temp": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "wind": cur.get("wind_speed_10m"),
        "code": cur.get("weather_code"),
        "days": days,
    }


WMO = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
    3: "Nublado", 45: "Niebla", 48: "Niebla", 51: "Llovizna", 53: "Llovizna",
    55: "Llovizna", 61: "Lluvia ligera", 63: "Lluvia", 65: "Lluvia fuerte",
    66: "Lluvia helada", 67: "Lluvia helada", 71: "Nieve ligera", 73: "Nieve",
    75: "Nieve fuerte", 80: "Chubascos", 81: "Chubascos", 82: "Chubascos fuertes",
    95: "Tormenta", 96: "Tormenta con granizo", 99: "Tormenta con granizo",
}


def weather_code_text(code):
    return WMO.get(code, "Desconocido")


# ---------------------------------------------------------------- fútbol

def football():
    return {"error": "desactivado"}


# ---------------------------------------------------------------- menú

def menu():
    try:
        with open(Config.MENU_FILE) as f:
            return {"available": True, "content": f.read()}
    except Exception as e:
        return {"available": False, "message": str(e), "content": ""}


# ---------------------------------------------------------------- spotify

_pkce_pending = {}
_SPOTIFY_SCOPES = " ".join((
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
))


def _auth_path():
    p = Config.AUTH_FILE or "auth.json"
    if os.path.isabs(p):
        return p
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(raiz, p)


def _spotify_state():
    """Lee el estado OAuth de Spotify desde auth.json."""
    try:
        with open(_auth_path(), encoding="utf-8") as f:
            store = json.load(f)
        st = (store.get("providers") or {}).get("spotify") or {}
        if not st.get("access_token"):
            return None
        return st
    except Exception:
        return None


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def spotify_login_url():
    """URL de Spotify Authorize (PKCE). No usa secret."""
    cid = (Config.SPOTIFY_CLIENT_ID or "").strip()
    if not cid:
        return None, "Falta el Client ID de Spotify en Ajustes"
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(24)
    _pkce_pending[state] = verifier
    q = urllib.parse.urlencode({
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": Config.SPOTIFY_REDIRECT,
        "scope": _SPOTIFY_SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": _pkce_challenge(verifier),
        "state": state,
    })
    return f"{Config.SPOTIFY_ACCOUNTS}/authorize?{q}", None


def spotify_finish(code: str, state: str):
    """Cambia el code de Spotify por tokens y los guarda en auth.json."""
    verifier = _pkce_pending.pop(state, None)
    if not verifier:
        return {"error": "Sesión de login caducada. Dale otra vez a Conectar."}
    cid = (Config.SPOTIFY_CLIENT_ID or "").strip()
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": Config.SPOTIFY_REDIRECT,
        "client_id": cid,
        "code_verifier": verifier,
    }).encode()
    req = urllib.request.Request(
        f"{Config.SPOTIFY_ACCOUNTS}/api/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"Spotify no dio el token ({e.code})"}
    except Exception as e:
        return {"error": str(e)}
    now = time.time()
    exp = int(payload.get("expires_in", 3600))
    st = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", ""),
        "client_id": cid,
        "expires_in": exp,
        "expires_at": time.strftime(
            "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now + exp)
        ),
        "api_base_url": Config.SPOTIFY_API,
        "accounts_base_url": Config.SPOTIFY_ACCOUNTS,
    }
    path = _auth_path()
    store = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                store = json.load(f) or {}
        except Exception:
            store = {}
    store.setdefault("providers", {})["spotify"] = st
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    return {"ok": True}


def _spotify_refresh(st):
    """Refresca el access token vía grant_type=refresh_token y guarda."""
    try:
        import urllib.parse
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": st.get("refresh_token", ""),
            "client_id": st.get("client_id") or Config.SPOTIFY_CLIENT_ID,
        }).encode()
        req = urllib.request.Request(
            f"{st.get('accounts_base_url', Config.SPOTIFY_ACCOUNTS)}/api/token",
            data=body, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            payload = json.loads(r.read())
        now = time.time()
        st["access_token"] = payload["access_token"]
        st["expires_in"] = int(payload.get("expires_in", 3600))
        st["expires_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now + st["expires_in"]))
        st["obtained_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now))
        with open(_auth_path(), encoding="utf-8") as f:
            store = json.load(f)
        (store.setdefault("providers", {}))["spotify"] = st
        with open(_auth_path(), "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
        return st
    except Exception as e:
        return {"error": f"refresh: {e}"}


def _spotify_request(method, path, body=None, retry=True):
    """Llamada a la Web API de Spotify con refresh automático en 401."""
    st = _spotify_state()
    if not st:
        return {"error": "Spotify no autenticado"}
    if "expires_at" in st:
        try:
            exp = st["expires_at"].replace("Z", "+00:00")
            exp_ts = time.mktime(time.strptime(exp, "%Y-%m-%dT%H:%M:%S+00:00"))
            if time.time() > exp_ts - 60:
                st = _spotify_refresh(st)
                if "error" in st:
                    return st
        except Exception:
            pass
    api = st.get("api_base_url") or Config.SPOTIFY_API
    url = f"{api}{path}"
    headers = {"Authorization": f"Bearer {st['access_token']}"}
    # _http_json serializa el dict y añade Content-Type: pasar el body como dict
    data = body if body is not None else None
    status, resp = _http_json(url, headers=headers, timeout=12, method=method, data=data)
    if status == 401 and retry:
        st = _spotify_refresh(st)
        if "error" in st:
            return st
        headers["Authorization"] = f"Bearer {st['access_token']}"
        status, resp = _http_json(url, headers=headers, timeout=12, method=method, data=data)
    if status >= 400:
        msg = f"Spotify HTTP {status}"
        # Errores comunes de Spotify → mensajes claros en español
        try:
            detail_str = json.dumps(resp) if isinstance(resp, (dict, list)) else str(resp)
        except Exception:
            detail_str = str(resp)
        if "NO_ACTIVE_DEVICE" in detail_str:
            msg = "Sin dispositivo activo — abre Spotify en tu móvil/PC y reproduce algo"
        elif "PREMIUM_REQUIRED" in detail_str:
            msg = "Se requiere cuenta Premium para esta acción"
        elif "rate limit" in detail_str.lower() or "429" in detail_str:
            msg = "Límite de peticiones de Spotify — espera un momento"
        return {"error": msg, "detail": resp}
    if resp is None:
        return {"ok": True}
    if isinstance(resp, dict):
        return resp
    # Respuestas no-JSON (p.ej. 204 No Content de play/pause): el body puede
    # ser bytes; convertirlo a texto para que el resultado sea serializable.
    if isinstance(resp, bytes):
        return {"ok": True, "raw": resp.decode("utf-8", "replace")}
    return {"ok": True, "raw": resp}


def spotify_status():
    """Reproducción actual + dispositivos Spotify Connect."""
    st = _spotify_state()
    if not st:
        return {
            "available": False,
            "message": "No autenticado",
            "client_id": bool((Config.SPOTIFY_CLIENT_ID or "").strip()),
        }
    out = {"available": True}
    now = _spotify_request("GET", "/me/player/currently-playing?market=ES")
    if "error" in now:
        out["playing"] = None
        out["error"] = now["error"]
    elif now.get("empty") or not now.get("item"):
        out["playing"] = None
    else:
        item = now.get("item") or {}
        out["playing"] = {
            "name": item.get("name"),
            "artists": ", ".join(a.get("name", "") for a in (item.get("artists") or [])),
            "album": (item.get("album") or {}).get("name"),
            "progress_ms": now.get("progress_ms"),
            "duration_ms": item.get("duration_ms"),
            "is_playing": now.get("is_playing"),
            "uri": item.get("uri"),
        }
    devs = _spotify_request("GET", "/me/player/devices")
    if "error" in devs:
        out["devices"] = []
    else:
        out["devices"] = [
            {"id": d.get("id"), "name": d.get("name"), "type": d.get("type"),
             "active": bool(d.get("is_active"))}
            for d in (devs.get("devices") or [])
        ]
    return out


def spotify_action(action, query=None, device_id=None, device=None):
    """Acciones: play (opcional query), pause, next, prev, volume(N), transfer(id), device (nombre)."""
    st = _spotify_state()
    if not st:
        return {"error": "Spotify no autenticado"}
    # Resolver dispositivo por nombre ("en el PC", "en el móvil", "en la tele"...)
    if device and not device_id:
        devs = _spotify_request("GET", "/me/player/devices")
        if isinstance(devs, dict) and "error" not in devs:
            items = devs.get("devices") or []
            dl = device.strip().lower()
            match = None
            for d in items:
                nm = (d.get("name") or "").lower()
                if nm == dl or dl in nm or nm in dl:
                    match = d
                    break
            if match:
                device_id = match.get("id")
            else:
                disponibles = ", ".join((d.get("name") or "?") for d in items) or "ninguno"
                return {"error": f"No veo ningún dispositivo «{device}». Disponibles: {disponibles}"}
    dev = f"?device_id={device_id}" if device_id else ""
    a = (action or "").lower()
    if a == "play":
        body = None
        if query:
            q = urllib.parse.quote(query)
            s = _spotify_request("GET", f"/search?q={q}&type=track&limit=1&market=ES")
            if "error" in s:
                return s
            tracks = (s.get("tracks") or {}).get("items") or []
            if not tracks:
                return {"error": f"No encontré «{query}»"}
            body = {"uris": [tracks[0]["uri"]]}
        resp = _spotify_request("PUT", f"/me/player/play{dev}", body=body)
        # Fallback: si no hay dispositivo activo, transferimos la reproducción
        # al primer dispositivo visible (móvil/PC) y reintentamos. Así el usuario
        # no tiene que abrir Spotify y darle a play manualmente.
        if isinstance(resp, dict) and "error" in resp and "dispositivo activo" in str(resp.get("error")):
            devs = _spotify_request("GET", "/me/player/devices")
            if isinstance(devs, dict) and "error" not in devs:
                devices = [d for d in (devs.get("devices") or []) if d.get("id")]
                if devices:
                    did = device_id or devices[0]["id"]
                    _spotify_request("PUT", "/me/player", body={"device_ids": [did]})
                    return _spotify_request(
                        "PUT", f"/me/player/play?device_id={did}", body=body
                    )
        return resp
    if a == "pause":
        return _spotify_request("PUT", f"/me/player/pause{dev}")
    if a == "next":
        return _spotify_request("POST", f"/me/player/next{dev}")
    if a == "prev":
        return _spotify_request("POST", f"/me/player/previous{dev}")
    if a == "volume":
        try:
            v = int(query)
        except Exception:
            return {"error": "volumen debe ser 0-100"}
        return _spotify_request("PUT", f"/me/player/volume?volume_percent={v}")
    if a == "transfer":
        if not device_id:
            return {"error": "falta device_id"}
        return _spotify_request("PUT", "/me/player", body={"device_ids": [device_id], "play": True})
    return {"error": f"acción desconocida: {action}"}


_SPOTIFY_DEV = re.compile(
    r"\s+en\s+(?:el\s+|la\s+)?(pc|ordenador|port[aá]til|m[oó]vil|tel[eé]fono|tele|tv|coche)\s*$",
    re.I,
)


def orden_spotify(text):
    """Si el señor pide música, dict para el widget. Si no, None."""
    t = (text or "").strip()
    if not t:
        return None
    device = None
    mdev = _SPOTIFY_DEV.search(t)
    if mdev:
        device = mdev.group(1).lower()
        t = t[:mdev.start()].strip()
    low = t.lower()

    def _dev(action, query=None):
        o = {"action": action}
        if query:
            o["query"] = query
        if device:
            o["device"] = device
        return o

    if re.search(r"qu[eé]\s+(?:suena|est[aá]\s+sonando)", low):
        return _dev("status")
    if re.search(r"\b(pausa|pause|para(?:\s+la)?\s+m[uú]sica|para\s+spotify)\b", low):
        return _dev("pause")
    if re.search(r"\b(salta|siguiente(?:\s+canci[oó]n)?)\b", low) and not re.search(r"\bpon", low):
        return _dev("next")
    if re.search(r"\b(anterior|previa)\b", low):
        return _dev("prev")
    if re.search(r"\b(sigue|reanuda|contin[uú]a)\b", low) and re.search(r"m[uú]sica|spotify|canci", low):
        return _dev("play")
    mv = re.search(r"\bvolumen\s+(\d{1,3})\b", low)
    if mv:
        return _dev("volume", mv.group(1))
    m = re.search(
        r"\b(?:oye\s+)?(?:ponme|reproduce|play|echa|pon)\s+(?:la\s+|el\s+)?(?:canci[oó]n\s+|tema\s+)?(.+)$",
        t,
        re.I,
    )
    if m:
        q = m.group(1).strip(" .¡!?")
        q = re.sub(r"^(?:la|el|una?)\s+", "", q, flags=re.I)
        if re.fullmatch(r"m[uú]sica", q, re.I):
            q = ""
        return _dev("play", q or None)
    return None


def cumplir_spotify(text):
    """Ejecuta la orden en el widget de este PC. None si no es música."""
    o = orden_spotify(text)
    if not o:
        return None
    action = o.get("action")
    query = o.get("query")
    device = o.get("device")
    if action == "status":
        st = spotify_status()
        if not st.get("available"):
            return "Spotify no está conectado en este PC. Conéctalo en el widget, señor."
        p = st.get("playing")
        if not p:
            return "Ahora mismo no suena nada, señor."
        verbo = "Suena" if p.get("is_playing") else "Está en pausa"
        name = p.get("name") or "una canción"
        artists = p.get("artists") or ""
        if artists:
            return f"{verbo} {name}, de {artists}."
        return f"{verbo} {name}."
    res = spotify_action(action, query, device=device)
    with _service_lock:
        _service_cache.pop("spotify", None)
    if isinstance(res, dict) and res.get("error"):
        err = str(res["error"])
        if "no autenticado" in err.lower():
            return "Spotify no está conectado en este PC. Conéctalo en el widget, señor."
        return err if err.endswith(".") else err + "."
    if action == "pause":
        return "Pausa, señor."
    if action == "next":
        return "Siguiente."
    if action == "prev":
        return "Anterior."
    if action == "volume":
        return f"Volumen {query}."
    if action == "play" and query:
        return f"Pongo {query}, señor."
    return "Hecho, señor."


# ---------------------------------------------------------------- estado global

# Caché POR SERVICIO: cada bloque (tiempo, fútbol, saldo, docker...) se
# consulta como mucho cada STATUS_TTL segundos y se reutiliza. El panel
# visual (full_status) y las consultas del chat comparten la MISMA caché.
# El chat YA NO llama a todo: usa smart_context() y consulta solo los
# servicios que la pregunta menciona.
_service_cache = {}
_service_lock = threading.Lock()


def _cached_service(name, fn):
    now = time.time()
    with _service_lock:
        c = _service_cache.get(name)
        if c is not None and now - c[0] < Config.STATUS_TTL:
            return c[1]
    try:
        val = fn()
    except Exception as e:
        val = {"error": str(e)}
    with _service_lock:
        _service_cache[name] = (time.time(), val)
    return val


# Reglas de intención: patrones (lowercase) por tema. El chat solo consulta
# los temas que aparecen en la pregunta del usuario.
_THEME_RULES = [
    ("weather", r"tiempo|clima|lluvia|llover|lluvioso|temperatura|grados|soleado|nublado|nubes|viento|humedad|prevision|previsión|meteo|calor|frio|frío"),
    ("balance", r"saldo|cuanto tengo|cuánto tengo|dinero|coste|costo|gasto|credito|crédito|dolares|dólares|balance|presupuesto|cuenta"),
    ("cron", r"cron|cronjob|tareas programadas|automatizacion|automatización|jobs"),
    ("proxy", r"proxy|cursor|tunel|túnel"),
    ("menu", r"menu|menú|comer|almuerzo|cenar|cena|desayuno|comida de hoy|que comemos|qué comemos"),
    ("system", r"cpu|ram|disco|procesador|uptime|encendido|reiniciar|rendimiento|servidor"),
]


def smart_context(text: str, extra=None) -> dict:
    """Contexto para el chat: SOLO los servicios que la pregunta menciona.

    Si la pregunta actual no menciona ningún tema (p.ej. "¿y mañana?"),
    se usan las preguntas recientes del usuario (extra) para resolver la
    referencia: si la anterior era del tiempo, se inyecta el tiempo.
    Si no hay ningún tema, devuelve {} — el chat responde sin llamadas.
    """
    low = (text or "").lower()
    temas = [k for k, p in _THEME_RULES if __import__("re").search(p, low)]
    if not temas and extra:
        # Referencias anafóricas: usar el tema de la última pregunta temática
        for prev in reversed(extra):
            low2 = (prev or "").lower()
            temas = [k for k, p in _THEME_RULES if __import__("re").search(p, low2)]
            if temas:
                break
    ctx = {}
    fn_map = {
        "weather": weather, "balance": deepseek_balance,
        "cron": cron_status, "proxy": proxy_status,
        "menu": menu, "system": system_metrics,
    }
    for key in temas:
        ctx[key] = _cached_service(key, fn_map[key])
    return ctx


def leer_avisos():
    """Hasta 10 avisos cortos para el HUD. Fuente: memoria/avisos.json."""
    try:
        raw = Path(AVISOS_FILE).read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        out = []
        for a in data[-10:]:
            if not isinstance(a, dict):
                continue
            texto = str(a.get("texto") or "").strip()
            if not texto:
                continue
            out.append({
                "id": str(a.get("id") or ""),
                "texto": texto[:200],
                "t": a.get("t") or 0,
            })
        return out
    except (OSError, ValueError, TypeError):
        return []


def escribir_aviso(texto: str) -> dict:
    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "error": "falta el texto"}
    avisos = leer_avisos()
    item = {
        "id": secrets.token_hex(8),
        "texto": texto[:200],
        "t": int(time.time()),
    }
    avisos.append(item)
    avisos = avisos[-10:]
    path = Path(AVISOS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(avisos, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "aviso": item}


def full_status():
    """Estado completo para el PANEL visual (polling). Usa la misma caché
    por servicio, así que no martillea las APIs externas."""
    return {
        "ts": int(time.time()),
        "system": _cached_service("system", system_metrics),
        "balance": _cached_service("balance", deepseek_balance),
        "cron": _cached_service("cron", cron_status),
        "proxy": _cached_service("proxy", proxy_status),
        "dashboard_url": Config.PUBLIC_URL,   # URL pública del dashboard
        "weather": _cached_service("weather", weather),
        "menu": _cached_service("menu", menu),
        "spotify": _cached_service("spotify", spotify_status),
        "avisos": leer_avisos(),
    }
