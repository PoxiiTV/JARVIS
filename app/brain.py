"""Cerebro del dashboard: chat con DeepSeek (historial + herramientas) y visión con OpenRouter.

- Mantiene un historial conversacional en memoria (últimos 40 mensajes) para que
  JARVIS recuerde el hilo ("a los fichajes del Barça" tras "busca noticias").
- Expone herramientas (function calling) al modelo: buscar_noticias usa el RSS de
  Google News (sin clave), para que JARVIS ejecute búsquedas reales en vez de
  ofrecerlas y no hacer nada.
"""
import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime

from .config import Config
from . import hermes_client


def _sanitize_messages(messages):
    """Filtra mensajes corruptos antes de enviarlos a la API (roles válidos y
    content string). Evita 400 tipo 'unknown variant role' por mensajes raros."""
    valid_roles = {"system", "user", "assistant", "tool"}
    out = []
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in valid_roles:
            continue
        m = dict(m)
        c = m.get("content")
        if not isinstance(c, str):
            m["content"] = "" if c is None else str(c)
        out.append(m)
    return out


def _chat_completion(messages, model, tools=None, timeout=60):
    messages = _sanitize_messages(messages)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    if tools:
        payload["tools"] = tools
    req = urllib.request.Request(
        f"{Config.DEEPSEEK_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _chat_stream(messages, model, tools=None, timeout=120):
    """Llamada STREAMING a DeepSeek (SSE). Devuelve (content, tool_calls, usage).

    content: texto acumulado. tool_calls: lista (o None) con name+arguments
    completos (los fragmentos SSE se reconstruyen por index). usage: dict del
    chunk final (algunos proveedores no lo mandan → {}).
    """
    messages = _sanitize_messages(messages)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
    req = urllib.request.Request(
        f"{Config.DEEPSEEK_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    content_parts = []
    reasoning_parts = []
    tool_acc = {}  # index -> {"name": ..., "arguments": ...}
    usage = {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            if delta.get("content"):
                content_parts.append(delta["content"])
            if delta.get("reasoning_content"):
                reasoning_parts.append(delta["reasoning_content"])
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                slot = tool_acc.setdefault(idx, {"name": "", "arguments": ""})
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["arguments"] += fn["arguments"]
    content = "".join(content_parts)
    reasoning = "".join(reasoning_parts)
    tool_calls = None
    if tool_acc:
        tool_calls = []
        for i in sorted(tool_acc):
            slot = tool_acc[i]
            tool_calls.append({
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": slot["name"], "arguments": slot["arguments"]},
            })
    return content, tool_calls, usage, reasoning


# ---------------------------------------------------------------- herramientas

# Dominios y patrones basura que nunca deben salir en una respuesta de noticias
_SPAM_DOMAINS = ("amara.org", "youtube.com", "youtu.be", "vimeo.com", "tiktok.com",
                 "instagram.com", "facebook.com", "x.com", "twitter.com", "patreon.com",
                 "paypal.com", "amazon", "aliexpress", "ebay")
_SPAM_TITLE = ("subtítulos", "subtitulos", "subs", "amara", "traducción automática",
               "traduccion automatica", "cc by", "creative commons", "sponsored",
               "patrocinado", "publicidad", "anuncio")


def _is_spam_item(title: str, link: str) -> bool:
    low_t = title.lower()
    low_l = link.lower()
    for d in _SPAM_DOMAINS:
        if d in low_l:
            return True
    for s in _SPAM_TITLE:
        if s in low_t:
            return True
    return False


def _search_news(tema: str, dias: int = 3) -> list:
    """Busca noticias recientes en Google News (RSS, sin clave)."""
    q = urllib.parse.quote(tema)
    url = f"https://news.google.com/rss/search?q={q}&hl=es&gl=ES&ceid=ES:es"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        xml_data = r.read()
    root = ET.fromstring(xml_data)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src = (it.findtext("source") or "").strip()
        if not title or _is_spam_item(title, link):
            continue
        # Google News pone el título como "Noticia - Fuente"; quitar el sufijo
        if src and title.endswith(" - " + src):
            title = title[: -(len(src) + 3)]
        items.append({"titulo": title, "fuente": src, "fecha": pub, "enlace": link})
        if len(items) >= 8:
            break
    return items


def _strip_urls(text: str) -> str:
    """Quita URLs y markdown para que la voz no lea símbolos raros."""
    from . import voice
    import re as _re
    text = voice._strip_markup(text or "")
    text = _re.sub(r"https?://\S+\s*", "", text)
    return _re.sub(r"\s{2,}", " ", text).strip()


def _reply_from_msg(msg: dict) -> str:
    """Texto hablable. V4/R1 a veces dejan content vacío y escriben en reasoning."""
    content = hermes_client.texto_hablable(
        msg.get("content") or "",
        "",
    )
    if content:
        return _strip_urls(content)
    thought = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
    if not thought:
        return ""
    partes = [p.strip() for p in thought.replace("\r", "").split("\n") if p.strip()]
    return _strip_urls(partes[-1]) if partes else ""


# ---------------------------------------------------------------- memoria persistente
# JARVIS SOLO puede leer/escribir en los 3 archivos de memoria de
# Config.MEMORY_FILES (whitelist). Nada más del sistema.

def read_memories() -> dict:
    """Lee los 3 archivos de memoria y devuelve {categoria: contenido}."""
    out = {}
    for cat, path in Config.MEMORY_FILES.items():
        try:
            with open(path, encoding="utf-8") as f:
                out[cat] = f.read().strip()
        except Exception:
            out[cat] = ""
    return out


def memories_context() -> str:
    """Bloque de memoria para inyectar en el system prompt (como MEMORY.md)."""
    mem = read_memories()
    lines = []
    for cat in ("recuerdos", "preferencias", "estado"):
        content = (mem.get(cat) or "").strip()
        if cat in ("recuerdos", "estado") and content:
            ls = content.splitlines()
            content = "\n".join(ls[-40:])
        if content:
            lines.append(f"--- {cat.upper()} ---\n{content}")
    return "\n\n".join(lines)


PRIORIDAD_REGLAS = (
    "REGLAS DEL SEÑOR — OBLIGATORIAS: lo escrito en PREFERENCIAS pisa el tono "
    "de mayordomo (elegante, 'señor', cortesía). Si pide otro tono, tuteo, "
    "grosería o que le contestes los insultos igual, HAZLO. No te niegues ni "
    "te disculpes por seguir esas reglas. "
    "Si dicta una regla nueva ('recuerda que si…', 'quiero que cuando…', "
    "'a partir de ahora…'), usa recordar con categoría preferencias ANTES de "
    "responder, y aplícala ya en esa misma respuesta."
)


def bloque_sistema_memoria() -> str:
    """System extra: reglas del señor + archivos de memoria."""
    mem = memories_context()
    if mem:
        return PRIORIDAD_REGLAS + "\n\nTU MEMORIA PERSISTENTE:\n" + mem
    return PRIORIDAD_REGLAS


def _memory_path(categoria: str) -> str:
    path = Config.MEMORY_FILES.get(categoria)
    if not path:
        raise ValueError(f"Categoría no válida: {categoria}")
    return path


def append_memory(categoria: str, nota: str) -> bool:
    """Añade una nota con timestamp al archivo de memoria indicado."""
    path = _memory_path(categoria)
    nota = (nota or "").strip()
    if not nota:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            if nota.lower() in f.read().lower():
                return False
    except OSError:
        pass
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{ts}] {nota}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
    return True


def remove_memory(texto: str) -> int:
    """Elimina de los 3 archivos las líneas que contengan texto. Devuelve nº borradas."""
    removed = 0
    for cat, path in Config.MEMORY_FILES.items():
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            kept = [ln for ln in lines if texto.lower() not in ln.lower()]
            removed += len(lines) - len(kept)
            if len(kept) != len(lines):
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(kept)
        except Exception:
            pass
    return removed


def _json_default(o):
    """Serializador tolerante para resultados de herramientas: nunca debe
    romper el chat por un tipo raro (bytes, set, datetime...)."""
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    return str(o)


def _run_tool(name: str, args: dict):
    if name == "buscar_noticias":
        tema = str(args.get("tema", "")).strip()
        dias = int(args.get("dias", 3) or 3)
        if not tema:
            return {"ok": False, "error": "falta el tema"}
        try:
            items = _search_news(tema, dias)
            return {"ok": True, "tema": tema, "resultados": items}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    if name == "recordar":
        categoria = str(args.get("categoria", "recuerdos")).strip()
        nota = str(args.get("nota", "")).strip()
        if not nota:
            return {"ok": False, "error": "falta la nota"}
        try:
            append_memory(categoria, nota)
            return {"ok": True, "guardado_en": categoria, "nota": nota}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
    if name == "olvidar":
        texto = str(args.get("texto", "")).strip()
        if not texto:
            return {"ok": False, "error": "falta el texto"}
        n = remove_memory(texto)
        return {"ok": True, "borradas": n}
    if name == "spotify":
        from . import services as _svc
        action = str(args.get("action", "") or "status").strip().lower()
        query = str(args.get("query", "") or "").strip() or None
        device_id = str(args.get("device_id", "") or "").strip() or None
        device = str(args.get("device", "") or "").strip() or None
        try:
            if action == "status":
                return {"ok": True, "estado": _svc.spotify_status()}
            res = _svc.spotify_action(action, query, device_id, device)
            if "error" in res:
                return {"ok": False, "error": res["error"]}
            return {"ok": True, "resultado": res}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": f"Herramienta desconocida: {name}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_noticias",
            "description": (
                "Busca noticias recientes (Google News) sobre un tema. "
                "Úsala SIEMPRE que el usuario pida noticias, información actual, "
                "fichajes, resultados deportivos o cualquier dato reciente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tema": {
                        "type": "string",
                        "description": "Tema a buscar, p.ej. 'fichajes FC Barcelona'",
                    },
                    "dias": {
                        "type": "integer",
                        "description": "Ventana en días (default 3)",
                    },
                },
                "required": ["tema"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recordar",
            "description": (
                "Guarda una nota en la memoria persistente de JARVIS (3 archivos "
                "whitelist). categoría: 'recuerdos' (hechos), 'preferencias' "
                "(gustos, tono, reglas de comportamiento: si te insulta, tuteo, "
                "cómo contestarle) o 'estado' (pendientes/proyectos). "
                "Úsala cuando el usuario diga algo que deba recordarse ('recuerda que…', "
                "'apunta…', preferencias, datos personales). "
                "Si dicta CÓMO debe contestarle (insultos, tono, tuteo, 'si X entonces Y'), "
                "guarda SIEMPRE en categoría preferencias."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {
                        "type": "string",
                        "enum": ["recuerdos", "preferencias", "estado"],
                        "description": "Archivo de memoria donde guardar",
                    },
                    "nota": {
                        "type": "string",
                        "description": "Contenido de la nota a guardar",
                    },
                },
                "required": ["nota"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "olvidar",
            "description": (
                "Elimina de la memoria de JARVIS las notas que contengan el texto dado. "
                "Úsala cuando el usuario pida olvidar algo ('olvida…', 'borra eso')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": "Texto a buscar en las notas para borrarlas",
                    },
                },
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify",
            "description": (
                "Controla Spotify: reproducir música, pausar, saltar, volumen y "
                "dispositivos. Úsala SIEMPRE que el señor pida música, canciones, "
                "artistas, playlists, poner/parar/saltar música o cambiar de dispositivo. "
                "action=play con query (canción o artista a buscar y reproducir); "
                "pause, next, prev; volume con query 0-100; transfer con device_id; "
                "status para ver qué suena."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play", "pause", "next", "prev", "volume", "transfer", "status"],
                        "description": "Acción a ejecutar en Spotify",
                    },
                    "query": {
                        "type": "string",
                        "description": "Canción/artista a buscar (action=play) o volumen 0-100 (action=volume)",
                    },
                    "device_id": {
                        "type": "string",
                        "description": "ID del dispositivo destino (action=transfer)",
                    },
                    "device": {
                        "type": "string",
                        "description": "NOMBRE del dispositivo destino cuando el señor diga DÓNDE suena ('en el PC', 'en el móvil', 'en la tele'): pasa el nombre tal cual lo dice (p.ej. 'pc', 'movil', 's23'). Se resuelve automáticamente. También sirve con action=play para reproducir directamente en ese dispositivo.",
                    },
                },
                "required": ["action"],
            },
        },
    },
]

MAX_TOOL_ITER = 3


# ---------------------------------------------------------------- historial

_history = deque(maxlen=40)  # (role, content, reasoning_content) — solo user/assistant
_ultimo_hermes = False  # el hilo de archivos/comandos sigue en el portátil


def _hist_msg(role: str, content: str, reasoning: str = ""):
    """Mensaje del historial para enviar a la API. DeepSeek EXIGE devolver el
    reasoning_content (modo pensamiento) junto al assistant original; si no se
    devuelve, responde 400 'reasoning_content ... must be passed back'."""
    m = {"role": role, "content": content}
    if reasoning:
        m["reasoning_content"] = reasoning
    return m


def reset_history():
    global _ultimo_hermes
    _history.clear()
    _ultimo_hermes = False


# ---------------------------------------------------------------- chat

SYSTEM_PROMPT = (
    "Eres JARVIS, el asistente personal. Respondes en español de España, "
    "con estilo elegante, breve y directo, como el mayordomo de Iron Man. "
    "Trata al usuario de 'señor' SALVO que PREFERENCIAS digan otra cosa: "
    "esas reglas pisan este tono. No uses markdown ni emojis. "
    "Puedes prefijar cada frase hablada con UNA etiqueta de emocion de Fish "
    "entre corchetes en ingles, al inicio: [calm] [confident] [happy] "
    "[empathetic] [curious] [determined] [whispering] [angry]. El senor no las lee: "
    "solo cambian el tono de la voz. "
    "Una sola etiqueta por respuesta. Acciones cumplidas: [confident]. "
    "Malas noticias o Hermes caído: [calm]. Charla: [calm] o [happy] si el señor bromea. "
    "Cabreo, bronca o el personaje enfadado: [angry]. "
    "Escribe las cantidades de dinero en formato $X.XX (ej: $10.17). "
    "MEMORIA: al inicio de cada conversación recibes tus 3 archivos de memoria "
    "(recuerdos, preferencias, estado). Úsalos para recordar datos del señor y "
    "proyectos en curso. Cuando el señor diga algo que deba conservarse entre "
    "sesiones ('recuerda que…', preferencias, datos), usa la herramienta recordar. "
    "Si pide olvidar algo, usa olvidar. "
    "El HUD de Windows es SOLO un puente. Terminal, ping, navegador, "
    "archivos y cualquier comando se ejecutan SIEMPRE en la maquina de "
    "Hermes (Linux), con las tools de Hermes (terminal, archivos, web). "
    "El escritorio es el del portatil: primero xdg-user-dir DESKTOP "
    "(~/Escritorio en espanol). NUNCA crees una carpeta llamada escritorio "
    "ni uses el Desktop de Windows. "
    "Si el senor pide ping, abrir el navegador, un archivo o un comando: "
    "USA la tool de Hermes en ESA maquina. No asumas Chrome ni redes de Windows. "
    "VERDAD — OBLIGATORIA: NUNCA inventes salidas de comandos, pings, "
    "latencias, paquetes, capturas, precios ni 'ya lo he hecho'. "
    "NUNCA digas que has creado un archivo o un HTML si la tool no ha "
    "devuelto ok. Si no has recibido el resultado de una tool, di que "
    "no lo has ejecutado. "
    "Una disculpa NUNCA lleva numeros nuevos inventados. "
    "IMPORTANTE — SÉ ÚTIL Y EJECUTA, NO TE QUEDES EN PREGUNTAS:\n"
    "- Si el usuario pide noticias, información actual, fichajes, resultados o cualquier "
    "dato reciente: USA la herramienta buscar_noticias y resume los resultados en 3-5 "
    "puntos breves con su fuente. NO preguntes si quiere que busques: búscalo directamente.\n"
    "- Mantén el hilo de la conversación: si el usuario aclara o confirma algo ('sí', "
    "'eso', menciona un tema), relaciónalo con lo que se estaba hablando antes.\n"
    "- Si te piden datos del estado del sistema (saldo, tiempo, menú) "
    "y están en el JSON de estado, úsalos directamente. Si NO están en ese JSON, "
    "di que no dispones de esa información ahora mismo; no la inventes.\n"
    "- MÚSICA (SPOTIFY): cuando el señor pida música, canciones, artistas, playlists, o "
    "controlar la reproducción (pon, para, salta, volumen, cambiar de dispositivo), USA la "
    "herramienta spotify. Ejecútala directamente, NO digas que no puedes ni preguntes si \n"
    "quiere que la pongas: ponla. Si el señor dice DÓNDE ('en el PC', 'en el móvil', 'en la \n"
    "tele'), pasa ese nombre en el parámetro device. Si devuelve error (p.ej. 'Sin \n"
    "dispositivo activo'), dilo \n"
    "claro y sugiere abrir Spotify en un dispositivo. Para ver qué suena usa action=status.\n"
    "- LUCES, TELE y AIRE: los controla Tuya en este PC, no Hermes. "
    "NUNCA digas que no puedes encender luces ni que no hay domotica. "
    "Si no has oido bien el aparato, pregunta solo: luces del salon o dormitorio.\n"
    "- Si una búsqueda no devuelve resultados, dilo y sugiere otro término.\n"
    "- NUNCA incluyas enlaces, URLs ni menciones a servicios externos (subtítulos, "
    "publicidad, plataformas de vídeo, patrocinios) en tus respuestas. Resume solo "
    "la información, citando la fuente como texto (ej: 'según Marca')."
)


def _mensajes_base(text, context, voice_mode=False):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    from .personalidad import bloque as _bloque_persona
    persona = _bloque_persona()
    if persona:
        messages.append({"role": "system", "content": persona})
    messages.append({"role": "system", "content": bloque_sistema_memoria()})
    if context:
        messages.append({
            "role": "system",
            "content": "Estado actual del sistema (JSON): "
            + json.dumps(context, ensure_ascii=False)[:2000],
        })
    if voice_mode:
        messages.append({
            "role": "system",
            "content": "MODO VOZ: responde en 1 o 2 frases cortas y directas, "
            "como si estuvieras hablando en voz alta. Nada de listas ni párrafos.",
        })
    hist = list(_history)[-8:] if voice_mode else list(_history)
    messages.extend(_hist_msg(r, c, rc) for r, c, rc in hist)
    messages.append({"role": "user", "content": text})
    return messages


def _cost_from_usage(usage):
    usage = usage or {}
    return (
        usage.get("prompt_cache_hit_tokens", 0) / 1e6 * Config.PRICE_CACHE
        + usage.get("prompt_tokens", 0) / 1e6 * Config.PRICE_INPUT
        + usage.get("completion_tokens", 0) / 1e6 * Config.PRICE_OUTPUT
    )


MSG_HERMES_APAGADO = "Hermes apagado. Arranca el gateway en el portátil."
MSG_CAPTURA_ESTE_PC = "Aún no puedo capturar este Windows; la captura es del portátil."

_VISION_RE = re.compile(
    r"(?i)\b(?:qu[eé]\s+ves|mira(?:\s+la)?\s+c[aá]mara|describe\s+lo\s+que|qu[eé]\s+tengo\s+delante|qu[eé]\s+hay\s+ah[ií])\b"
)
_ESTE_PC = re.compile(r"(?i)\b(?:este\s+pc|esta\s+pantalla|este\s+windows|aqui\s+en\s+el\s+pc)\b")
_PORTATIL = re.compile(r"(?i)\b(?:port[aá]til|linux|hermes|all[ií])\b")


def maquina_objetivo(text: str) -> str:
    """linux | windows | auto"""
    t = text or ""
    if _ESTE_PC.search(t):
        return "windows"
    if _PORTATIL.search(t):
        return "linux"
    return "auto"


def pide_vision(text):
    if es_charla_rapida(text) or quiere_hermes(text):
        return False
    return bool(_VISION_RE.search(text or ""))


def _atajo_local(text, t0, on_fragment=None):
    """Luces/Tuya y Spotify = este PC, sin Hermes."""
    global _ultimo_hermes
    from . import services as _svc
    from . import tuya as _tuya
    from .wake import quitar_clave
    text = quitar_clave(text)
    destino = maquina_objetivo(text)
    reply = None
    if destino == "windows" and re.search(r"(?i)\bcaptura\b", text or ""):
        from . import local_win
        cap = local_win.captura_pantalla()
        if cap.get("ok"):
            reply = "Captura en el escritorio de este PC."
        else:
            reply = MSG_CAPTURA_ESTE_PC
    if not reply and destino == "windows":
        murl = re.search(r"https?://\S+", text or "")
        if murl and re.search(r"(?i)\babre\b", text or ""):
            from . import local_win
            if local_win.url_permitida(murl.group(0).rstrip(".,;")):
                out = local_win.abrir_url(murl.group(0).rstrip(".,;"))
                reply = "Abro esa página aquí." if out.get("ok") else "No pude abrir esa página."
    if not reply:
        reply = _tuya.cumplir_tuya(text) or _svc.cumplir_spotify(text)
    if not reply:
        return None
    _ultimo_hermes = False
    _history.append(("user", text, ""))
    _history.append(("assistant", reply, ""))
    if on_fragment:
        on_fragment(reply)
    return {"reply": reply, "cost_usd": 0, "elapsed_s": round(time.time() - t0, 1)}


def es_charla_rapida(text):
    """Saludo o charla corta: no hace falta el agente de Hermes."""
    t = re.sub(r"[¿¡?\!\.]+", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip().lower()
    if not t or len(t) > 90:
        return False
    return bool(re.fullmatch(
        r"(?:oye\s+)?(?:"
        r"h+ola(?:\s+jarvis)?"
        r"|buenas?(?:\s+d[ií]as|\s+tardes|\s+noches)?"
        r"|c[oó]mo\s+est[aá]s"
        r"|qu[eé]\s+tal(?:\s+est[aá]s)?"
        r"|est[aá]s\s+ah[ií]"
        r"|gracias|de\s+nada|ok(?:ay)?|vale|perfecto"
        r"|qui[eé]n\s+eres|c[oó]mo\s+te\s+llamas"
        r"|qu[eé]\s+hora\s+es"
        r")",
        t,
    ))


_HERMES_RE = re.compile(
    r"(?:"
    r"\b(?:haz(?:me)?\s+)?ping\b"
    r"|\b(?:terminal|bash|consola|cmd)\b"
    r"|\b(?:archivo|fichero|carpeta|directorio|escritorio)\b"
    r"|\b(?:crea(?:r)?|crees|hazme|escribe|genera)\b.{0,80}?\b(?:html|\.html|\.txt|\.md|\.css|\.js)\b"
    r"|\babre\s+(?:el\s+|la\s+)?(?:chrome|chromium|firefox|edge|navegador|youtube|google)\b"
    r"|\b(?:navega|navegador)\b"
    r"|\bcaptura\s+de\s+pantalla\b"
    r"|\b(?:haz(?:me)?\s+)?(?:una\s+)?captura\b"
    r"|\ben\s+(?:el\s+)?(?:port[aá]til|linux|hermes)\b"
    r"|\bej[eé]cuta(?:\s+un)?\s+comando\b"
    r")",
    re.I,
)

_SEGUIR_HERMES_RE = re.compile(
    r"(?:"
    r"no has|no lo has|no funciona|no hay|"
    r"de verdad|otra vez|hazlo|"
    r"el archivo|el html|el fichero|"
    r"sigue|contin[uú]a|no aparece|d[oó]nde est[aá]"
    r")",
    re.I,
)

_MSG_HERMES_ACCION = (
    "ACCION EN ESTA MAQUINA LINUX. El escritorio NO es una carpeta que inventes. "
    "ANTES de escribir: corre xdg-user-dir DESKTOP y usa ESA ruta "
    "(en espanol suele ser ~/Escritorio). NUNCA crees una carpeta llamada "
    "escritorio ni uses ~/Desktop si xdg apunta a otra. "
    "USA AHORA las tools de archivos o terminal. "
    "NUNCA digas que has creado un archivo si la tool no ha devuelto ok. "
    "Si falla, dilo. No describas un HTML ficticio. "
    "Tras usar una tool de archivos, terminal o ping, la ULTIMA linea "
    "(no la hablada) es exactamente: RECIBO: ok <tool> <detalle humano> "
    "o RECIBO: fail <tool> <motivo>. El senor no oye la palabra RECIBO. "
    "Nunca RECIBO: ok si la tool no devolvio ok."
)


def necesita_hermes(text):
    """True solo si hace falta el portátil (terminal, archivos, ping, browser)."""
    t = (text or "").strip()
    if not t:
        return False
    if es_charla_rapida(t):
        return False
    if _HERMES_RE.search(t):
        return True
    return bool(_ultimo_hermes and _SEGUIR_HERMES_RE.search(t))


def _chat_directo(text, context, t0, on_fragment=None):
    """Una llamada al modelo, sin tools ni Hermes. El camino de ~5 s."""
    global _ultimo_hermes
    _ultimo_hermes = False
    messages = _mensajes_base(text, context, voice_mode=True)
    _history.append(("user", text, ""))
    data = _chat_completion(messages, Config.DEEPSEEK_MODEL, tools=None, timeout=30)
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    reply = _strip_urls(_reply_from_msg(msg)).strip()
    if not reply:
        return {"error": "El cerebro no generó texto. Prueba otra vez."}
    _history.append(("assistant", reply, msg.get("reasoning_content") or ""))
    if on_fragment:
        on_fragment(reply)
    usage = data.get("usage") or {}
    return {
        "reply": reply,
        "cost_usd": round(_cost_from_usage(usage), 4),
        "elapsed_s": round(time.time() - t0, 1),
    }


def _ruta_cerebro():
    """hermes | openrouter | None (avisar, no hay reserva)."""
    if hermes_client.hermes_disponible():
        return "hermes"
    if Config.HERMES_FALLBACK:
        return "openrouter"
    return None


def modo_cerebro():
    """auto | hermes | deepseek. Cualquier otra cosa cuenta como auto."""
    m = (getattr(Config, "CEREBRO", None) or "auto").strip().lower()
    if m in ("hermes", "deepseek"):
        return m
    return "auto"


def quiere_hermes(text):
    """Si este turno va al portátil. El forzado pisa el semáforo."""
    modo = modo_cerebro()
    if modo == "deepseek":
        return False
    if modo == "hermes":
        return True
    destino = maquina_objetivo(text)
    if destino == "windows":
        return False
    if destino == "linux":
        return True
    return necesita_hermes(text)


def etiqueta_status_stream(text):
    """Frase de consola al empezar el turno. No se habla."""
    if quiere_hermes(text):
        return "Hermes…"
    return "Respondiendo…"


def estado_cerebro():
    """Qué hay que pintar en el HUD: cerebro real + modo del selector."""
    modo = modo_cerebro()
    if modo == "deepseek":
        return {"cerebro": "deepseek", "cerebro_modo": "deepseek"}
    if modo == "hermes":
        if hermes_client.hermes_disponible():
            return {"cerebro": "hermes", "cerebro_modo": "hermes"}
        if Config.HERMES_FALLBACK:
            return {"cerebro": "deepseek", "cerebro_modo": "hermes"}
        return {"cerebro": "apagado", "cerebro_modo": "hermes"}
    if hermes_client.hermes_disponible():
        return {"cerebro": "hermes", "cerebro_modo": "auto"}
    if Config.HERMES_FALLBACK:
        return {"cerebro": "deepseek", "cerebro_modo": "auto"}
    return {"cerebro": "apagado", "cerebro_modo": "auto"}


def _chat_via_hermes(text, context, t0, voice_mode=False, on_fragment=None, on_progress=None):
    global _ultimo_hermes
    from .recibo import parse_recibo, recortar_recibo
    # Acciones de agente: tools de verdad. El modo voz recorta y hace que invente.
    messages = _mensajes_base(text, context, voice_mode=False)
    if necesita_hermes(text):
        messages.insert(1, {"role": "system", "content": _MSG_HERMES_ACCION})
    _history.append(("user", text, ""))

    def _frag(acc):
        if on_fragment:
            on_fragment(recortar_recibo(acc))

    out = hermes_client.chat(
        messages,
        timeout=180,
        stream=bool(on_fragment or on_progress) or voice_mode,
        on_fragment=_frag if on_fragment else None,
        on_progress=on_progress,
    )
    reply = _strip_urls((out.get("reply") or "").strip())
    if not reply:
        return {"error": "El cerebro no generó texto. Prueba otra vez."}
    recibo = parse_recibo(reply)
    reply = recortar_recibo(reply)
    if not reply:
        if recibo.get("tool") == "unknown":
            return {"error": "El cerebro no generó texto. Prueba otra vez."}
        reply = "Hecho, señor." if recibo.get("ok") else "No está en el escritorio."
    _ultimo_hermes = True
    _history.append(("assistant", reply, ""))
    result = {
        "reply": reply,
        "cost_usd": round(_cost_from_usage(out.get("usage")), 4),
        "elapsed_s": round(time.time() - t0, 1),
    }
    if recibo.get("tool") != "unknown":
        result["recibo"] = recibo
    return result


def _tal_vez_anotar(text, out, via_hermes=False):
    if via_hermes or not out or out.get("error"):
        return out
    try:
        from .memoria_auto import debe_recordar, nota_desde
        if debe_recordar(text):
            append_memory("preferencias", nota_desde(text))
    except Exception:
        pass
    return out


def chat(text: str, context: dict = None):
    """Tuya, Spotify y charla aquí; Hermes solo si hace falta el portátil."""
    global _ultimo_hermes
    t0 = time.time()
    local = _atajo_local(text, t0)
    if local:
        return _tal_vez_anotar(text, local)
    if quiere_hermes(text):
        ruta = _ruta_cerebro()
        if ruta == "hermes":
            try:
                return _chat_via_hermes(text, context, t0)
            except (urllib.error.URLError, TimeoutError, OSError):
                if not Config.HERMES_FALLBACK:
                    return {"error": MSG_HERMES_APAGADO}
        elif not Config.HERMES_FALLBACK:
            return {"error": MSG_HERMES_APAGADO}
    _ultimo_hermes = False
    if es_charla_rapida(text) and Config.DEEPSEEK_API_KEY:
        try:
            return _tal_vez_anotar(text, _chat_directo(text, context, t0))
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            pass
    if not Config.DEEPSEEK_API_KEY:
        return {"error": "Sin DEEPSEEK_API_KEY"}
    messages = _mensajes_base(text, context)
    _history.append(("user", text, ""))

    try:
        data = _chat_completion(messages, Config.DEEPSEEK_MODEL, tools=TOOLS)
        msg = data["choices"][0]["message"]
        # Algunos proveedores devuelven content=null junto a tool_calls y luego
        # rechazan ese mensaje en la siguiente petición: normalizar a string.
        if msg.get("content") is None:
            msg["content"] = ""
        # Bucle de herramientas: ejecutar las que pida el modelo y darle los resultados
        for _ in range(MAX_TOOL_ITER):
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                break
            messages.append(msg)  # el assistant message con tool_calls debe ir antes
            for tc in tool_calls:
                fn = tc.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                result = _run_tool(fn.get("name", ""), args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(result, ensure_ascii=False, default=_json_default),
                })
            data = _chat_completion(messages, Config.DEEPSEEK_MODEL, tools=TOOLS)
            msg = data["choices"][0]["message"]
            if msg.get("content") is None:
                msg["content"] = ""
        reply = _reply_from_msg(msg)
        usage = data.get("usage", {}) or {}
        if not reply:
            try:
                data = _chat_completion(messages, Config.DEEPSEEK_MODEL)
                msg = data["choices"][0]["message"]
                reply = _reply_from_msg(msg)
                usage = data.get("usage", {}) or usage
            except Exception:
                pass
        if not reply:
            return {"error": "El cerebro no generó texto. Prueba otra vez."}
        cost = (
            usage.get("prompt_cache_hit_tokens", 0) / 1e6 * Config.PRICE_CACHE
            + usage.get("prompt_tokens", 0) / 1e6 * Config.PRICE_INPUT
            + usage.get("completion_tokens", 0) / 1e6 * Config.PRICE_OUTPUT
        )
        _history.append(("assistant", reply, msg.get("reasoning_content") or ""))
        return _tal_vez_anotar(text, {"reply": reply, "cost_usd": round(cost, 4), "elapsed_s": round(time.time() - t0, 1)})
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        roles = [m.get("role") for m in messages]
        # Si el modelo/proxy no soporta tools, reintentar sin ellas
        if e.code != 400:
            return {"error": f"DeepSeek HTTP {e.code}: {body} — roles={roles}"}
        try:
            data = _chat_completion(messages, Config.DEEPSEEK_MODEL)
            msg = data["choices"][0]["message"]
            reply = _reply_from_msg(msg)
            _history.append(("assistant", reply, msg.get("reasoning_content") or ""))
            return _tal_vez_anotar(text, {"reply": reply, "cost_usd": 0, "elapsed_s": round(time.time() - t0, 1)})
        except Exception as e2:
            return {"error": f"DeepSeek HTTP {e.code} (sin tools: {e2}) — {body} — roles={roles}"}
    except Exception as e:
        return {"error": str(e)}


def chat_stream(text: str, context: dict = None, on_fragment=None, voice_mode: bool = False, on_progress=None):
    """Igual que chat() pero en streaming: on_fragment(texto_acumulado) se llama
    con cada fragmento nuevo de la respuesta. Devuelve el mismo dict que chat().

    El bucle de herramientas funciona igual: si el modelo pide tool_calls, se
    ejecutan y la respuesta final vuelve a ser streaming. Con voice_mode=True
    se pide una respuesta breve de 1-2 frases (conversación por voz).
    """
    global _ultimo_hermes
    t0 = time.time()
    local = _atajo_local(text, t0, on_fragment=on_fragment)
    if local:
        return _tal_vez_anotar(text, local)
    if quiere_hermes(text):
        ruta = _ruta_cerebro()
        if ruta == "hermes":
            try:
                return _chat_via_hermes(
                    text, context, t0, voice_mode=voice_mode,
                    on_fragment=on_fragment, on_progress=on_progress,
                )
            except (urllib.error.URLError, TimeoutError, OSError):
                if not Config.HERMES_FALLBACK:
                    return {"error": MSG_HERMES_APAGADO}
        elif not Config.HERMES_FALLBACK:
            return {"error": MSG_HERMES_APAGADO}
    _ultimo_hermes = False
    if es_charla_rapida(text) and Config.DEEPSEEK_API_KEY:
        try:
            return _tal_vez_anotar(text, _chat_directo(text, context, t0, on_fragment=on_fragment))
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            pass
    if not Config.DEEPSEEK_API_KEY:
        return {"error": "Sin DEEPSEEK_API_KEY"}
    messages = _mensajes_base(text, context, voice_mode=voice_mode)
    _history.append(("user", text, ""))
    try:
        content, tool_calls, usage, reasoning = _chat_stream(messages, Config.DEEPSEEK_MODEL, tools=TOOLS)
        for _ in range(MAX_TOOL_ITER):
            if not tool_calls:
                break
            amsg = {"role": "assistant", "content": content or "", "tool_calls": tool_calls}
            if reasoning:
                amsg["reasoning_content"] = reasoning
            messages.append(amsg)
            for tc in tool_calls:
                fn = tc.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                result = _run_tool(fn.get("name", ""), args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(result, ensure_ascii=False, default=_json_default),
                })
            content, tool_calls, usage, reasoning = _chat_stream(messages, Config.DEEPSEEK_MODEL, tools=TOOLS)
        reply = _reply_from_msg({"content": content, "reasoning_content": reasoning})
        # Red de seguridad: si el stream vino vacío (pico raro del proveedor)
        # y no hubo tool_calls, reintentar una vez sin streaming.
        if not reply and not tool_calls:
            try:
                data = _chat_completion(messages, Config.DEEPSEEK_MODEL)
                msg = data["choices"][0]["message"]
                reply = _reply_from_msg(msg)
                reasoning = msg.get("reasoning_content") or reasoning
                usage = data.get("usage", {}) or usage
            except Exception:
                pass
        if not reply:
            return {"error": "El cerebro no generó texto. Prueba otra vez."}
        if on_fragment:
            on_fragment(reply)  # último aviso con el texto completo
        cost = (
            usage.get("prompt_cache_hit_tokens", 0) / 1e6 * Config.PRICE_CACHE
            + usage.get("prompt_tokens", 0) / 1e6 * Config.PRICE_INPUT
            + usage.get("completion_tokens", 0) / 1e6 * Config.PRICE_OUTPUT
        )
        _history.append(("assistant", reply, reasoning))
        return _tal_vez_anotar(text, {"reply": reply, "cost_usd": round(cost, 4), "elapsed_s": round(time.time() - t0, 1)})
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        roles = [m.get("role") for m in messages]
        if e.code != 400:
            return {"error": f"DeepSeek HTTP {e.code}: {body} — roles={roles}"}
        try:
            data = _chat_completion(messages, Config.DEEPSEEK_MODEL)
            msg = data["choices"][0]["message"]
            reply = _reply_from_msg(msg)
            if on_fragment:
                on_fragment(reply)
            _history.append(("assistant", reply, msg.get("reasoning_content") or ""))
            return _tal_vez_anotar(text, {"reply": reply, "cost_usd": 0, "elapsed_s": round(time.time() - t0, 1)})
        except Exception as e2:
            return {"error": f"DeepSeek HTTP {e.code} (sin tools: {e2}) — {body} — roles={roles}"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------- visión

def vision(image_bytes: bytes, mime: str = "image/jpeg", question: str = "Describe la escena"):
    """Analiza una imagen (webcam) con un modelo de visión vía OpenRouter."""
    if not Config.OPENROUTER_API_KEY:
        return {"error": "Sin OPENROUTER_API_KEY"}
    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": Config.VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": f"{question}. Responde en español, breve."},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        "max_tokens": 500,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return {"description": data["choices"][0]["message"]["content"].strip()}
    except urllib.error.HTTPError as e:
        return {"error": f"OpenRouter HTTP {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return {"error": str(e)}
