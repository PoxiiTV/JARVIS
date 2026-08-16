# JARVIS Iron Man — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que en 90 segundos el señor sienta que tiene un mayordomo, no un chatbot con glow: oye, corta, actúa en la máquina correcta, enseña el recibo y habla como JARVIS.

**Architecture:** Windows = oído, voz, HUD, Spotify, Tuya, visión. Linux = manos (archivos, browser, terminal, cron). DeepSeek = charla rápida. El HUD es un puesto de mando con estados (espera / oye / piensa / actúa / habla / fallo), no un log de chat. En pantalla el nombre es siempre JARVIS; Vosk sigue oyendo Yarvis.

**Tech Stack:** FastAPI · Electron 33 · Three.js · Vosk + Whisper · Fish Audio (`prosody.volume`) · Hermes Agent LAN (`192.168.1.100:8642`) · DeepSeek v4 Flash / OpenRouter · MCP `app/mcp_jarvis.py`

**Spec:** este documento. Decisiones cerradas 2026-08-16.

---

## Norte — mejor que la película, en un PC de verdad

La peli hace trampa: hologramas volumétricos, un reactor en el pecho, cero latencia de red. Nosotros no. **Ganamos en lo que Stark no tenía:** dos máquinas reales, memoria tuya, claves tuyas, Spotify, volumen por voz, y un mayordomo que **nunca miente**.

Iron Man de mentira: partículas, «procesando…», un HTML inventado en `/home/...`.  
Iron Man de verdad: pulso al oírte, primera frase en cuanto existe, archivo en el Escritorio del Linux, recibo en el Núcleo, «Hermes no responde» una sola vez.

### Guion de 90 segundos (esto es el producto)

1. Se abre el HUD. El reactor está vivo. Briefing: hora, grados en Alcoy, Hermes ok. **Nada de «JARVIS en línea».**
2. «Yarvis.» Pulso cian. «Te escucho.» Cero voz de relleno.
3. «Cómo estás.» < 5 s. Fish. Núcleo en habla. DeepSeek, no el portátil.
4. «Crea un html de hola mundo estilo Apple en el escritorio.» Máquina = portátil. Consola: «Orden en el portátil…». Voz callada. Recibo: `Escritorio, hola-mundo.html`. Primera frase hablada sin esperar al párrafo entero. El archivo está en `~/Escritorio`, no en una carpeta nueva.
5. Hablas encima → la voz se corta al instante.
6. Selector DeepSeek → la misma orden de HTML **no** va a Hermes. Auto otra vez.
7. Si el gateway está caído: una frase, charla sigue aquí.

Si ese guion falla, el resto del plan es decorado.

### Presupuesto de latencia (techos, no deseos)

| Momento | Techo | Si se pasa |
|---|---|---|
| Wake → «Te escucho» (log + pulso) | 300 ms | El oído está mal o el WS no está abierto |
| Charla Auto → primera onda de Fish | 5 s | DeepSeek o red; no mandar a Hermes |
| Acción Hermes → primer `t=status` | 1 s | El cliente no está streameando |
| Acción Hermes → primera frase hablada | 8 s | Hablar el trozo estable; no esperar al done |
| Barge-in → silencio | 200 ms | `cortarVoz` no está en el VAD |
| Recibo en Núcleo | junto al `done` | Parser RECIBO o tool muda |

El HUD **nunca** cuenta «14s» en voz alta. El tiempo es del reactor (thinking), no del mayordomo.

### Máquina de estados del HUD

Un solo sitio pinta el mundo. Nombres fijos; el CSS y el 3D escuchan la clase de `#hud-ui`:

| Estado | Clase | Reactor | Consola | Voz |
|---|---|---|---|---|
| espera | *(nada)* | giro lento | — | no |
| oye | `ack-pulse` | flash | Te escucho | no |
| piensa | `thinking` | glow alto | status (Hermes… / Respondiendo…) | no |
| actúa fuera | `remote thinking` | glow frío | Orden en el portátil | no |
| habla | `speaking` | pulso al beat | reply | Fish |
| fallo | `bad` | rojo suave 1,2 s | error honesto | una frase, sin números inventados |

Prohibido: dos voces a la vez, status hablado, 3D apagado, «En ello, señor. 12s.»

### Fallos diseñados (también son JARVIS)

| Qué pasa | Qué hace |
|---|---|
| Hermes caído (Auto) | Una frase. Charla local. Recibo vacío. Máquina = este PC. |
| Hermes caído (forzado) | Error claro. No fingir el archivo. |
| Fish caído | Álvaro, sin anunciar un motor. Si también cae, texto en consola. |
| Tool fail | `RECIBO: fail`. Voz: «No está en el escritorio.» Cero ruta inventada. |
| Wake sin orden | «Te oí, pero no la orden.» No llama al cerebro. |
| Visión sin cámara | «No veo la cámara.» No llama a OpenRouter vacío. |

### Personalidad (una página)

Español de España. Señor, salvo que preferencias pisen. Breve. Útil. Sin markdown, sin URLs, sin emojis. Una etiqueta Fish por turno. No pide permiso para hacer lo que ya puede. No se disculpa con datos nuevos. Las rutas se dicen en palabras: «en el escritorio, hola html».

---

## 0. Biblia — no se discute en implementación

Estas reglas pisan cualquier idea «más Iron Man» que las rompa.

1. **Este PC no escribe archivos.** Escritorio = `xdg-user-dir DESKTOP` en Linux (`~/Escritorio`). Nunca `mkdir escritorio`. Nunca `~/Desktop` si xdg apunta a otra.
2. **Semáforo por defecto (Auto):** charla (`cómo estás`, hora, hola) → DeepSeek aquí. Acciones (archivos, ping, navegador, terminal) → Hermes. Spotify y Tuya → este Windows.
3. **Selector Ajustes** `CEREBRO=auto|hermes|deepseek` ya existe. No se sustituye: se respeta en TODOS los sitios que hoy miran solo `necesita_hermes`.
4. **Fish es la voz.** No se reactivan XTTS / CosyVoice / F5 como motor principal. Álvaro/Google siguen de reserva.
5. **El 3D no se apaga** por FPS. No vuelve el «Modo 3D desactivado».
6. **Nunca inventar resultados de tools.** Si no hay ok de tool, se dice. Una disculpa no trae números nuevos.
7. **El TTS no narra el progreso.** «Consultando la red…» es consola/HUD, no voz. La voz solo dice la respuesta final (o la primera frase estable, Fase 1).
8. **No arrancar el servidor 8080** durante la implementación. Tests con `venv\Scripts\python.exe tests\...`. Dev, si hace falta, puerto **8095** (`_dev.bat`).
9. **Commits** en español, conventional commits, a nombre de Poxi, sin rastro de IA. Push **solo** si el señor lo pide. No commitear `.env`, `venv/`, `models/`, `dist-electron/`.
10. **Fuera de alcance (YAGNI):** WhatsApp, fútbol API, Docker en el chat, escribir en el escritorio de Windows, OpenClaw, modelos caros por defecto, rediseñar el HUD a React.

**Qué es «nivel Iron Man o mejor» aquí (medible), no CGI:**

| Película | Aquí, de verdad |
|---|---|
| Siempre oye | Wake Vosk + escucha ON al abrir (ya). Barge-in que CORTA la voz (Fase 1). |
| Responde al instante | Charla < 5 s. Primera frase hablada de una acción Hermes < 8 s con stream. |
| No miente | Recibos de tool en HUD. Cero «ya lo creé» sin ok. |
| Overlay de datos | Tarjetas vivas: Hermes, Spotify, tiempo, recibo. Núcleo 3D reacciona. |
| Mayordomo | SOUL + emociones Fish + saludo útil, no «JARVIS en línea». |
| Hace cosas | Hermes en Linux con xdg, browser, terminal. Este PC: Spotify + Tuya + «en este PC» explícito. |
| Mejor que la peli | Memoria persistente tuya, claves tuyas, dos máquinas reales, volumen por voz. |

Si una tarea no mueve una fila de esa tabla, no entra en este plan.

---

## 1. Qué hay hoy (estado real, 2026-08-16)

```
Oído Vosk ──► Whisper (large-v3-turbo) ──► /api/chat/stream ──┬── Spotify / Tuya local
                                             ├── DeepSeek (charla / noticias / memoria)
                                             └── Hermes Linux (acciones) ── tools + MCP jarvis
HUD Electron 8080 ◄── Fish TTS ◄── reply final
```

**Ya funciona y se conserva:** selector Auto/Hermes/DeepSeek; volumen Fish por voz (`FISH_VOLUME` −20..20 dB); 3D siempre on; `quiere_hermes` + sticky de reproche; prompt xdg; wake 0,5 s; stream NDJSON de progreso; MCP Spotify/noticias/memoria; Tuya atajo Windows (`app/tuya.py`); Whisper `large-v3-turbo` + beam 3 (Ajustes → Oído, reiniciar); HUD `nombreHud()` (nunca Yarvis/Garbis en pantalla). No volver a poner `initial_prompt` de Whisper solo de luces.

**Hoy rompe la ilusión (orden de dolor):**

1. `app/static/index.html` ~2450 líneas: chat, 3D, wake, ajustes, Spotify, visión mezclados. Cada arreglo toca una mina.
2. `/api/chat/stream` anuncia `"Hermes…"` con `necesita_hermes`, no `quiere_hermes` → el selector forzado miente en consola.
3. La voz espera al `done`. Hermes de 20 s = silencio + «En ello, señor. 12s.»
4. `playAck()` está vacío: no hay pulso de «te oí» más que el log.
5. No hay barge-in: si hablas encima, la voz sigue.
6. Visión es un POST manual, no «mírame esto».
7. README ya describe Hermes+Fish (actualizado 2026-08-16). `electron/main.js` no debe seguir hablando de XTTS en el puerto 5002.
8. Recibos: el señor no ve QUÉ tool corrió ni en QUÉ máquina.
9. Memoria solo si dice «recuerda». JARVIS no aprende solo.
10. Cero proactividad: no avisa si Hermes cae (salvo un log), no hay briefing.

---

## 2. Arquitectura objetivo

```
                    ┌──────────── este Windows ────────────┐
  Mic ─ Vosk wake ─► FastAPI ─ router ─┬─ DeepSeek (charla)
       Whisper orden                   ├─ Spotify widget
       Barge-in corta TTS              ├─ Tuya (luces / IR)
                                       └─ Hermes LAN ─────────────┐
  HUD  ◄─ Fish (prosody speed+volume)                             │
       ◄─ recibos / tarjetas / núcleo 3D                          ▼
       ◄─ visión opcional (cámara de este PC)              portátil Linux
                                                           Hermes Agent
                                                           xdg DESKTOP
                                                           browser, shell
                                                           cron → aviso HUD
```

Contrato de mensajes del stream (ampliar, no romper):

```json
{"t":"status","msg":"Orden en el portátil…"}
{"t":"receipt","machine":"linux","tool":"write","ok":true,"detail":"Escritorio, hola-mundo.html"}
{"t":"text","reply":"[confident] Hecho, señor."}
{"t":"done","reply":"...","error":null,"elapsed_s":4.2}
```

`t=receipt` es NUEVO. El HUD lo pinta en la tarjeta Recibo. El TTS lo ignora.

Funciones canónicas (nombres que NO se renombran a mitad de plan):

| Símbolo | Dónde | Rol |
|---|---|---|
| `modo_cerebro()` | `app/brain.py` | `auto` \| `hermes` \| `deepseek` |
| `quiere_hermes(text)` | `app/brain.py` | ¿este turno va al portátil? |
| `necesita_hermes(text)` | `app/brain.py` | semáforo Auto (regex + sticky) |
| `estado_cerebro()` | `app/brain.py` | `{cerebro, cerebro_modo}` para el HUD |
| `fish_prosody()` | `app/voice.py` | `{speed, volume}` para Fish |
| `texto_progreso(info)` | `app/hermes_client.py` | frase de consola, no voz |

---

## 3. Ficheros

| Fichero | Responsabilidad en este plan |
|---|---|
| `app/brain.py` | Router, sticky, recibos, `quiere_hermes` en stream |
| `app/hermes_client.py` | SSE, progreso, extraer receipts si Hermes los manda |
| `app/voice.py` | Fish, barge-in hook, stream de primera frase |
| `app/wake.py` | Silencio, cancelar TTS (señal), timeout de orden |
| `app/main.py` | Stream NDJSON con `receipt`, visión, briefing, `quiere_hermes` |
| `app/mcp_jarvis.py` | Tools del HUD hacia Hermes (Spotify, memoria, estado) |
| `app/services.py` | Spotify, métricas, smart_context (sin fútbol) |
| `app/tuya.py` | Luces / IR / aire en este Windows (atajo, como Spotify) |
| `app/config.py` | Flags nuevos: `JARVIS_BRIEFING`, `JARVIS_BARGE_IN` |
| `hermes/SOUL.md` | Identidad + xdg + nunca inventar |
| `hermes/skills/escritorio.md` | Skill corta: siempre `xdg-user-dir DESKTOP` |
| `app/static/index.html` | Markup + boot + ajustes (se PARTE en Fase 3) |
| `app/static/hud-chat.js` | Chat, stream, barge-in, recibos (extraído) |
| `app/static/hud-three.js` | Reactor 3D (extraído) |
| `app/static/hud-wake.js` | Oído (extraído) |
| `app/static/hud.css` | Tarjetas, recibos, pulso |
| `electron/main.js` | Quitar mentiras XTTS; IPC mute/volumen de este PC |
| `README.md` | Alinear con la arquitectura real (ES+EN) |
| `tests/test_*.py` | Una suite por fase, sin red |

No se crea un frontend React. No se parte Python en microservicios.

---

## 4. Orden de fases

Cada fase deja software usable. No empezar la 3 si la 1 no pasa tests.

```
0 Higiene de verdad     → el producto deja de mentir
1 Bucle de película     → oír / cortar / hablar rápido
2 Recibos y verdad      → el señor VE lo que hizo Hermes
3 HUD vivo              → presencia Iron Man
4 Memoria               → le conoce
5 Ojos                  → visión sin ceremonia
6 Proactividad          → él habla primero
7 Este PC vs portátil   → «aquí» / «allí» sin ambigüedad
8 Personalidad          → mayordomo, no chatbot
9 Empaque               → README, Electron, regresión
```

Estimación honesta si se ejecuta sin parar: **fases 0–3 = el salto que se nota** (el guion de 90 s). 4–8 = de bueno a «mejor que la peli». 9 = no romper el `.exe`.

**Prioridad si hay que recortar:** 0.1 → 1.2 barge-in → 1.3 primera frase → 2.1 recibos → 2.2 xdg → 1.1 pulso → 1.4 quitar el cronómetro. El resto espera. Un JARVIS lento y honesto gana a uno bonito que inventa archivos.

---

## Fase 0 — Higiene: el producto deja de mentir

**Por qué primero:** un HUD Iron Man que promete fútbol y XTTS es de cartón. La confianza es el 50 % de JARVIS.

### Task 0.1: Stream respeta el selector

**Files:**
- Modify: `app/main.py` (worker de `/api/chat/stream`, hoy ~línea 467)
- Modify: `app/brain.py` si hace falta exportar `quiere_hermes`
- Test: `tests/test_cerebro_forzado.py`

- [ ] **Step 1: Write the failing test**

Añadir al final de `tests/test_cerebro_forzado.py`:

```python
def test_stream_status_usa_quiere_hermes():
    orig = brain.Config.CEREBRO
    brain.Config.CEREBRO = "hermes"
    try:
        assert brain.quiere_hermes("cómo estás") is True
        # El worker del stream debe usar quiere_hermes, no necesita_hermes.
        assert brain.necesita_hermes("cómo estás") is False
    finally:
        brain.Config.CEREBRO = orig
```

El test de comportamiento real del worker va en el paso 3: extraer la etiqueta de status a una función pura.

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe tests\test_cerebro_forzado.py`

Hasta que no exista `etiqueta_status_stream`, añadir:

```python
from app.brain import etiqueta_status_stream
```

Expected: `ImportError: cannot import name 'etiqueta_status_stream'`

- [ ] **Step 3: Write minimal implementation**

En `app/brain.py`, junto a `quiere_hermes`:

```python
def etiqueta_status_stream(text):
    """Frase de consola al empezar el turno. No se habla."""
    if quiere_hermes(text):
        return "Hermes…"
    return "Respondiendo…"
```

En `app/main.py` worker, sustituir:

```python
q.put({"t": "status", "msg": "Hermes…" if brain.necesita_hermes(text) else "Respondiendo…"})
```

por:

```python
q.put({"t": "status", "msg": brain.etiqueta_status_stream(text)})
```

Completar el test:

```python
def test_etiqueta_status_respeta_forzado():
    orig = brain.Config.CEREBRO
    try:
        brain.Config.CEREBRO = "hermes"
        assert brain.etiqueta_status_stream("cómo estás") == "Hermes…"
        brain.Config.CEREBRO = "deepseek"
        assert brain.etiqueta_status_stream("crea un html en el escritorio") == "Respondiendo…"
        brain.Config.CEREBRO = "auto"
        assert brain.etiqueta_status_stream("cómo estás") == "Respondiendo…"
        assert brain.etiqueta_status_stream("haz ping a google.com") == "Hermes…"
    finally:
        brain.Config.CEREBRO = orig
```

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\python.exe tests\test_cerebro_forzado.py`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add app/brain.py app/main.py tests/test_cerebro_forzado.py
git commit -m "$(cat <<'EOF'
fix: el stream respeta el cerebro forzado

EOF
)"
```

### Task 0.2: README y Electron dejan de hablar de un JARVIS que ya no existe

**Files:**
- Modify: `README.md` — **hecho 2026-08-16** (Hermes, Fish, sin fútbol/XTTS/OpenClaw, ES+EN)
- Modify: `electron/main.js` líneas 1–11 (comentario XTTS puerto 5002)
- Modify: `app/main.py` docstring del módulo (`TTS (F5 → fallback Álvaro)`)

- [x] **Step 1: Reescribir el contrato en README** (hecho: arquitectura real, wake Yarvis, selector, dos máquinas)

Sustituir la tabla «Vigila» y el bloque de fútbol/Docker/XTTS por la arquitectura real:

- Piensa: DeepSeek aquí / Hermes en el portátil (Auto).
- Habla: Fish. Reserva Álvaro.
- Escucha: Vosk (Yarvis) + Whisper.
- Actúa: archivos y navegador en Linux. Spotify en este PC.
- Quitar fútbol como feature. Docker: panel opcional, NO en el chat.
- Quitar el `<details>` de XTTS como camino soportado (una línea: «TTS local no está en este build»).

Inglés: el mismo contenido, no un resumen vago.

- [x] **Step 2: Comentario de Electron** (hecho)

Cabecera de `electron/main.js` actualizada: FastAPI 8080, Hermes en Linux, Fish, sin XTTS.

- [x] **Step 3: Docstring FastAPI** (hecho)

`POST /api/tts` → Fish → Álvaro → Google.

- [ ] **Step 4: Commit** (este lote: README + plan + comentarios)

```bash
git add README.md electron/main.js app/main.py
git commit -m "$(cat <<'EOF'
docs: alinear README y Electron con Hermes+Fish

EOF
)"
```

No hay test de markdown. Verificación: buscar `XTTS`, `fútbol`, `5002` en esos tres archivos y que no queden como features actuales.

---

## Fase 1 — Bucle de película (oír, cortar, hablar)

**Por qué:** Iron Man no espera 20 s en silencio. El mayordomo corta cuando le interrumpes y suelta la primera frase en cuanto la tiene.

### Task 1.1: Pulso de «te oí» sin hablar

**Files:**
- Modify: `app/static/index.html` (`playAck`, `setSpeaking`, núcleo)
- Modify: `app/static/hud.css`

- [ ] **Step 1: playAck vuelve a ser un pulso visual, no voz**

Sustituir `function playAck() {}` por:

```javascript
function playAck() {
  const hud = document.getElementById('hud-ui');
  if (!hud) return;
  hud.classList.remove('ack-pulse');
  void hud.offsetWidth;
  hud.classList.add('ack-pulse');
  setTimeout(() => hud.classList.remove('ack-pulse'), 700);
}
function cancelAck() {
  const hud = document.getElementById('hud-ui');
  if (hud) hud.classList.remove('ack-pulse');
}
```

CSS:

```css
#hud-ui.ack-pulse { animation: ackFlash 0.7s var(--ease); }
@keyframes ackFlash {
  0% { filter: brightness(1); }
  35% { filter: brightness(1.18) saturate(1.15); }
  100% { filter: brightness(1); }
}
```

En el evento `wake` del WebSocket (hoy `log('Te escucho…')`), llamar `playAck()` ANTES del log.

- [ ] **Step 2: Verificar a mano**

No hay test JS en el repo. Criterio: al decir Yarvis, el HUD parpadea cian y NO se oye «En ello». `playAck` no llama a `speak`.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html app/static/hud.css
git commit -m "$(cat <<'EOF'
feat: pulso visual al oír Yarvis, sin voz de relleno

EOF
)"
```

### Task 1.2: Barge-in — hablar encima corta el TTS

**Files:**
- Modify: `app/static/index.html` (loop de escucha + `speak`)
- Modify: `app/wake.py` si hace falta no mandar `order` mientras `speaking`
- Test: no hay harness de audio. Extraer la regla a JS testeable no vale la pena. Verificación manual + guarda en código.

- [ ] **Step 1: Cortar voz en cuanto el VAD ve voz del señor durante TTS**

Hoy `escuchaProc.onaudioprocess` ya manda PCM. Añadir, junto al analyser, un umbral:

```javascript
const BARGE_RMS = 0.02;
function rmsDe(buf) {
  let s = 0;
  for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
  return Math.sqrt(s / buf.length);
}
```

Dentro de `onaudioprocess`, DESPUÉS de `if (recording) return`:

```javascript
if (speaking && rmsDe(e.inputBuffer.getChannelData(0)) > BARGE_RMS) {
  cortarVoz();
}
```

`cortarVoz()` ya existe: debe parar `AudioContext` / `audio.pause()` y `setSpeaking(false)`.

- [ ] **Step 2: No mandar una «orden» fantasma hecha del TTS**

El wake no debe transcribir la voz de JARVIS. Ya hay `escuchaPausa` / `mandarPausaEscucha`. Al `setSpeaking(true)`, llamar `mandarPausaEscucha(true)`. Al terminar TTS o barge-in, `false`.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "$(cat <<'EOF'
feat: barge-in corta la voz al hablar encima

EOF
)"
```

### Task 1.3: Hablar la primera frase estable sin esperar a Hermes entero

**Files:**
- Modify: `app/static/index.html` (`sendChat`)
- Modify: `app/voice.py` (`_extract_sentences` ya existe; reutilizar en el HUD)
- Test: `tests/test_voice_norm.py` ya cubre extract en Python. Añadir espejo mínimo de la regla JS no. Extraer a Python un helper de «primera frase» si el HUD llama a `/api/tts` por trozos.

Diseño cerrado: el HUD, al recibir el primer `t=text` cuyo `reply` tenga una frase terminada en `.!?…` de ≥ 15 caracteres, llama a `speak(primera)` UNA vez (`sendChat._spokeHead`). Al `done`, si el reply completo es más largo, habla SOLO el resto (`reply.slice(head.length)`), no todo otra vez.

- [ ] **Step 1: Write the failing test (regla de corte)**

Crear `tests/test_primera_frase.py`:

```python
"""La primera frase hablable se corta igual que el voice_chat."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.voice import _extract_sentences

def test_primera_frase_estable():
    frases, marker = _extract_sentences(
        "Hecho, señor. El html está en el escritorio.", "", 15
    )
    assert frases
    assert "Hecho" in frases[0]
    assert marker.endswith("señor. ") or "Hecho" in marker
```

- [ ] **Step 2: Run it**

Run: `venv\Scripts\python.exe tests\test_primera_frase.py`

Si `_extract_sentences` ya cumple, el test PASA (verde inmediato: no reimplementar). Si falla el marker, ajustar el test a la semántica real de la función, no al revés.

- [ ] **Step 3: HUD usa esa regla**

En `sendChat`:

```javascript
sendChat._spokeHead = false;
sendChat._head = '';
// en t=text:
if (voz && !sendChat._spokeHead) {
  const m = d.reply.match(/^(.{15,}?[.!?…])(\s|$)/);
  if (m) {
    sendChat._spokeHead = true;
    sendChat._head = m[1];
    speak(m[1]);
  }
}
// en done, si voz:
if (voz && last.reply) {
  if (sendChat._spokeHead) {
    const rest = last.reply.slice(sendChat._head.length).trim();
    if (rest) speak(rest);
  } else {
    speak(last.reply);
  }
}
```

Quitar el `speak(last.reply)` incondicional que hay ahora para no duplicar.

- [ ] **Step 4: Commit**

```bash
git add tests/test_primera_frase.py app/static/index.html
git commit -m "$(cat <<'EOF'
feat: la voz suelta la primera frase sin esperar al done

EOF
)"
```

### Task 1.4: Consola de espera sin «En ello, señor. 14s.»

**Files:**
- Modify: `app/static/index.html` (`fraseEnEllo`)

- [ ] **Step 1: El vivo muestra SOLO el status, sin cronómetro hablado**

```javascript
function fraseEnEllo(seg, estado) {
  return 'JARVIS: ' + (estado || 'En ello, señor.');
}
```

El `setInterval` que reescribe `14s` se elimina. El `t=status` sigue actualizando `estado`. El núcleo 3D usa `speaking` o una clase `thinking` mientras `sendChat._busy && !hayTexto`.

```javascript
document.getElementById('hud-ui').classList.toggle('thinking', sendChat._busy && !hayTexto);
```

CSS: el reactor ya pulsa con `speaking`; `.thinking` sube opacidad del glow (no nuevo sistema 3D).

- [ ] **Step 2: Commit**

```bash
git add app/static/index.html app/static/hud.css
git commit -m "$(cat <<'EOF'
fix: la espera deja de contar segundos en voz alta

EOF
)"
```

---

## Fase 2 — Recibos y verdad (el señor VE lo que pasó)

**Por qué:** el HTML «creado» que no estaba en Escritorio mató más inmersión que cualquier FPS. Iron Man no dice «listo» si el reactor no encendió.

### Task 2.1: Recibo canónico en el cerebro

**Files:**
- Create: `app/recibo.py`
- Test: `tests/test_recibo.py`
- Modify: `app/brain.py` (`_chat_via_hermes`)
- Modify: `app/main.py` (emitir `t=receipt`)
- Modify: `hermes/SOUL.md`

- [ ] **Step 1: Write the failing test**

```python
"""Recibo: una linea para el HUD, nunca para el TTS."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.recibo import parse_recibo, formatear_recibo

def test_parse_ok_write():
    r = parse_recibo("WROTE /home/usuario/Escritorio/hola-mundo.html")
    assert r["ok"] is True
    assert r["machine"] == "linux"
    assert r["tool"] == "write"
    assert "hola-mundo" in r["detail"]

def test_formatear_sin_ruta_cruda():
    t = formatear_recibo({
        "ok": True, "machine": "linux", "tool": "write",
        "detail": "Escritorio, hola-mundo.html",
    })
    assert "home" not in t
    assert "hola-mundo" in t
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv\Scripts\python.exe tests\test_recibo.py`

Expected: `ModuleNotFoundError: app.recibo`

- [ ] **Step 3: Implement `app/recibo.py`**

```python
import re

_WROTE = re.compile(r"(?i)(?:wrote|created|creado|escrito)\s+(\S+)")
_PING = re.compile(r"(?i)(\d+(?:[.,]\d+)?)\s*ms")

def parse_recibo(blob: str) -> dict:
    blob = blob or ""
    m = _WROTE.search(blob)
    if m:
        path = m.group(1).rstrip(".,;")
        nombre = path.replace("\\", "/").split("/")[-1]
        return {
            "ok": True,
            "machine": "linux",
            "tool": "write",
            "detail": "Escritorio, " + nombre if "scritorio" in path.lower() else nombre,
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
```

Hermes no siempre imprime `WROTE ...`. Por eso el SOUL obliga a una línea máquina:

```
RECIBO: ok write Escritorio/hola-mundo.html
```

Ampliar el parser:

```python
_REC = re.compile(r"(?im)^RECIBO:\s+(ok|fail)\s+(\S+)\s+(.+)$")

def parse_recibo(blob: str) -> dict:
    m = _REC.search(blob or "")
    if m:
        return {
            "ok": m.group(1).lower() == "ok",
            "machine": "linux",
            "tool": m.group(2).lower(),
            "detail": m.group(3).strip(),
        }
    # ... fallbacks wrote/ping de arriba
```

En `hermes/SOUL.md` añadir al final:

```
Tras usar una tool de archivos, terminal o ping, la ULTIMA linea del
mensaje interno (no la hablada) es exactamente:
RECIBO: ok <tool> <detalle humano>
o RECIBO: fail <tool> <motivo>
El senor no debe oir la palabra RECIBO. El HUD la recorta.
Nunca RECIBO: ok si la tool no devolvio ok.
```

- [ ] **Step 4: El stream recorta RECIBO del texto hablado y lo emite aparte**

En `app/brain.py` `_chat_via_hermes`, tras `reply = _strip_urls(...)`:

```python
from .recibo import parse_recibo, recortar_recibo

recibo = parse_recibo(reply)
reply = recortar_recibo(reply)
```

```python
def recortar_recibo(text: str) -> str:
    return re.sub(r"(?im)^RECIBO:\s+\S+\s+\S+\s+.+\s*", "", text or "").strip()
```

El dict de retorno de `_chat_via_hermes` gana `"recibo": recibo` si `recibo.get("tool") != "unknown"`.

`chat_stream` / `chat` lo copian. `app/main.py` worker:

```python
if r.get("recibo"):
    q.put({"t": "receipt", **r["recibo"]})
```

Test extra:

```python
def test_recortar_no_se_habla():
    from app.recibo import recortar_recibo
    t = recortar_recibo("Hecho, senor.\nRECIBO: ok write Escritorio/hola.html")
    assert "RECIBO" not in t
    assert "Hecho" in t
```

- [ ] **Step 5: HUD pinta el recibo**

En `sendChat`, si `d.t === 'receipt'`:

```javascript
pintarRecibo(d);
```

Tarjeta en el panel Núcleo (HTML estático, una fila nueva):

```html
<div class="row"><span>RECIBO</span><span id="v-recibo">—</span></div>
```

```javascript
function pintarRecibo(d) {
  const el = $('v-recibo');
  if (!el) return;
  el.textContent = (d.ok ? '' : 'Fallo: ') + (d.detail || d.tool || '—');
  el.className = d.ok ? 'ok' : 'bad';
  log((d.ok ? 'Recibo: ' : 'Recibo fallido: ') + (d.detail || ''), d.ok ? 'ok' : 'bad');
}
```

- [ ] **Step 6: Run tests + commit**

Run: `venv\Scripts\python.exe tests\test_recibo.py`

```bash
git add app/recibo.py app/brain.py app/main.py hermes/SOUL.md app/static/index.html tests/test_recibo.py
git commit -m "$(cat <<'EOF'
feat: recibos de tool en el HUD, fuera de la voz

EOF
)"
```

Copiar a mano `hermes/SOUL.md` a `~/.hermes/SOUL.md` del Linux (Hermes no lee el del repo). El SYSTEM_PROMPT de Windows ya viaja en cada request: la línea RECIBO también se añade a `_MSG_HERMES_ACCION`.

### Task 2.2: Skill de escritorio en el repo (para copiar al Linux)

**Files:**
- Create: `hermes/skills/escritorio.md`

- [ ] **Step 1: Escribir la skill**

```markdown
# Escritorio del señor

Antes de crear o listar archivos del escritorio:

1. Corre `xdg-user-dir DESKTOP` y usa ESA ruta.
2. En español suele ser `/home/usuario/Escritorio`.
3. NUNCA `mkdir escritorio`. NUNCA asumas `~/Desktop`.
4. Lista con `ls` esa ruta para verificar.
5. Cierra con `RECIBO: ok write Escritorio/<nombre>`.
```

El runtime de Hermes en Linux debe copiar esta skill a `~/.hermes/skills/` (paso humano, una vez). El plan no automatiza SSH.

- [ ] **Step 2: Commit**

```bash
git add hermes/skills/escritorio.md
git commit -m "$(cat <<'EOF'
feat: skill Hermes para el Escritorio real de Linux

EOF
)"
```

---

## Fase 3 — HUD vivo (presencia)

**Por qué:** el 3D ya no se apaga. Falta que el puesto de mando *cuente una historia*: quién piensa, qué máquina actúa, qué suena, qué tiempo hace.

### Task 3.1: Partir `index.html` sin cambiar comportamiento

**Files:**
- Create: `app/static/hud-three.js`
- Create: `app/static/hud-wake.js`
- Create: `app/static/hud-chat.js`
- Modify: `app/static/index.html` (deja markup + boot + ajustes)
- Modify: `app/main.py` si sirve estáticos (ya monta `/static`)

Criterio de no regresión: mismas funciones globales (`initThree`, `sendChat`, `speak`, `poll`). Se extraen por corte, no se reescriben.

- [ ] **Step 1: Extraer Three**

Mover desde el comentario `THREE.JS: reactor` hasta el `visibilitychange` a `hud-three.js`. En `index.html`:

```html
<script src="/static/hud-three.js?v=iron1"></script>
```

antes del script inline.

- [ ] **Step 2: Extraer wake + chat**

`hud-wake.js`: Vosk WS, VU, `iniciarEscucha`.
`hud-chat.js`: `sendChat`, `speak`, `textoSinEmocion`, recibos.

Orden de carga: three → wake → chat → inline (ajustes, poll, boot).

- [ ] **Step 3: Verificar**

No hay test de DOM. Criterio: `start.bat`, wake sigue, 3D sigue, chat escribe. Si una función queda `undefined`, el fallo es inmediato en consola.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html app/static/hud-three.js app/static/hud-wake.js app/static/hud-chat.js
git commit -m "$(cat <<'EOF'
refactor: partir el HUD en three, oído y chat

EOF
)"
```

### Task 3.2: Tarjeta de misión (máquina + cerebro + recibo)

**Files:**
- Modify: `app/static/index.html` panel Núcleo
- Modify: `app/static/hud.css`
- Modify: `app/static/hud-chat.js`

- [ ] **Step 1: Markup**

Bajo CEREBRO, añadir:

```html
<div class="row"><span>MÁQUINA</span><span id="v-maquina">este PC</span></div>
<div class="row"><span>MISIÓN</span><span id="v-mision">en espera</span></div>
```

- [ ] **Step 2: Actualizar en stream**

Al empezar `sendChat`:

```javascript
$('v-mision').textContent = 'recibida';
$('v-maquina').textContent = 'este PC';
```

Si el primer status contiene `Hermes` o `portátil`:

```javascript
$('v-maquina').textContent = 'portátil';
$('v-mision').textContent = d.msg;
```

Al `done`:

```javascript
$('v-mision').textContent = last.error ? 'fallo' : 'completa';
```

Núcleo 3D: `hud-ui.thinking` ya de Fase 1. Si `v-maquina` es portátil, clase `hud-ui.remote` (glow más frío, no otro renderer).

```css
#hud-ui.remote .stage canvas { filter: hue-rotate(-12deg); }
```

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html app/static/hud.css app/static/hud-chat.js
git commit -m "$(cat <<'EOF'
feat: el núcleo dice qué máquina está en misión

EOF
)"
```

### Task 3.3: Spotify y tiempo como hologramas, no filas muertas

No se rediseña el panel. Se hace que el NOW PLAYING y el tiempo pulsen cuando cambian.

- [ ] **Step 1:** En `renderSpotify` / `renderStatus`, si el texto de `v-spotify` o el tiempo cambió, `el.classList.add('tick')` y quitarlo a 600 ms.

```css
.tick { animation: tickGlow 0.6s var(--ease); }
@keyframes tickGlow {
  from { text-shadow: 0 0 12px var(--cyan); }
  to { text-shadow: none; }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/index.html app/static/hud.css
git commit -m "$(cat <<'EOF'
feat: pulso HUD al cambiar Spotify o el tiempo

EOF
)"
```

---

## Fase 4 — Memoria que le conoce

**Por qué:** el JARVIS de la peli no espera a «recuerda que…». Anota lo estable (nombre, tono, odio a rodeos) y lo usa.

### Task 4.1: Extraer candidatos a preferencia, no escribir a ciegas

**Files:**
- Create: `app/memoria_auto.py`
- Test: `tests/test_memoria_auto.py`
- Modify: `app/brain.py` (tras cada `chat` local, no Hermes)

Regla cerrada: SOLO se propone guardar si el señor dice un patrón explícito de regla o dato estable. No se scrapea toda la charla (privacidad + basura).

Patrones:

```python
_REGLA = re.compile(
    r"(?i)\b(?:recuerda(?:\s+que)?|anota que|quiero que(?:\s+siempre)?|no me hables\s+de|odio que)\b"
)
```

Si `_REGLA` coincide y NO se llamó ya la tool `recordar` en ese turno, el cerebro local hace un append a `preferencias.md` con la frase recortada, y el reply puede incluir «Anotado, señor.» solo si el append fue ok.

- [ ] **Step 1: Failing test**

```python
from app.memoria_auto import debe_recordar, nota_desde

def test_no_recuerda_como_estas():
    assert debe_recordar("cómo estás") is False

def test_si_recuerda_regla():
    t = "recuerda que odio los rodeos"
    assert debe_recordar(t) is True
    assert "odio los rodeos" in nota_desde(t)
```

- [ ] **Step 2: Implement**

```python
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
```

En `chat()` / `chat_stream()`, DESPUÉS de un turno que NO fue Hermes y NO usó ya `recordar`:

```python
if debe_recordar(text):
    append_memory("preferencias", nota_desde(text))
```

No duplicar: `append_memory` debe no escribir si la nota ya está en el archivo (comprobar substring). Test:

```python
def test_no_duplica(tmp_path, monkeypatch):
    # monkeypatch Config.MEMORY_FILES preferencias → tmp_path / "p.md"
    ...
```

Usar el `append_memory` real de `brain.py`. Si ya existe, leerlo y añadir el guard de duplicado ahí (un solo sitio).

- [ ] **Step 3: Commit**

```bash
git add app/memoria_auto.py app/brain.py tests/test_memoria_auto.py
git commit -m "$(cat <<'EOF'
feat: anota preferencias dichas en claro, sin duplicar

EOF
)"
```

### Task 4.2: Bloque de memoria más corto y útil

Hoy `bloque_sistema_memoria()` mete los 3 md enteros. Si crecen, DeepSeek se vuelve lento y tonto.

- [ ] **Step 1: Failing test**

En `tests/test_memoria_auto.py`:

```python
def test_recuerdos_solo_cola(tmp_path, monkeypatch):
    from app import brain
    rec = tmp_path / "recuerdos.md"
    rec.write_text("\n".join(f"L{i}" for i in range(80)), encoding="utf-8")
    monkeypatch.setitem(brain.Config.MEMORY_FILES, "recuerdos", str(rec))
    monkeypatch.setitem(brain.Config.MEMORY_FILES, "preferencias", str(tmp_path / "p.md"))
    monkeypatch.setitem(brain.Config.MEMORY_FILES, "estado", str(tmp_path / "e.md"))
    (tmp_path / "p.md").write_text("regla\n", encoding="utf-8")
    (tmp_path / "e.md").write_text("ok\n", encoding="utf-8")
    bloque = brain.bloque_sistema_memoria()
    assert "L0" not in bloque
    assert "L79" in bloque
```

Ese test usa pytest `tmp_path`. Si se corre como script, sustituir por `tempfile.mkdtemp()`.

- [ ] **Step 2: Implement**

En `bloque_sistema_memoria()`, al leer `recuerdos` y `estado`, usar `lines[-40:]`. `preferencias` entero.

- [ ] **Step 3: Commit**

```bash
git add app/brain.py tests/test_memoria_auto.py
git commit -m "$(cat <<'EOF'
fix: la memoria larga no ahoga el prompt

EOF
)"
```

---

## Fase 5 — Ojos

**Por qué:** JARVIS ve. Hoy hay que pulsar cámara y esperar un párrafo. El modo película es «Yarvis, ¿qué ves?».

### Task 5.1: Intención de visión en el router

**Files:**
- Modify: `app/brain.py`
- Modify: `app/main.py` `/api/chat/stream`
- Modify: `app/static/hud-chat.js` / wake
- Test: `tests/test_intencion.py`

- [ ] **Step 1: Failing test**

```python
def test_vision_es_local():
    from app.brain import pide_vision
    for t in ("qué ves", "mira la cámara", "describe lo que hay", "qué tengo delante"):
        assert pide_vision(t), t
    assert not pide_vision("cómo estás")
    assert not pide_vision("crea un html en el escritorio")
```

- [ ] **Step 2: Implement**

```python
_VISION_RE = re.compile(
    r"(?i)\b(?:qu[eé]\s+ves|mira(?:\s+la)?\s+c[aá]mara|describe\s+lo\s+que|qu[eé]\s+tengo\s+delante|qu[eé]\s+hay\s+ah[ií])\b"
)

def pide_vision(text):
    if es_charla_rapida(text) or quiere_hermes(text):
        return False
    return bool(_VISION_RE.search(text or ""))
```

`quiere_hermes` gana: un «mira el escritorio» de archivos NO es visión.

- [ ] **Step 3: El HUD, si `pide_vision`…**

No hace falta que Python capture la webcam (está en el browser). Contrato:

1. Wake/chat envía `{text, voice, vision: true}` cuando el cliente ya decidió.
2. El cliente decide con la misma regex en JS (duplicar la lista de frases, 5 strings, no un motor).
3. Si `vision: true`, el HUD captura un frame (código que ya existe ~línea 2030 de `index.html`) y POST `/api/vision`, luego concatena la descripción al texto: `"El señor pregunta: {text}. La cámara ve: {description}"` y manda eso a `/api/chat/stream`.

Más limpio: endpoint único más tarde. En esta tarea, el HUD hace la captura ANTES del stream si la frase coincide. Python `pide_vision` sirve para tests y para no mandar a Hermes.

- [ ] **Step 4: Commit**

```bash
git add app/brain.py tests/test_intencion.py app/static/hud-chat.js app/static/hud-wake.js
git commit -m "$(cat <<'EOF'
feat: 'qué ves' usa la cámara sin pulsar botones

EOF
)"
```

### Task 5.2: Captura de pantalla del portátil = Hermes, no este PC

«Haz una captura» ya está en `_HERMES_RE`. Confirmar test y SOUL: la captura es del Linux. Si el señor dice «captura de esta pantalla» / «de este PC»:

```python
_ESTE_PC = re.compile(r"(?i)\b(?:este\s+pc|esta\s+pantalla|este\s+windows)\b")
```

Eso NO va a Hermes. Fase 7 implementa la captura Windows. En Fase 5, si `_ESTE_PC` y captura: reply honesto «Aún no puedo capturar este Windows; la captura es del portátil.» (test de intención, un string fijo en brain, sin Electron).

- [ ] **Step 1: Test + frase fija**

```python
def test_captura_este_pc_no_es_hermes():
    t = "haz una captura de este pc"
    assert not quiere_hermes(t)  # con CEREBRO=auto
```

Implementar: si captura AND este pc → no Hermes, reply constante. Si captura sin este pc → Hermes.

- [ ] **Step 2: Commit**

```bash
git add app/brain.py tests/test_intencion.py
git commit -m "$(cat <<'EOF'
fix: captura 'de este PC' no se finge en Linux

EOF
)"
```

---

## Fase 6 — Proactividad

**Por qué:** JARVIS habla primero. Un briefing de 8 s al abrir, y un aviso si Hermes se cae (una vez, no spam).

### Task 6.1: Aviso único Hermes apagado

**Files:**
- Modify: `app/static/index.html` `renderStatus` (ya loguea)
- Modify: `app/voice.py` no. El HUD llama `speak` UNA vez por transición `hermes → apagado`.

Hoy ya hay:

```javascript
if (renderStatus._cerebro !== 'apagado') log('Hermes apagado…', 'bad');
```

Añadir:

```javascript
if (renderStatus._cerebro !== 'apagado' && d.cerebro === 'apagado') {
  speak('[calm] Hermes no responde en el portátil. La charla sigue aquí.');
}
```

No hablar si el selector es `deepseek` forzado (`cerebro_modo === 'deepseek'`).

- [ ] **Step 1: Commit**

```bash
git add app/static/index.html
git commit -m "$(cat <<'EOF'
feat: avisa una vez por voz si Hermes se cae

EOF
)"
```

### Task 6.2: Briefing de arranque (opt-in, default ON, se puede quitar)

**Files:**
- Modify: `app/config.py` `BRIEFING = _env("JARVIS_BRIEFING", "1") == "1"`
- Modify: `app/main.py` `GET /api/briefing`
- Modify: `app/static/index.html` boot
- Test: `tests/test_briefing.py`

El briefing NO llama al LLM. Monta 2 frases con datos ya cacheados: saludo por hora + tiempo si `smart_context`/`weather()` hay datos + Hermes ok/apagado.

```python
def texto_briefing(status: dict, hora: int) -> str:
    tramo = "Buenos días" if hora < 12 else ("Buenas tardes" if hora < 20 else "Buenas noches")
    bits = [f"{tramo}, señor."]
    w = (status.get("weather") or {})
    if w.get("temp") is not None:
        bits.append(f"En Alcoy, {int(w['temp'])} grados.")
    if status.get("cerebro") == "apagado":
        bits.append("Hermes no responde.")
    else:
        bits.append("Sistemas en orden.")
    return " ".join(bits)
```

- [ ] **Step 1: Failing test**

```python
from app.briefing import texto_briefing

def test_briefing_manana():
    t = texto_briefing({"weather": {"temp": 18.2}, "cerebro": "hermes"}, 9)
    assert t.startswith("Buenos días")
    assert "18" in t
    assert "orden" in t
```

- [ ] **Step 2: Endpoint y boot**

`GET /api/briefing` → `{text, enabled}`. El HUD, al terminar `startBootSequence` (no en el overlay), si `enabled` y no se ha hablado aún: `speak(text)`. No duplicar el saludo actual si ya dice lo mismo: sustituir el saludo de boot por el briefing.

Ajustes: no hace falta UI en esta tarea. `.env` `JARVIS_BRIEFING=0` lo apaga. Se puede añadir al selector de claves en Fase 9 si molesta.

- [ ] **Step 3: Commit**

```bash
git add app/briefing.py app/config.py app/main.py app/static/index.html tests/test_briefing.py
git commit -m "$(cat <<'EOF'
feat: briefing de arranque con hora, tiempo y Hermes

EOF
)"
```

### Task 6.3: Cron de Hermes → tarjeta, no voz continua

Hermes en Linux ya tiene cron. El HUD no lo lee. Diseño cerrado y mínimo: `GET /api/status` incluye `avisos: []`. Un aviso es `{id, text, t}`. Fuente v1: archivo `memoria/avisos.json` que Hermes puede escribir vía MCP nuevo `avisar`.

- [ ] **Step 1: MCP `avisar`**

En `app/mcp_jarvis.py` añadir tool:

```python
{
    "name": "avisar",
    "description": "Deja un aviso corto en el HUD del senor (una linea).",
    "inputSchema": {
        "type": "object",
        "properties": {"texto": {"type": "string"}},
        "required": ["texto"],
    },
}
```

`dispatch` escribe como máximo 10 avisos en `memoria/avisos.json`. `full_status()` los lee.

HUD: si entra un `id` nuevo, `log(text)` y `speak` SOLO si `avisos.length` y el texto tiene < 80 caracteres. Un speak cada 10 min máximo (`lastAvisoSpeak`).

En `tests/test_mcp_jarvis.py`:

```python
def test_avisar_queda_en_status(tmp_path, monkeypatch):
    from app import mcp_jarvis, services
    monkeypatch.setattr(services, "AVISOS_FILE", tmp_path / "avisos.json")
    out = mcp_jarvis.dispatch("avisar", {"texto": "el backup acabo"})
    assert out.get("ok") is True
    avisos = services.leer_avisos()
    assert avisos[0]["texto"] == "el backup acabo"
```

`AVISOS_FILE = Path(Config.MEMORY_DIR) / "avisos.json"`. Máximo 10. `full_status()` incluye `"avisos": leer_avisos()`.

- [ ] **Step 2: Commit**

```bash
git add app/mcp_jarvis.py app/services.py tests/test_mcp_jarvis.py app/static/index.html
git commit -m "$(cat <<'EOF'
feat: avisos de Hermes al HUD, con voz corta

EOF
)"
```

---

## Fase 7 — «Este PC» vs «el portátil»

**Por qué:** la ambigüedad mató el HTML. Iron Man sabe qué consola está usando.

### Task 7.1: Clasificador de máquina

**Files:**
- Modify: `app/brain.py`
- Test: `tests/test_intencion.py`

```python
def maquina_objetivo(text: str) -> str:
    """linux | windows | auto"""
    t = text or ""
    if re.search(r"(?i)\b(?:este\s+pc|este\s+windows|aqui\s+en\s+el\s+pc)\b", t):
        return "windows"
    if re.search(r"(?i)\b(?:port[aá]til|linux|hermes|all[ií])\b", t):
        return "linux"
    return "auto"
```

`quiere_hermes`: si `maquina_objetivo == "windows"` → False (salvo que CEREBRO=hermes forzado: el forzado gana, es un override de depuración). Si `"linux"` → True. Si `"auto"` → semáforo actual.

- [ ] **Step 1: Tests**

```python
def test_maquina_objetivo():
    from app.brain import maquina_objetivo
    assert maquina_objetivo("abre chrome en el portátil") == "linux"
    assert maquina_objetivo("sube el volumen de este pc") == "windows"
    assert maquina_objetivo("cómo estás") == "auto"
```

- [ ] **Step 2: Commit**

```bash
git add app/brain.py tests/test_intencion.py
git commit -m "$(cat <<'EOF'
feat: 'este PC' y 'portátil' eligen máquina a propósito

EOF
)"
```

### Task 7.2: Acciones locales Windows (pocas, reales)

Solo las que este PC PUEDE hacer sin fingir:

| Frase | Acción | Cómo |
|---|---|---|
| volumen de este pc / mute | volumen Windows | Electron IPC `win-audio` o `nircmd` si está. Si no hay tool, reply honesto. |
| captura de este pc | screenshot | `electron` `desktopCapturer` → guarda en Escritorio de Windows del usuario (`os.path.join(os.path.expanduser("~"), "Desktop")` y si no existe, `Escritorio`). Esto SÍ es Windows porque el señor lo pidió «de este PC». |
| abre {url} en este pc | `shell.openExternal` | IPC |

NO: crear HTML en Windows salvo «este PC» + archivo. Aun así, preferir decir «eso lo hago en el portátil» si no dijo «este PC». YAGNI de un explorador de archivos Windows.

- [ ] **Step 1:** IPC mínimo en `electron/preload.js` + `main.js`:

```javascript
ipcMain.handle('abrir-url', (_e, url) => {
  if (!/^https?:\/\//i.test(url)) return { ok: false };
  shell.openExternal(url);
  return { ok: true };
});
```

Python no abre URLs: el HUD, si `maquina_objetivo==windows` y hay URL, llama IPC. Detectar URL en el cliente es frágil. Mejor: endpoint `POST /api/local/abrir` que Electron no ve… En kiosco el backend es el mismo proceso hijo: `webbrowser.open` en Python SÍ abre en este Windows.

Cerrado: `app/local_win.py` con `abrir_url(url)` usando `webbrowser.open` y `captura_pantalla()` usando `ImageGrab` (Pillow ya está en el venv por otras rutas; si no, skip con error honesto).

Test de `abrir_url` valida el esquema, no abre nada:

```python
def test_url_http_ok():
    from app.local_win import url_permitida
    assert url_permitida("https://example.com")
    assert not url_permitida("file:///c:/windows/system32")
```

- [ ] **Step 2: Commit**

```bash
git add app/local_win.py app/brain.py tests/test_local_win.py
git commit -m "$(cat <<'EOF'
feat: abrir URL y captura solo si pide este Windows

EOF
)"
```

Pillow: comprobar `requirements.txt`. Si no está, NO añadir para un screenshot. Entonces captura Windows = «no disponible» hasta que el señor pida la dep. Decisión: si `PIL` no importa, `captura_pantalla` devuelve `{error: "Sin captura en este PC"}`. No inflar el exe.

---

## Fase 8 — Personalidad de mayordomo

**Por qué:** sin esto es un router con glow. Con esto es JARVIS.

### Task 8.1: Saludo de boot = briefing (si Fase 6 está), nunca «JARVIS en línea»

Buscar en `index.html` / voz de tutorial esa cadena y matarla. Test grep mental: `JARVIS en línea` no debe existir en estáticos.

- [ ] **Step 1:** `rg "en línea|en linea|JARVIS online" app electron`

Sustituir por silencio o por el briefing.

- [ ] **Step 2: Commit**

```bash
git add app/static
git commit -m "$(cat <<'EOF'
fix: el arranque no dice JARVIS en línea

EOF
)"
```

### Task 8.2: Emoción Fish coherente con el turno

El modelo ya puede prefijar `[calm]`. Añadir al SYSTEM_PROMPT una línea:

```
Una sola etiqueta por respuesta. Acciones cumplidas: [confident].
Malas noticias o Hermes caído: [calm]. Charla: [calm] o [happy] si el señor bromea.
```

No hay clasificador aparte (YAGNI). Test: el prompt contiene esas tres palabras clave.

```python
def test_prompt_pide_emocion():
    from app.brain import SYSTEM_PROMPT
    assert "[confident]" in SYSTEM_PROMPT
    assert "Una sola etiqueta" in SYSTEM_PROMPT
```

- [ ] **Step 1: Commit**

```bash
git add app/brain.py tests/test_brain_reply.py
git commit -m "$(cat <<'EOF'
feat: el prompt fija una emoción Fish por tipo de turno

EOF
)"
```

### Task 8.3: Probar voz con el volumen de ESA voz

En Ajustes, junto a cada chip, un botón `▶` que POST `/api/tts` con `{text:"A su servicio, señor.", ...}` usando el volumen ya aplicado (activar voz y luego tts). No nuevo endpoint si `/api/tts` ya lee `Config.FISH_VOLUME`: el ▶ llama `aplicarVoz` y luego fetch tts.

- [ ] **Step 1: Commit** (solo HUD)

```bash
git add app/static/index.html app/static/hud.css
git commit -m "$(cat <<'EOF'
feat: botón de prueba por voz con su volumen

EOF
)"
```

---

## Fase 9 — Empaque y regresión

### Task 9.1: Batería que el agente debe pasar SIEMPRE antes de decir «listo»

```bat
venv\Scripts\python.exe tests\test_cerebro_forzado.py
venv\Scripts\python.exe tests\test_intencion.py
venv\Scripts\python.exe tests\test_charla_rapida.py
venv\Scripts\python.exe tests\test_brain_hermes.py
venv\Scripts\python.exe tests\test_spotify_orden.py
venv\Scripts\python.exe tests\test_fish_volumen.py
venv\Scripts\python.exe tests\test_recibo.py
venv\Scripts\python.exe tests\test_voice_norm.py
venv\Scripts\python.exe tests\test_hermes_client.py
venv\Scripts\python.exe tests\test_mcp_jarvis.py
```

Crear `tests\run_iron.bat` que las lanza y falla al primer error. No es pytest-global a propósito: el repo no usa pytest como runner único.

- [ ] **Step 1: Commit**

```bash
git add tests/run_iron.bat
git commit -m "$(cat <<'EOF'
chore: batería de regresión del JARVIS Iron Man

EOF
)"
```

### Task 9.2: Peso del exe

Al pedir build: `electron/package.json` `files` / `extraResources` no mete `venv`, `models/vosk` se copia a propósito (oído). No meter `docs/`, `tests/`, `*.pyc`. Si el portable salta de decenas a cientos de MB, el filtro `files` está mal — avisarlo, no «optimizar» a ciegas.

Checklist en el commit de build (cuando el señor lo pida, no ahora):

- [ ] `dist-electron` no se commitea
- [ ] portable + nsis
- [ ] `latest.yml` + blockmap si hay auto-update

### Task 9.3: TokenSaver

Este archivo es el plan VIVO de la campaña. No se le añade historial de sprints. Si una fase se completa, se marcan las casillas. Si una fase se cancela, se borra del plan (no se deja un «ya no»). README sigue siendo el estado del producto, no este md.

---

## Criterio de aceptación — «es Iron Man»

Se puede decir que el sistema llegó cuando, en el PC de Alexis, sin trampas:

1. Dices **Yarvis** → pulso cian, «Te escucho», sin voz de relleno.
2. **Cómo estás** → DeepSeek, < 5 s, voz Fish, núcleo pulsa.
3. **Crea un html de hola mundo en el escritorio** → máquina = portátil, progreso en consola no hablado, archivo en `~/Escritorio`, recibo en Núcleo, voz «Hecho» sin inventar ruta Windows.
4. **No has creado nada** (si falló) → sigue en Hermes, no DeepSeek sin tools.
5. Hablas encima de JARVIS → la voz se corta.
6. Selector DeepSeek → el html NO va a Hermes. Selector Hermes → el cómo estás SÍ.
7. Kratos con +8 dB se oye a la par que JARVIS.
8. El 3D no desaparece. Nunca más el log de rendimiento bajo.
9. Hermes caído → una frase hablada, charla sigue aquí.
10. README describe este sistema, no el de XTTS+fútbol.

Si 1–10 se cumplen, las fases 4–8 son lujo que se nota; si fallan 1–4, el lujo es maquillaje.

---

## Cómo se ejecuta este plan

**1. Subagent-Driven (recomendado)** — un subagente fresco por Task, review entre tareas, TDD.

**2. Inline Execution** — skill `executing-plans`, por lotes, con checkpoints.

Empieza SIEMPRE por **Fase 0 Task 0.1** (el stream del selector). El README ya está alineado. No saltes a visión ni a 3D nuevo.

Restricción de cada agente:

- Español de España en UI.
- Tests primero (salvo CSS/markup puro, que se verifica a mano).
- No 8080.
- Push solo si el señor lo pide.
- No Windows-escribir-html «por si acaso».
- No reactivar el apagado de Three.js.
- Toda tarea tiene que mover el **guion de 90 segundos** o un techo de latencia. Si no, fuera.

---

## Autorevisión del plan

**Cobertura de la biblia:** reglas 1–10 tienen tarea. Tuya es atajo Windows (como Spotify), no Hermes. Fuera de alcance: WhatsApp/React/OpenClaw.

**Placeholders:** no hay TBD. Las verificaciones JS sin harness están marcadas como criterio manual, no «añadir tests luego».

**Nombres:** `quiere_hermes`, `etiqueta_status_stream`, `parse_recibo`, `RECIBO:`, `maquina_objetivo`, `texto_briefing`, `fish_prosody` se usan iguales en todas las fases.

**Riesgo mayor:** Hermes en Linux no copia SOUL/skill solo. Cada fase 2 debe incluir el recordatorio de copiar `hermes/SOUL.md` y `hermes/skills/escritorio.md` al `~/.hermes` del portátil. El SYSTEM_PROMPT de Windows cubre el 80 %; el 20 % (cron, Telegram) vive en SOUL local.
