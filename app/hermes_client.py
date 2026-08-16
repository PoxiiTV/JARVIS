"""Cliente fino del gateway Hermes (OpenAI-compatible en localhost)."""
import json
import re
import time
import urllib.error
import urllib.request

from .config import Config

# Hermes, si DeepSeek solo rellena el pensamiento interno, envuelve la
# respuesta real en este aviso en inglés con un ⚠️.
_ENVOLTORIO = re.compile(
    r"(?is)The model produced only internal reasoning.*?"
    r"which may contain the(?:\s+answer)?:\s*"
)


def texto_hablable(content: str, reasoning: str = "") -> str:
    """Quita el envoltorio de Hermes y usa el razonamiento si no hay texto."""
    text = (content or "").strip()
    thought = (reasoning or "").strip()
    m = _ENVOLTORIO.search(text)
    if m:
        text = text[m.end():].strip() or thought
    elif not text:
        text = thought
    return re.sub(r"^(?:⚠️|⚠)\s*", "", text).strip()

_probe = {"t": 0.0, "ok": False}


def _headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.HERMES_KEY}",
    }


def hermes_disponible() -> bool:
    url = (Config.HERMES_URL or "").rstrip("/")
    if not url or not Config.HERMES_ENABLED:
        return False
    now = time.time()
    ttl = 15 if _probe["ok"] else 4
    if now - _probe["t"] < ttl and _probe["t"]:
        return _probe["ok"]
    try:
        req = urllib.request.Request(url + "/models", headers=_headers(), method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            ok = 200 <= getattr(r, "status", 200) < 300
    except Exception:
        ok = False
    _probe["t"] = now
    _probe["ok"] = ok
    return ok


def parse_sse_text(raw: str):
    """Junta deltas de content. Ignora event: hermes.tool.progress."""
    parts = []
    usage = {}
    event = None
    for line in raw.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        if event == "hermes.tool.progress":
            event = None
            continue
        event = None
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
            parts.append(delta["content"])
        msg = choices[0].get("message") or {}
        if msg.get("content") and not delta.get("content"):
            parts.append(msg["content"])
    return "".join(parts), usage


def texto_progreso(info):
    """Frase corta para la consola. No se habla: es estado, no respuesta."""
    if not isinstance(info, dict):
        return "Hermes trabaja…"
    name = str(
        info.get("tool")
        or info.get("name")
        or info.get("tool_name")
        or (info.get("function") or {}).get("name")
        or ""
    ).lower()
    if any(x in name for x in ("web", "search", "browser", "http", "noticia")):
        return "Consultando la red…"
    if "spotify" in name:
        return "Spotify…"
    if any(x in name for x in ("terminal", "shell", "bash", "exec")):
        return "Orden en el portátil…"
    if name:
        return "Hermes: " + name
    return "Hermes trabaja…"


def iter_sse_text(response, on_progress=None):
    """Lee un stream HTTP SSE. Yield (texto_acumulado, usage) en cada delta."""
    parts = []
    usage = {}
    event = None
    buf = b""
    while True:
        chunk = response.read(256)
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            raw_line, buf = buf.split(b"\n", 1)
            line = raw_line.decode("utf-8", "replace").strip()
            if line.startswith("event:"):
                event = line[6:].strip()
                continue
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                yield "".join(parts), usage
                return
            if event == "hermes.tool.progress":
                if on_progress:
                    try:
                        on_progress(json.loads(data) if data else {})
                    except Exception:
                        on_progress({"raw": data})
                event = None
                continue
            event = None
            try:
                obj = json.loads(data)
            except Exception:
                continue
            if obj.get("usage"):
                usage = obj["usage"]
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            if delta.get("content"):
                parts.append(delta["content"])
                yield "".join(parts), usage
    yield "".join(parts), usage


def chat(messages, timeout=180, stream=False, on_fragment=None, on_progress=None):
    """POST /chat/completions. Sin tools: Hermes las corre dentro."""
    url = Config.HERMES_URL.rstrip("/") + "/chat/completions"
    usar_stream = bool(stream or on_fragment or on_progress)
    payload = {
        "model": Config.HERMES_MODEL,
        "messages": messages,
        "stream": usar_stream,
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if usar_stream:
            text, usage = "", {}
            for text, usage in iter_sse_text(r, on_progress=on_progress):
                reply = texto_hablable(text)
                if on_fragment:
                    on_fragment(reply)
            return {"reply": texto_hablable(text), "usage": usage}
        data = json.loads(r.read())
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        return {
            "reply": texto_hablable(
                msg.get("content") or "",
                msg.get("reasoning_content") or msg.get("reasoning") or "",
            ),
            "usage": data.get("usage") or {},
        }
