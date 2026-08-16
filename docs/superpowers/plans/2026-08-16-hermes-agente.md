# Cerebro Hermes (OpenRouter + DeepSeek) — Plan de implementación

> **Para agentes:** SUB-SKILL OBLIGATORIA: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar tarea a tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** JARVIS deja de hablar *directo* con DeepSeek. El HUD (Electron + voz + panel) se queda igual; el chat pasa por **Hermes Agent**, que hace el bucle de acciones (buscar, recordar, Spotify, skills) y llama a DeepSeek por la **misma API de OpenRouter** que ya usamos.

**Arquitectura:** Hermes corre en local (`127.0.0.1:8642`, API compatible con OpenAI). `brain.py` se convierte en un cliente fino: manda el texto del señor y espera la respuesta *final* (Hermes ya ejecutó las tools). Las herramientas propias de JARVIS (Spotify, noticias, memoria) se exponen a Hermes por MCP. Si Hermes no está arrancado, se cae al cerebro actual para no dejar mudo el panel.

**Stack:** Hermes Agent (nativo Windows) · OpenRouter · `deepseek/deepseek-v4-flash` · FastAPI · MCP · Electron

**Spec:** este documento. No hay spec aparte.

---

## Decisión: Hermes, no OpenClaw

Los dos son *harnesses* de agente (el modelo sigue siendo DeepSeek). No sustituyen a OpenRouter: **pasan por él**.

| | Hermes Agent (Nous) | OpenClaw |
|---|---|---|
| Encaje con este proyecto | Alto | Medio |
| Windows nativo | Sí (PowerShell, `%LOCALAPPDATA%\hermes`) | Sí, pero el núcleo es un gateway multi-canal |
| API para el HUD | `/v1/chat/completions` en `:8642` (encaja con `brain.py`) | HTTP OpenAI opcional en `:18789` (apagado por defecto) + WebSocket propio |
| Memoria / se vuelve más listo | Memoria persistente + skills que el propio agente crea | Markdown + skills humanas (ClawHub, 44k) |
| Tools de serie | Web, browser, visión, cron, 40+ | Skills ClawHub + tools del gateway |
| Modelo que ya usamos | `deepseek/deepseek-v4-flash` es de los más usados en Hermes/OpenRouter | Cualquiera vía OpenRouter |
| Lo que JARVIS ya tiene | Panel + voz + Electron | OpenClaw brilla en WhatsApp/Telegram/Discord — **no lo necesitamos** |

**Recomendación: Hermes.** OpenClaw es un *router de canales*. JARVIS ya es el canal (HUD + wake word + Fish). Lo que falta es un *cerebro que actúe y recuerde*, que es exactamente Hermes. Además DeepSeek V4 Flash ya está batallado ahí: no es un experimento.

OpenClaw queda como plan B si más adelante quieres el mismo JARVIS por Telegram/WhatsApp.

---

## Cómo queda el flujo

Hoy:

```
HUD / voz  →  FastAPI /api/chat  →  brain.py (bucle de 4 tools)  →  OpenRouter  →  DeepSeek
```

Después:

```
HUD / voz  →  FastAPI /api/chat  →  brain.py (cliente fino)
                                      ↓  http://127.0.0.1:8642/v1
                                   Hermes Agent  (bucle de acciones + memoria + skills)
                                      ↓  misma clave OpenRouter
                                   DeepSeek V4 Flash
```

Hermes ejecuta las tools **en el servidor**. El cliente **no** recibe `tool_calls` pendientes: recibe el texto final. Por eso se puede tirar el bucle de tools de `chat()` / `chat_stream()` cuando Hermes está activo.

La voz (Fish, wake Vosk, barge-in) no se toca. Solo cambia de dónde sale el `reply`.

---

## Qué se conserva y qué se mueve

**Se queda en JARVIS (no lo reescribimos):**
- Electron, HUD, Ajustes, login kiosco
- Fish TTS, STT Whisper, wake Vosk, barge-in
- `memoria/recuerdos.md`, `preferencias.md`, `estado.md` y las reglas del señor
- Spotify (`app/services.py`), noticias RSS, métricas, visión OpenRouter
- El prompt de mayordomo + prioridad de preferencias

**Pasa a Hermes:**
- El bucle “piensa → llama tool → observa → responde”
- Búsqueda web / browser (más capaz que el RSS actual; el RSS se queda como tool MCP por si acaso)
- Skills reutilizables (p.ej. “cómo controla Spotify este señor”)
- Memoria de sesión larga de Hermes (complementa, no sustituye, `memoria/*.md`)

**No se da a Hermes (seguridad):**
- Terminal libre del PC (apagado en el perfil JARVIS)
- Escritura fuera de `memoria/`
- La clave OpenRouter no sale del `.env` de Hermes / JARVIS; el HUD nunca la ve

---

## Seguridad (por qué importa)

Hermes, de serie, puede ejecutar terminal y tocar ficheros con los permisos de tu usuario. En un asistente de voz eso es peligroso: un wake word mal oído + “borra esto” no puede acabar en PowerShell.

Perfil JARVIS:
- Bind solo `127.0.0.1`
- `API_SERVER_KEY` obligatorio
- Toolsets: `web` + MCP `jarvis` + memoria Hermes. **Sin `terminal`.**
- Aprobaciones: `manual` o `smart` si más adelante se enciende alguna tool peligrosa
- Fallback: si el gateway no responde, cerebro viejo (sin acciones extra), no un Hermes “a ciegas”

---

## Ficheros

| Fichero | Rol |
|---|---|
| `app/config.py` | `HERMES_URL`, `HERMES_KEY`, `HERMES_ENABLED`, timeouts |
| `app/brain.py` | Si Hermes está vivo → cliente fino. Si no → cerebro actual |
| `app/hermes_client.py` | HTTP OpenAI a `:8642` (sync + stream). Ignora eventos `hermes.tool.progress` para el TTS |
| `app/mcp_jarvis.py` | Servidor MCP stdio: `spotify`, `buscar_noticias`, `recordar`, `olvidar`, `estado_sistema` |
| `hermes/config.yaml` | Plantilla del perfil (modelo OpenRouter, toolsets, MCP) |
| `hermes/SOUL.md` | Identidad JARVIS para Hermes (mayordomo + reglas del señor) |
| `start.bat` | Arranca `hermes gateway` si existe, luego Electron |
| `tests/test_hermes_client.py` | Cliente: parseo SSE, fallback, strip de tool-progress |
| `tests/test_mcp_jarvis.py` | Tools MCP delegan en las funciones ya existentes |
| `.env.example` | Nuevas vars, sin secretos |

No se mete el runtime de Hermes en el repo (`%LOCALAPPDATA%\hermes` es del usuario).

---

## Restricciones

- Español de España en textos visibles. Comentarios en español, UTF-8 sin BOM.
- **No arrancar el servidor 8080** durante la implementación; tests y, si hace falta, puerto 8095.
- La clave sigue siendo la de OpenRouter (`DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY`). Hermes usa `OPENROUTER_API_KEY` en `%LOCALAPPDATA%\hermes\.env`.
- Modelo: `deepseek/deepseek-v4-flash` (el mismo slug de ahora).
- No romper voz: el stream de Hermes puede tardar más (bucle de tools). Timeout 180 s. El TTS solo habla el texto final, no los “buscando…” internos.
- Commits en español, conventional commits, a nombre de Poxi, sin rastro de IA. **No push.** No commitear `%LOCALAPPDATA%\hermes` ni claves.

---

### Tarea 1: Cliente Hermes (tests primero)

**Ficheros:**
- Crear: `app/hermes_client.py`
- Test: `tests/test_hermes_client.py`

Hermes habla OpenAI Chat Completions. El stream mete eventos extra `hermes.tool.progress` que **no** deben ir a Fish.

- [ ] **Paso 1: Test que falla**

Crear `tests/test_hermes_client.py`:

```python
"""El cliente Hermes solo habla texto final, nunca tool-progress."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.hermes_client import parse_sse_text, hermes_disponible


def test_parse_sse_ignora_tool_progress():
    raw = (
        "data: " + json.dumps({
            "choices": [{"delta": {"content": "Señor, "}}]
        }) + "\n\n"
        "event: hermes.tool.progress\n"
        "data: " + json.dumps({"tool": "web_search", "status": "start"}) + "\n\n"
        "data: " + json.dumps({
            "choices": [{"delta": {"content": "hecho."}}]
        }) + "\n\n"
        "data: [DONE]\n\n"
    )
    text, usage = parse_sse_text(raw)
    assert text == "Señor, hecho."
    assert "web_search" not in text


def test_hermes_caido_devuelve_false(monkeypatch):
    class Fake:
        def __enter__(self):
            raise OSError("connection refused")
        def __exit__(self, *a):
            return False
    import app.hermes_client as hc
    monkeypatch.setattr(hc, "_probe", lambda: (_ for _ in ()).throw(OSError("no")))
    assert hermes_disponible() is False


if __name__ == "__main__":
    test_parse_sse_ignora_tool_progress()
    print("OK")
```

Si el proyecto no usa pytest/`monkeypatch`, el segundo test puede comprobar solo `parse_sse_text` y un `hermes_disponible()` con URL inventada (`http://127.0.0.1:1`).

- [ ] **Paso 2: Correr el test y ver que falla**

```bat
venv\Scripts\python.exe tests\test_hermes_client.py
```

Esperado: `ImportError: cannot import name 'parse_sse_text'`

- [ ] **Paso 3: Implementación mínima**

Crear `app/hermes_client.py`:

```python
"""Cliente fino del gateway Hermes (OpenAI-compatible en localhost)."""
import json
import urllib.error
import urllib.request

from .config import Config


def _headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.HERMES_KEY}",
    }


def hermes_disponible() -> bool:
    url = (Config.HERMES_URL or "").rstrip("/")
    if not url or not Config.HERMES_ENABLED:
        return False
    try:
        req = urllib.request.Request(url + "/models", headers=_headers(), method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


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
        if msg.get("content") and not delta:
            parts.append(msg["content"])
    return "".join(parts), usage


def chat(messages, timeout=180, stream=False):
    """POST /chat/completions. Sin tools: Hermes las corre dentro."""
    url = Config.HERMES_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": Config.HERMES_MODEL,
        "messages": messages,
        "stream": stream,
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if stream:
            raw = r.read().decode("utf-8", "replace")
            text, usage = parse_sse_text(raw)
            return {"reply": text, "usage": usage}
        data = json.loads(r.read())
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        return {
            "reply": (msg.get("content") or "").strip(),
            "usage": data.get("usage") or {},
        }
```

Añadir en `app/config.py` junto al bloque DeepSeek:

```python
    # --- Hermes (agente local; el LLM sigue siendo OpenRouter/DeepSeek) ---
    HERMES_ENABLED = _env("HERMES_ENABLED", "1") == "1"
    HERMES_URL = _env("HERMES_URL", "http://127.0.0.1:8642/v1")
    HERMES_KEY = _env("HERMES_KEY", "")
    HERMES_MODEL = _env("HERMES_MODEL", "hermes-agent")
```

El `model` que se manda a `:8642` es **`hermes-agent`**, no el slug de DeepSeek. DeepSeek se configura *dentro* de Hermes (`config.yaml`).

- [ ] **Paso 4: Correr el test**

```bat
venv\Scripts\python.exe tests\test_hermes_client.py
```

Esperado: `OK`

- [ ] **Paso 5: Commit** (cuando Poxi lo pida)

```
feat: cliente HTTP para el gateway Hermes
```

---

### Tarea 2: `brain.py` usa Hermes si está vivo

**Ficheros:**
- Modificar: `app/brain.py` (`chat`, `chat_stream`)
- Test: `tests/test_brain_hermes.py`

Contrato: `chat(text, context)` y `chat_stream(...)` siguen devolviendo el mismo dict (`reply`, `cost_usd`, `error`). El HUD no cambia.

- [ ] **Paso 1: Test que falla**

```python
"""Si Hermes esta arriba, brain no llama a DeepSeek directo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import brain


def test_chat_por_hermes(monkeypatch):
    monkeypatch.setattr("app.hermes_client.hermes_disponible", lambda: True)
    monkeypatch.setattr(
        "app.hermes_client.chat",
        lambda messages, timeout=180, stream=False: {
            "reply": "A la orden.",
            "usage": {"prompt_tokens": 10, "completion_tokens": 4},
        },
    )
    called = {"deepseek": False}

    def boom(*a, **k):
        called["deepseek"] = True
        raise AssertionError("no deberia llamar a DeepSeek")

    monkeypatch.setattr(brain, "_chat_completion", boom)
    out = brain.chat("hola")
    assert called["deepseek"] is False
    assert out["reply"] == "A la orden."
```

Si no hay pytest, usar un stub manual de módulos. Lo importante: con Hermes “vivo”, `_chat_completion` no se toca.

- [ ] **Paso 2: Encaminar `chat` y `chat_stream`**

Al inicio de `chat()` y `chat_stream()`, después de comprobar que hay cerebro:

```python
from . import hermes_client

def _mensajes_base(text, context, voice_mode=False):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": bloque_sistema_memoria()},
    ]
    if context:
        messages.append({
            "role": "system",
            "content": "Estado actual del sistema (JSON): "
            + json.dumps(context, ensure_ascii=False)[:2000],
        })
    if voice_mode:
        messages.append({
            "role": "system",
            "content": "MODO VOZ: responde en 1 o 2 frases cortas y directas.",
        })
    hist = list(_history)[-8:] if voice_mode else list(_history)
    messages.extend(_hist_msg(r, c, rc) for r, c, rc in hist)
    messages.append({"role": "user", "content": text})
    return messages


def chat(text, context=None):
    if hermes_client.hermes_disponible():
        messages = _mensajes_base(text, context)
        _history.append(("user", text, ""))
        try:
            out = hermes_client.chat(messages, timeout=180, stream=False)
        except Exception as e:
            return {"error": f"Hermes: {e}"}
        reply = _strip_urls((out.get("reply") or "").strip())
        _history.append(("assistant", reply, ""))
        return {"reply": reply, "usage": out.get("usage") or {}}
    # ... cerebro DeepSeek actual intacto ...
```

`chat_stream`: igual, con `stream=True`. Si Hermes soporta SSE token a token, ir llamando `on_fragment` con el texto acumulado **solo de `delta.content`**. Si el gateway no fragmenta hasta el final, una sola llamada a `on_fragment` al terminar (la voz ya sabe esperar).

Timeout: 180 s (el bucle de tools tarda más que un chat seco).

- [ ] **Paso 3: Fallback**

Si `hermes_disponible()` es False **o** el POST lanza error de conexión: usar el `chat()` viejo. Log interno: `"cerebro: fallback DeepSeek (Hermes caido)"`. El señor no tiene que ver un stack.

- [ ] **Paso 4: Tests**

```bat
venv\Scripts\python.exe tests\test_brain_hermes.py
venv\Scripts\python.exe tests\test_brain_reply.py
venv\Scripts\python.exe tests\test_reglas.py
```

Esperado: `OK` en los tres.

- [ ] **Paso 5: Commit**

```
feat: el chat usa Hermes cuando el gateway esta vivo
```

---

### Tarea 3: Instalar Hermes en el PC y enganchar OpenRouter

Esto lo hace Poxi una vez (o el agente en su máquina). No va al git salvo la plantilla.

- [ ] **Paso 1: Instalar nativo Windows** (PowerShell, sin admin)

```powershell
iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
```

Cierra y abre la terminal. `hermes` tiene que estar en PATH. Datos en `%LOCALAPPDATA%\hermes\`.

No usar WSL para JARVIS: el HUD es Windows, Spotify es Windows, el micro es Windows. WSL solo añade el lío `localhost` ↔ VM.

- [ ] **Paso 2: Clave OpenRouter (la misma de ahora)**

En `%LOCALAPPDATA%\hermes\.env`:

```
OPENROUTER_API_KEY=sk-or-...   # la misma que DEEPSEEK_API_KEY del .env de JARVIS
API_SERVER_ENABLED=true
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
API_SERVER_KEY=  # generar uno local, copiarlo a JARVIS_HERMES_KEY / HERMES_KEY
```

En `%LOCALAPPDATA%\hermes\config.yaml`:

```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-v4-flash

agent:
  disabled_toolsets:
    - terminal

platform_toolsets:
  api:
    - web
    - memory
    - skills
```

El slug `deepseek/deepseek-v4-flash` es el que ya está en `.env.example` de JARVIS. Hermes lo documenta como modelo rápido/barato en OpenRouter.

- [ ] **Paso 3: Identidad JARVIS**

Hermes carga la identidad **solo** desde `%LOCALAPPDATA%\hermes\SOUL.md` (`HERMES_HOME`). No lee un `SOUL.md` del repo. El repo guarda una copia en `hermes/SOUL.md` para copiarla ahí (Hermes no pisa un SOUL ya editado). Contenido base:

```markdown
Eres JARVIS, el asistente personal del señor. Español de España.
Estilo mayordomo elegante, breve, directo. Tratale de señor
SALVO que PREFERENCIAS digan otra cosa: esas reglas pisan el tono.
No markdown, no emojis, no URLs.
Las etiquetas Fish [calm] [happy] ... al inicio de frase son para la voz, el señor no las lee.
Si te piden musica, noticias o recordar algo, USA las tools MCP jarvis
(spotify, buscar_noticias, recordar, olvidar) en vez de inventar.
```

El `SYSTEM_PROMPT` de `brain.py` se sigue inyectando en cada request (reglas del señor incluidas). SOUL.md es el ancla por si Hermes arranca un job cron sin pasar por el HUD.

- [ ] **Paso 4: Probar el gateway solo**

```bat
hermes gateway
```

En otra consola:

```bat
curl http://127.0.0.1:8642/v1/models -H "Authorization: Bearer TU_HERMES_KEY"
```

Esperado: JSON con `hermes-agent`. Luego un POST de “di hola en una frase”. Tiene que salir texto, cobrado en OpenRouter (mismo dashboard de siempre).

- [ ] **Paso 5: Vars en el `.env` de JARVIS** (Ajustes del panel o a mano)

```
HERMES_ENABLED=1
HERMES_URL=http://127.0.0.1:8642/v1
HERMES_KEY=  # el mismo API_SERVER_KEY
HERMES_MODEL=hermes-agent
```

Añadir las mismas claves a `app/main.py` en el diccionario de Ajustes (junto a `DEEPSEEK_*`) para poder verlas/editarlas en el panel.

- [ ] **Paso 6: Commit de plantillas** (no el `.env` real)

```
chore: plantilla Hermes (SOUL + config) y vars de Ajustes
```

---

### Tarea 4: MCP `jarvis` (Spotify, noticias, memoria)

Hermes ya busca en la web. Lo que **no** tiene es Spotify de este PC ni los 3 markdown de `memoria/`. Se lo damos por MCP stdio.

**Ficheros:**
- Crear: `app/mcp_jarvis.py`
- Test: `tests/test_mcp_jarvis.py`
- Modificar: plantilla `hermes/config.yaml` → `mcp_servers.jarvis`

- [ ] **Paso 1: Tests que fallan** — las tools delegan, no reimplementan

```python
"""MCP jarvis llama a las funciones que ya existen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mcp_jarvis import dispatch


def test_recordar_preferencias(tmp_path, monkeypatch):
    # stub append_memory
    seen = {}
    monkeypatch.setattr(
        "app.brain.append_memory",
        lambda cat, nota: seen.update(cat=cat, nota=nota) or True,
    )
    out = dispatch("recordar", {"categoria": "preferencias", "nota": "si te insulto, igual"})
    assert out["ok"] is True
    assert seen["cat"] == "preferencias"


def test_tool_desconocida():
    out = dispatch("format_c", {})
    assert out["ok"] is False
```

- [ ] **Paso 2: `dispatch` mínimo**

Reutilizar `_run_tool` de `app/brain.py` (noticias, recordar, olvidar, spotify) más una tool `estado_sistema` que llame a `services.smart_context` / métricas. **Whitelist.** Nada de shell.

Interfaz MCP: stdio JSON-RPC (`tools/list`, `tools/call`). Hermes lanza:

```
venv\Scripts\python.exe -m app.mcp_jarvis
```

con cwd = raíz del repo. Implementación propia en `app/mcp_jarvis.py` (sin paquete `mcp` extra). Si el handshake oficial exige más de ~150 líneas, entonces sí se añade `mcp` a `requirements.txt` — no antes.

Tools:

| Nombre | Args | Implementación |
|---|---|---|
| `buscar_noticias` | `tema`, `dias?` | `_run_tool` actual |
| `recordar` | `categoria`, `nota` | `_run_tool` |
| `olvidar` | `texto` | `_run_tool` |
| `spotify` | `action`, `query?`, `device?` | `_run_tool` |
| `estado_sistema` | `pregunta` | `services.smart_context(pregunta)` |

- [ ] **Paso 3: Registrar en Hermes**

En la plantilla `hermes/config.yaml`:

```yaml
mcp_servers:
  jarvis:
    command: "F:\\jarvismejorao\\venv\\Scripts\\python.exe"
    args: ["-m", "app.mcp_jarvis"]
    cwd: "F:\\jarvismejorao"
    enabled: true
```

La ruta se documenta; `start.bat` o un `hermes\sync-config.ps1` puede reescribir `cwd`/`command` al path real del repo.

- [ ] **Paso 4: Probar**

Con el gateway arriba, desde el HUD: “pon música” y “recuerda que si te insulto me contestas igual”. Tiene que:
1. Llamar MCP (log de Hermes)
2. Escribir en `memoria/preferencias.md`
3. Contestar en voz JARVIS, no en inglés de agente genérico

- [ ] **Paso 5: Commit**

```
feat: MCP jarvis para Spotify, noticias y memoria
```

---

### Tarea 5: `start.bat` arranca el gateway

Si Hermes no está, JARVIS sigue abriéndose (fallback DeepSeek). Si está, el gateway tiene que vivir **antes** de Electron.

- [ ] **Paso 1: En `start.bat`, después de `:cerrar_instancias`**

```bat
rem Hermes en 127.0.0.1:8642 (acciones). Si no esta instalado, el cerebro viejo aguanta.
if exist "%LOCALAPPDATA%\hermes\hermes-agent\bin\hermes.exe" (
  echo Arrancando Hermes...
  start "JARVIS-Hermes" /MIN "%LOCALAPPDATA%\hermes\hermes-agent\bin\hermes.exe" gateway
  timeout /t 2 /nobreak >nul
)
```

Al cerrar JARVIS no hace falta matar Hermes sí o sí (el siguiente arranque reutiliza `:8642`). Si el puerto está ocupado por un gateway viejo, no lanzar otro.

En `:cerrar_instancias` **no** matar `hermes.exe` por defecto (tarda en subir). Opcional: comprobar `127.0.0.1:8642` con PowerShell y solo lanzar si no hay listen.

- [ ] **Paso 2: HUD — estado del cerebro**

En el panel (fila de saldo / proxy), una línea **CEREBRO**: `Hermes` | `DeepSeek (fallback)`. Endpoint interno `GET /api/cerebro` que devuelve `{backend: "hermes"|"deepseek", hermes: bool}`.

No rediseñar el HUD; una fila más en la consola de sistema.

- [ ] **Paso 3: Commit**

```
feat: start.bat lanza Hermes y el panel muestra el backend
```

---

### Tarea 6: Voz y timeouts (regresión)

El bucle de agente alarga la primera frase. Fish no puede leer basura de tools.

- [ ] Comprobar que `voice.voice_chat` sigue llamando `chat_stream(..., voice_mode=True)`.
- [ ] `parse_sse_text` ya descarta `hermes.tool.progress`.
- [ ] Timeout de `_chat_stream` Hermes = 180 s; el de Fish se queda.
- [ ] Frase de espera: no inventar TTS de “estoy buscando” a no ser que el HUD lo pida después. Primera versión: silencio hasta el reply final (como ahora cuando DeepSeek tarda).
- [ ] Tests existentes: `tests/test_voice_norm.py`, `tests/test_wake.py` — no deben romper.

```bat
venv\Scripts\python.exe tests\test_voice_norm.py
venv\Scripts\python.exe tests\test_wake.py
venv\Scripts\python.exe tests\test_reglas.py
```

- [ ] **Commit**

```
fix: la voz espera el texto final de Hermes
```

---

### Tarea 7: Verificación en el PC (no “debería”)

Cerrar JARVIS. `start.bat`.

Checklist:

1. El panel abre. Fila CEREBRO = `Hermes`.
2. Texto: “qué hora es” → responde (estado_sistema o conocimiento).
3. “Recuerda: si te insulto, contéstame igual” → línea nueva en `memoria/preferencias.md`.
4. Insulto en el turno siguiente → tono de las reglas, no mayordomo ofendido.
5. “Busca noticias del Barça” → datos reales (web Hermes o RSS MCP), sin URLs en voz.
6. “Pon música” → tool Spotify, no “no puedo”.
7. 👂 Yarvis + orden corta → una transcripción + un chat + Fish. Sin bucle Whisper.
8. Quitar `hermes gateway` a mano → el panel sigue hablando por DeepSeek directo (fallback).
9. Gasto: aparece en OpenRouter (misma clave), no en api.deepseek.com.

Si 3, 4 o 6 fallan: no dar la tarea por hecha. Mirar log de Hermes (`%LOCALAPPDATA%\hermes\logs\`) y el de FastAPI.

---

## Fuera de alcance (a propósito)

- WhatsApp / Telegram / Discord (eso sería OpenClaw o el gateway de mensajería de Hermes; el HUD ya es el canal).
- Cambiar Fish, Vosk o el modelo de visión.
- Meter el runtime de Hermes en Electron / el instalador portable (el `.exe` se dispararía de peso). En el portable: documentar “hace falta Hermes instalado” o un `compilar.bat` que lo detecte.
- Terminal libre, browser autónomo con tu Chrome logueado, o skills de ClawHub sin revisar.
- Sustituir DeepSeek por Claude/GPT. El plan **fija** OpenRouter + `deepseek/deepseek-v4-flash`. Cambiar de modelo es una línea en `config.yaml` el día que quieras.

---

## Orden de ataque

1. Cliente + tests (Tarea 1)  
2. Switch en `brain.py` + fallback (Tarea 2)  
3. Instalar Hermes y OpenRouter en el PC (Tarea 3) — aquí se nota el salto  
4. MCP jarvis (Tarea 4) — aquí se nota “acciones de verdad”  
5. `start.bat` + indicador (Tarea 5)  
6. Voz / timeouts (Tarea 6)  
7. Checklist en el PC (Tarea 7)

Tareas 1–2 se pueden hacer **sin** Hermes instalado (mocks). A partir de la 3 hace falta el gateway en `localhost`.

---

## Cómo probar en desarrollo

No usar el 8080 de la app. Puerto 8095 + Hermes en 8642:

```bat
:: _dev.bat ya esta en gitignore
set HERMES_ENABLED=1
set HERMES_URL=http://127.0.0.1:8642/v1
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8095
```

Hermes en otra ventana: `hermes gateway`.
