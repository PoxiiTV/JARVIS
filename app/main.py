"""Dashboard JARVIS — servicio FastAPI.

Endpoints:
  POST /api/login      {user, password} → cookie de sesión firmada
  POST /api/logout
  GET  /api/status     estado global (sistema, saldo, tiempo, menú, Hermes)
  POST /api/chat       {text} → cerebro (Auto: DeepSeek o Hermes)
  POST /api/tts        {text} → audio (Fish → Álvaro → Google)
  POST /api/stt        multipart audio → transcripción (Whisper)
  WS   /api/wake       PCM 16 kHz → Yarvis local (Vosk) + orden (Whisper)
  POST /api/vision     multipart imagen → descripción (OpenRouter)
  GET  /api/ping       heartbeat
"""
import base64
import hashlib
import hmac
import json
import os
import time
import asyncio
import collections
import threading
import queue

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, JSONResponse, FileResponse, RedirectResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from .config import Config
from . import services
from . import voice
from . import brain

app = FastAPI(title="JARVIS Dashboard", version="1.0.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
SESSION_TTL = 60 * 60 * 12  # 12 h


@app.on_event("startup")
async def _voice_warmup():
    """Calienta los TTS del PC en segundo plano (primera petición más rápida)."""
    threading.Thread(target=voice.warmup, daemon=True).start()

# ---------------------------------------------------------------- rate limit login
# Por IP (x-forwarded-for que manda cloudflared): 5 fallos / 15 min → 429
_login_failures = collections.defaultdict(list)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _check_rate_limit(request: Request):
    ip = _client_ip(request)
    now = time.time()
    _login_failures[ip] = [t for t in _login_failures[ip] if now - t < Config.LOGIN_WINDOW]
    if len(_login_failures[ip]) >= Config.LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Espera 15 minutos.")
    return ip


# ---------------------------------------------------------------- auth helpers

def _sign(payload: str) -> str:
    return hmac.new(Config.SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _make_token(user: str) -> str:
    exp = int(time.time()) + SESSION_TTL
    payload = f"{user}|{exp}"
    return f"{payload}|{_sign(payload)}"


def _check_token(token: str):
    try:
        payload, sig = token.rsplit("|", 1)
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        user, exp = payload.rsplit("|", 1)
        if int(exp) < time.time():
            return None
        return user
    except Exception:
        return None


def _get_user(request: Request):
    token = request.cookies.get("jarvis_session", "")
    return _check_token(token)


def _require_user(request: Request):
    # Modo kiosco (app de escritorio): sin login. Solo se permite si la
    # peticion viene de la propia maquina — si alguien alcanzase el puerto
    # desde la red, sigue necesitando sesion.
    # Ojo: se mira request.client (IP real del socket), NO _client_ip(), que
    # hace caso a x-forwarded-for y es falsificable por quien haga la peticion.
    if Config.KIOSK:
        peer = request.client.host if request.client else ""
        if peer in ("127.0.0.1", "::1"):
            return "local"
    user = _get_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    return user


# ---------------------------------------------------------------- login

@app.post("/api/login")
async def login(request: Request):
    ip = _check_rate_limit(request)
    try:
        body = await request.json()
    except Exception:
        # Body no-JSON: cuenta como intento fallido (si no, es un hueco para
        # sondear el endpoint sin gastar el limite de intentos).
        _login_failures[ip].append(time.time())
        raise HTTPException(status_code=400, detail="Petición inválida")
    if not isinstance(body, dict):
        _login_failures[ip].append(time.time())
        raise HTTPException(status_code=400, detail="Petición inválida")
    user = body.get("user", "")
    password = body.get("password", "")
    if user != Config.USER or password != Config.PASSWORD:
        _login_failures[ip].append(time.time())
        await asyncio.sleep(0.5)  # frenar fuerza bruta
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    _login_failures.pop(ip, None)
    resp = JSONResponse({"ok": True, "user": user})
    resp.set_cookie(
        "jarvis_session", _make_token(user),
        httponly=True, samesite="strict", secure=Config.COOKIE_SECURE,
        max_age=SESSION_TTL,
    )
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("jarvis_session")
    brain.reset_history()
    return resp


@app.get("/api/ping")
async def ping():
    # kiosk: el frontend lo usa para esconder el boton de cerrar sesion
    # (en la app de escritorio no hay sesion que cerrar).
    # escritorio: lo pone Electron; habilita "repetir configuracion inicial".
    return {
        "pong": int(time.time()),
        "kiosk": Config.KIOSK,
        "escritorio": bool(os.environ.get("JARVIS_MARCADOR_CONFIG")),
    }


@app.get("/api/log")
async def api_log(request: Request):
    """Últimas líneas del log del servidor (tracebacks de backend que no se
    ven en la consola del navegador). Con sesión (mismo auth que /api/status).
    """
    _require_user(request)
    lines = []
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard.log")
        if not os.path.exists(log_path):
            return {"log": "", "error": "dashboard.log no existe"}
        with open(log_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 60000))
            data = f.read().decode("utf-8", "replace")
        lines = data.splitlines()[-150:]
    except Exception as e:
        return {"log": "", "error": str(e)}
    return {"log": "\n".join(lines)}


# ---------------------------------------------------------------- ajustes (claves)

# Claves que se pueden tocar desde el panel. El resto del .env (rutas,
# puertos...) no se expone: son cosas de instalacion, no de usuario.
AJUSTES_EDITABLES = {
    "DEEPSEEK_API_KEY": {"etiqueta": "Clave cerebro", "secreto": True},
    "DEEPSEEK_BASE_URL": {"etiqueta": "Servidor cerebro", "secreto": False},
    "DEEPSEEK_MODEL": {"etiqueta": "Modelo", "secreto": False},
    "HERMES_URL": {"etiqueta": "URL Hermes", "secreto": False},
    "HERMES_KEY": {"etiqueta": "Clave Hermes", "secreto": True},
    "HERMES_FALLBACK": {"etiqueta": "OpenRouter si Hermes apagado (0/1)", "secreto": False},
    "CEREBRO": {"etiqueta": "Cerebro", "secreto": False},
    "PERSONALIDAD": {"etiqueta": "Personalidad", "secreto": False},
    "SPOTIFY_CLIENT_ID": {"etiqueta": "Spotify Client ID", "secreto": False},
    "TUYA_ACCESS_ID": {"etiqueta": "Tuya Access ID", "secreto": True},
    "TUYA_ACCESS_SECRET": {"etiqueta": "Tuya Access Secret", "secreto": True},
    "TUYA_REGION": {"etiqueta": "Tuya región (eu/us/cn)", "secreto": False},
    "TUYA_DEVICE_ID": {"etiqueta": "Tuya Device ID (cualquiera)", "secreto": False},
    "OPENROUTER_API_KEY": {"etiqueta": "Clave vision", "secreto": True},
    "FISH_API_KEY": {"etiqueta": "Clave voz", "secreto": True},
    "FISH_VOICE_ID": {"etiqueta": "Id de voz", "secreto": False},
    "FISH_SPEED": {"etiqueta": "Velocidad (0.5-2)", "secreto": False},
    "FISH_VOLUME": {"etiqueta": "Volumen voz (dB)", "secreto": False},
    "FISH_EMOTION": {"etiqueta": "Emocion", "secreto": False},
    "JARVIS_WHISPER_MODEL": {"etiqueta": "Oído (Whisper)", "secreto": False},
    "JARVIS_LAT": {"etiqueta": "Latitud", "secreto": False},
    "JARVIS_LON": {"etiqueta": "Longitud", "secreto": False},
}


def _ruta_env() -> str:
    """.env que manda. JARVIS_ENV_FILE lo fija Electron (carpeta del usuario,
    porque dentro de Program Files no se puede escribir sin ser admin)."""
    return os.environ.get("JARVIS_ENV_FILE") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def _leer_env_bruto() -> dict:
    vals = {}
    ruta = _ruta_env()
    if not os.path.exists(ruta):
        return vals
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            t = linea.strip()
            if not t or t.startswith("#") or "=" not in t:
                continue
            k, v = t.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def _tapar(valor: str) -> str:
    """'sk-or-v1-abc...xyz' → para mostrar sin filtrar la clave entera."""
    if not valor:
        return ""
    if len(valor) <= 12:
        return "•" * len(valor)
    return f"{valor[:8]}…{valor[-4:]}"


@app.get("/api/ajustes")
async def ajustes_get(request: Request):
    """Valores actuales. Las claves van tapadas: nunca se devuelven enteras."""
    _require_user(request)
    actuales = _leer_env_bruto()
    alias = {"JARVIS_LAT": "LAT", "JARVIS_LON": "LON", "JARVIS_WHISPER_MODEL": "WHISPER_MODEL"}
    salida = {}
    for clave, meta in AJUSTES_EDITABLES.items():
        crudo = actuales.get(clave, "")
        if crudo:
            valor = crudo
            puesto = True
        elif meta["secreto"]:
            valor = ""
            puesto = False
        else:
            # Si no esta en el .env, mostrar el valor que ya usa la app
            # (si no, velocidad 1.0 sale como "sin configurar" y parece bloqueada).
            attr = alias.get(clave, clave)
            fallback = getattr(Config, attr, "")
            valor = "" if fallback in (None, "") else str(fallback)
            puesto = bool(valor)
        salida[clave] = {
            "etiqueta": meta["etiqueta"],
            "secreto": meta["secreto"],
            "puesto": puesto,
            "valor": _tapar(valor) if meta["secreto"] else valor,
        }
    from .personalidad import opciones
    return {"ajustes": salida, "archivo": _ruta_env(), "personalidades": opciones()}


@app.post("/api/ajustes")
async def ajustes_post(request: Request):
    """Guarda claves en el .env, conservando comentarios y orden.

    Un valor vacio significa "no lo toques" (el panel muestra las claves
    tapadas, asi que un campo en blanco es "lo dejo como esta", no "borralo").
    Para borrar de verdad se manda la cadena "-".
    """
    _require_user(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Petición inválida")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Petición inválida")

    cambios = {}
    for clave, valor in body.items():
        if clave not in AJUSTES_EDITABLES:
            continue  # whitelist: no se deja escribir cualquier variable
        valor = str(valor).strip()
        if not valor:
            continue
        # Un salto de linea permitiria colar variables extra en el archivo.
        if "\n" in valor or "\r" in valor:
            raise HTTPException(status_code=400, detail=f"Valor inválido en {clave}")
        if clave == "CEREBRO":
            valor = valor.lower()
            if valor not in ("auto", "hermes", "deepseek"):
                valor = "auto"
        if clave == "PERSONALIDAD":
            from .personalidad import slug_activo
            valor = slug_activo(valor) or "jarvis"
        if clave == "FISH_VOLUME":
            try:
                n = float(valor.replace(",", "."))
            except ValueError:
                continue
            valor = str(max(-20.0, min(20.0, n)))
        if clave == "JARVIS_WHISPER_MODEL":
            from .config import _whisper_modelo
            valor = _whisper_modelo(valor)
        cambios[clave] = "" if valor == "-" else valor

    if not cambios:
        return {"ok": True, "cambios": 0}

    ruta = _ruta_env()
    lineas = []
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            lineas = f.read().splitlines()

    # Reescribir en su sitio las que ya existen (se respetan comentarios)
    pendientes = dict(cambios)
    for i, linea in enumerate(lineas):
        t = linea.strip()
        if not t or t.startswith("#") or "=" not in t:
            continue
        k = t.split("=", 1)[0].strip()
        if k in pendientes:
            lineas[i] = f"{k}={pendientes.pop(k)}"
    # Y anadir al final las que no estaban
    if pendientes:
        lineas.append("")
        lineas.append("# --- Anadido desde el panel de ajustes ---")
        for k, v in pendientes.items():
            lineas.append(f"{k}={v}")

    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    os.replace(tmp, ruta)  # atomico: si falla, no deja el .env a medias

    # Aplicar en caliente (evita reiniciar la app para que valga la clave nueva)
    for k, v in cambios.items():
        os.environ[k] = v
    Config.DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", Config.DEEPSEEK_API_KEY)
    Config.DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", Config.DEEPSEEK_BASE_URL)
    Config.DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", Config.DEEPSEEK_MODEL)
    Config.HERMES_ENABLED = os.environ.get("HERMES_ENABLED", "1") == "1"
    Config.HERMES_URL = os.environ.get("HERMES_URL", Config.HERMES_URL)
    Config.HERMES_KEY = os.environ.get("HERMES_KEY", Config.HERMES_KEY)
    Config.HERMES_MODEL = os.environ.get("HERMES_MODEL", Config.HERMES_MODEL)
    Config.HERMES_FALLBACK = os.environ.get("HERMES_FALLBACK", "0") == "1"
    _c = (os.environ.get("CEREBRO") or "auto").strip().lower()
    Config.CEREBRO = _c if _c in ("auto", "hermes", "deepseek") else "auto"
    Config.SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", Config.SPOTIFY_CLIENT_ID)
    Config.TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID", Config.TUYA_ACCESS_ID)
    Config.TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET", Config.TUYA_ACCESS_SECRET)
    Config.TUYA_REGION = (os.environ.get("TUYA_REGION") or Config.TUYA_REGION or "eu").strip() or "eu"
    Config.TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID", Config.TUYA_DEVICE_ID)
    try:
        from . import tuya as _tuya
        _tuya._nube = None
    except Exception:
        pass
    Config.OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", Config.OPENROUTER_API_KEY)
    Config.FISH_API_KEY = os.environ.get("FISH_API_KEY", Config.FISH_API_KEY)
    Config.FISH_VOICE_ID = os.environ.get("FISH_VOICE_ID", Config.FISH_VOICE_ID)
    try:
        Config.FISH_SPEED = float(os.environ.get("FISH_SPEED", Config.FISH_SPEED))
    except ValueError:
        pass  # valor no numerico: se deja el anterior
    try:
        Config.FISH_VOLUME = float(os.environ.get("FISH_VOLUME", Config.FISH_VOLUME))
    except (TypeError, ValueError):
        pass
    Config.FISH_EMOTION = os.environ.get("FISH_EMOTION", Config.FISH_EMOTION)
    if Config.FISH_EMOTION in ("-", "none"):
        Config.FISH_EMOTION = ""
    from .personalidad import slug_activo
    Config.PERSONALIDAD = slug_activo(os.environ.get("PERSONALIDAD", Config.PERSONALIDAD)) or "jarvis"
    Config.LAT = os.environ.get("JARVIS_LAT", Config.LAT)
    Config.LON = os.environ.get("JARVIS_LON", Config.LON)
    from .config import _whisper_modelo
    Config.WHISPER_MODEL = _whisper_modelo(
        os.environ.get("JARVIS_WHISPER_MODEL", Config.WHISPER_MODEL)
    )

    return {
        "ok": True,
        "cambios": len(cambios),
        "reinicio_oido": "JARVIS_WHISPER_MODEL" in cambios,
    }


@app.post("/api/ajustes/repetir-tutorial")
async def ajustes_repetir_tutorial(request: Request):
    """Borra el marcador de "ya configurado" para que el tutorial vuelva a
    salir al reabrir la app. Solo aplica a la app de escritorio."""
    _require_user(request)
    marcador = os.environ.get("JARVIS_MARCADOR_CONFIG")
    if not marcador:
        return {"ok": False, "error": "Solo disponible en la app de escritorio"}
    try:
        if os.path.exists(marcador):
            os.remove(marcador)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/ajustes/probar")
async def ajustes_probar(request: Request):
    """Comprueba que la clave del cerebro responde de verdad."""
    _require_user(request)
    if not Config.DEEPSEEK_API_KEY:
        return {"ok": False, "error": "Sin clave configurada"}
    try:
        r = await run_in_threadpool(brain.chat, "Responde solo: ok")
        if r.get("error"):
            return {"ok": False, "error": r["error"]}
        return {"ok": True, "respuesta": (r.get("reply") or "")[:60],
                "modelo": Config.DEEPSEEK_MODEL}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- estado

@app.get("/api/status")
async def status(request: Request):
    _require_user(request)
    # full_status() hace llamadas HTTP síncronas (saldo, Portainer, clima...):
    # fuera del event loop para que /api/ping nunca se bloquee (watchdog).
    data = await run_in_threadpool(services.full_status)
    data.update(brain.estado_cerebro())
    return data


@app.get("/api/briefing")
async def briefing(request: Request):
    _require_user(request)
    if not getattr(Config, "BRIEFING", True):
        return {"text": "", "enabled": False}
    from .briefing import texto_briefing
    st = await run_in_threadpool(services.full_status)
    st.update(brain.estado_cerebro())
    hora = time.localtime().tm_hour
    return {"text": texto_briefing(st, hora), "enabled": True}


# ---------------------------------------------------------------- cerebro

@app.post("/api/chat")
async def chat(request: Request):
    _require_user(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text vacío")
    ctx = None
    try:
        # Contexto SOLO con los servicios que la pregunta menciona (tiempo,
        # fútbol, saldo...). Las últimas preguntas del usuario se pasan para
        # resolver referencias ("¿y mañana?" tras hablar del tiempo).
        recent = [c for r, c, _ in brain._history if r == "user"][-2:]
        ctx = await run_in_threadpool(services.smart_context, text, recent)
    except Exception:
        pass
    # brain.chat() es una llamada LLM síncrona (puede tardar 10-30s):
    # en threadpool para no bloquear el event loop ni el /api/ping.
    return await run_in_threadpool(brain.chat, text, ctx)


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """Igual que /api/chat pero va soltando estado y texto a la consola."""
    _require_user(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text vacío")
    q = queue.Queue()

    def _on_fragment(acc):
        q.put({"t": "text", "reply": acc})

    def _on_progress(info):
        from . import hermes_client as hc
        q.put({"t": "status", "msg": hc.texto_progreso(info)})

    def worker():
        try:
            q.put({"t": "status", "msg": "Preparando…"})
            ctx = None
            try:
                recent = [c for r, c, _ in brain._history if r == "user"][-2:]
                ctx = services.smart_context(text, recent)
            except Exception:
                pass
            q.put({"t": "status", "msg": brain.etiqueta_status_stream(text)})
            r = brain.chat_stream(
                text, ctx, on_fragment=_on_fragment, on_progress=_on_progress,
                voice_mode=bool(body.get("voice")),
            )
            if r.get("recibo"):
                q.put({"t": "receipt", **r["recibo"]})
            q.put({
                "t": "done",
                "reply": r.get("reply") or "",
                "error": r.get("error"),
            })
        except Exception as e:
            q.put({"t": "done", "error": str(e)})
        q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            if item is None:
                break
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------------------------------------------------------------- voz

@app.post("/api/tts")
async def tts(request: Request):
    _require_user(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text vacío")
    data, ctype, source = await run_in_threadpool(voice.tts, text)
    if not data:
        raise HTTPException(status_code=500, detail="No se pudo generar voz")
    resp = Response(content=data, media_type=ctype)
    resp.headers["X-TTS-Source"] = source
    return resp


@app.post("/api/stt")
async def stt(request: Request):
    _require_user(request)
    form = await request.form()
    audio = form.get("audio")
    if audio is None:
        raise HTTPException(status_code=400, detail="falta audio")
    raw = await audio.read()
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < 100:
        return {"text": ""}
    if len(raw) > 5_000_000:
        raise HTTPException(status_code=400, detail="audio demasiado grande")
    return await run_in_threadpool(voice.stt, raw)


@app.post("/api/voice-chat")
async def voice_chat(request: Request):
    """Pipeline completo de voz en UNA llamada: audio → STT → LLM → TTS → audio.

    Devuelve JSON {text, reply, audio_b64, ctype, source, cost_usd, timings}.
    El TTS de las frases se solapa con la generación del LLM (más rápido).
    """
    _require_user(request)
    form = await request.form()
    audio = form.get("audio")
    if audio is None:
        raise HTTPException(status_code=400, detail="falta audio")
    raw = await audio.read()
    # El contexto se resuelve DENTRO de voice_chat, tras transcribir: solo los
    # servicios que la pregunta de voz mencione (smart_context).
    return await run_in_threadpool(voice.voice_chat, raw, None)


@app.websocket("/api/wake")
async def wake_ws(ws: WebSocket):
    """Oído local: Vosk detecta Yarvis. Whisper solo transcribe la orden."""
    peer = ws.client.host if ws.client else ""
    ok = Config.KIOSK and peer in ("127.0.0.1", "::1")
    if not ok:
        ok = bool(_check_token(ws.cookies.get("jarvis_session", "")))
    if not ok:
        await ws.close(code=4401)
        return
    await ws.accept()
    await ws.send_json({"event": "loading", "text": "Preparando oído para Yarvis…"})

    def preparar():
        from . import wake as wk
        wk.asegurar_modelo()
        return wk.SesionWake()

    try:
        ses = await run_in_threadpool(preparar)
    except Exception as e:
        await ws.send_json({"event": "error", "text": str(e)})
        await ws.close()
        return
    await ws.send_json({"event": "ready"})

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            texto = msg.get("text")
            if texto:
                try:
                    d = json.loads(texto)
                except Exception:
                    continue
                ses.pausado = bool(d.get("pause"))
                continue
            data = msg.get("bytes")
            if not data or len(data) > 256_000:
                continue
            dt = (len(data) / 2) / 16000.0
            ev = await run_in_threadpool(ses.feed, data, dt)
            if ev:
                await ws.send_json(ev)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass


# ---------------------------------------------------------------- visión

@app.post("/api/vision")
async def vision(request: Request):
    _require_user(request)
    form = await request.form()
    img = form.get("image")
    question = form.get("question") or "Describe la escena"
    if img is None:
        raise HTTPException(status_code=400, detail="falta imagen")
    raw = await img.read()
    mime = img.content_type or "image/jpeg"
    return await run_in_threadpool(brain.vision, raw, mime, question)


# ---------------------------------------------------------------- spotify

@app.get("/api/spotify")
async def spotify_get(request: Request):
    _require_user(request)
    return await run_in_threadpool(services.spotify_status)


@app.get("/api/spotify/login")
async def spotify_login(request: Request):
    _require_user(request)
    url, err = services.spotify_login_url()
    if err:
        raise HTTPException(status_code=400, detail=err)
    return RedirectResponse(url, status_code=302)


@app.get("/api/spotify/callback")
async def spotify_callback(request: Request):
    """Vuelta de Spotify. En kiosco viene de localhost; no pide cookie extra."""
    if Config.KIOSK:
        peer = request.client.host if request.client else ""
        if peer not in ("127.0.0.1", "::1"):
            raise HTTPException(status_code=401, detail="No autorizado")
    else:
        _require_user(request)
    err = request.query_params.get("error")
    if err:
        return RedirectResponse("/?spotify=error", status_code=302)
    code = request.query_params.get("code") or ""
    state = request.query_params.get("state") or ""
    out = services.spotify_finish(code, state)
    if out.get("error"):
        return RedirectResponse("/?spotify=error", status_code=302)
    return RedirectResponse("/?spotify=ok", status_code=302)


@app.post("/api/spotify")
async def spotify_post(request: Request):
    _require_user(request)
    body = await request.json()
    action = (body.get("action") or "").strip()
    query = (body.get("query") or "").strip() or None
    device_id = (body.get("device_id") or "").strip() or None
    return await run_in_threadpool(services.spotify_action, action, query, device_id)


# ---------------------------------------------------------------- estudio de voz
# El Estudio de Voz (generar audio con CosyVoice 3 / F5 / Álvaro y editar la
# referencia) se sirve en /estudio y sus APIs hacen de PROXY al PC del usuario
# (IP del PC TTS en la LAN: puertos 5004 / 5003). Así funciona desde cualquier
# sitio a través de la URL pública del dashboard, con la misma sesión.

def _pc_call(url: str, payload: dict, timeout: int = 180):
    """POST JSON al PC (servidor TTS). Devuelve (bytes, content_type)."""
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.headers.get("Content-Type", "audio/wav")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise HTTPException(status_code=502,
                            detail=f"El servidor TTS devolvió {e.code}: {detail}")
    except Exception as e:
        raise HTTPException(status_code=502,
                            detail=f"No se pudo conectar con el servidor TTS: {e}")


def _pc_get_json(url: str, timeout: int = 15):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"PC HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con el PC: {e}")


def _pc_post_json(url: str, payload: dict, timeout: int = 15):
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"PC HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con el PC: {e}")


def _edge_tts(text: str, speed: float) -> bytes:
    import asyncio
    import io
    import edge_tts

    async def _gen():
        rate = f"{(speed - 1.0) * 100:+.0f}%" if abs(speed - 1.0) > 0.01 else "+0%"
        c = edge_tts.Communicate(text, "es-ES-AlvaroNeural", rate=rate)
        buf = io.BytesIO()
        async for ch in c.stream():
            if ch["type"] == "audio":
                buf.write(ch["data"])
        return buf.getvalue()

    mp3 = asyncio.run(_gen())
    if not mp3:
        raise RuntimeError("edge-tts no devolvió audio")
    return mp3


@app.get("/estudio")
async def estudio_page(request: Request):
    try:
        _require_user(request)
    except HTTPException:
        return RedirectResponse("/")
    return FileResponse(os.path.join(STATIC_DIR, "estudio", "index.html"))


@app.get("/api/studio/health")
async def studio_health(request: Request):
    _require_user(request)

    def up(url: str) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    import importlib.util
    return {
        "cv3": up(Config.CV3_URL.replace("/tts", "/health")),
        "f5": up(Config.PC_TTS_URL.replace("/tts", "/health")),
        "alvaro": importlib.util.find_spec("edge_tts") is not None,
    }


@app.post("/api/studio/tts")
async def studio_tts(request: Request):
    _require_user(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    model = (body.get("model") or "cv3").strip().lower()
    speed = max(0.5, min(2.0, float(body.get("speed") or 1.0)))
    if not text:
        raise HTTPException(status_code=400, detail="Escribe algo para sintetizar")
    if len(text) > 3000:
        raise HTTPException(status_code=400, detail="Máximo 3000 caracteres")

    if model == "cv3":
        data, ctype = await run_in_threadpool(
            _pc_call, Config.CV3_URL,
            {"text": voice.normalize_for_cv3(text), "speed": speed})
    elif model == "f5":
        data, ctype = await run_in_threadpool(
            _pc_call, Config.PC_TTS_URL,
            {"text": voice.normalize_for_tts(text), "speed": speed,
             "cfg_strength": Config.F5_CFG, "nfe_step": Config.F5_NFE})
    elif model == "alvaro":
        try:
            mp3 = await run_in_threadpool(_edge_tts, voice.normalize_for_cv3(text), speed)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Álvaro no disponible: {e}")
        data, ctype = mp3, "audio/mpeg"
    else:
        raise HTTPException(status_code=400, detail="Modelo desconocido (cv3|f5|alvaro)")

    resp = Response(content=data, media_type=ctype)
    resp.headers["X-Generated-By"] = model
    return resp


@app.get("/api/studio/ref")
async def studio_ref(request: Request):
    _require_user(request)
    return await run_in_threadpool(_pc_get_json, Config.CV3_URL.replace("/tts", "/api/ref"))


@app.post("/api/studio/ref/text")
async def studio_ref_text(request: Request):
    _require_user(request)
    body = await request.json()
    return await run_in_threadpool(
        _pc_post_json, Config.CV3_URL.replace("/tts", "/api/ref/text"), body)


@app.post("/api/studio/ref/audio")
async def studio_ref_audio(request: Request):
    _require_user(request)
    raw = await request.body()
    import urllib.request
    req = urllib.request.Request(
        Config.CV3_URL.replace("/tts", "/api/ref/audio"),
        data=raw, headers={"Content-Type": "application/octet-stream"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"PC HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con el PC: {e}")


# --- Multivoz (proxies al servidor CosyVoice del PC) ---

def _pc_delete_json(url: str, timeout: int = 15):
    import urllib.request
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"PC HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con el PC: {e}")


@app.get("/api/studio/voces")
async def studio_voces(request: Request):
    _require_user(request)
    return await run_in_threadpool(_pc_get_json, Config.CV3_URL.replace("/tts", "/api/voces"), 20)


@app.post("/api/studio/voces")
async def studio_voces_crear(request: Request):
    _require_user(request)
    body = await request.json()
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Ponle un nombre a la voz")
    return await run_in_threadpool(
        _pc_post_json, Config.CV3_URL.replace("/tts", "/api/voces"), body, 60)


@app.post("/api/studio/voces/activar")
async def studio_voces_activar(request: Request):
    _require_user(request)
    body = await request.json()
    if not (body.get("nombre") or "").strip():
        raise HTTPException(status_code=400, detail="Falta el nombre de la voz")
    return await run_in_threadpool(
        _pc_post_json, Config.CV3_URL.replace("/tts", "/api/voces/activar"), body, 20)


@app.delete("/api/studio/voces/{nombre}")
async def studio_voces_borrar(nombre: str, request: Request):
    _require_user(request)
    import urllib.parse
    url = Config.CV3_URL.replace("/tts", "/api/voces/") + urllib.parse.quote(nombre, safe="")
    return await run_in_threadpool(_pc_delete_json, url, 20)


# ---------------------------------------------------------------- estáticos

@app.get("/")
async def index():
    return FileResponse(
        os.path.join(STATIC_DIR, "index.html"),
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
