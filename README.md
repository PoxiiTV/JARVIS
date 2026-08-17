<div align="center">

# ⚡ J.A.R.V.I.S.

### Mayordomo de escritorio: te oye, habla y actúa donde toca

**v1.0.0** · HUD 3D · wake «Yarvis» · Fish Audio · Hermes en la LAN · DeepSeek

![Versión](https://img.shields.io/badge/versión-1.0.0-5eeaff?style=flat-square)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=flat-square&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10--3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Electron](https://img.shields.io/badge/Electron-33-47848F?style=flat-square&logo=electron&logoColor=white)
[![Licencia](https://img.shields.io/badge/Uso-Personal-5eeaff?style=flat-square)](LICENSE)

<br/>

[![Instalador](https://img.shields.io/badge/⬇_Instalador-JARVIS--Setup--1.0.0.exe-5eeaff?style=for-the-badge)](https://github.com/PoxiiTV/JARVIS/releases/tag/v1.0.0)
[![Portable](https://img.shields.io/badge/📦_Portable-JARVIS--Portable--1.0.0.exe-0078D6?style=for-the-badge)](https://github.com/PoxiiTV/JARVIS/releases/tag/v1.0.0)

[English](#-english) · [Releases](https://github.com/PoxiiTV/JARVIS/releases)

</div>

---

## 📑 Índice

1. [Qué es](#1--qué-es)
2. [Por qué dos PCs](#2--por-qué-dos-pcs-y-por-qué-hermes-no-es-localhost)
3. [Funciones](#3--inventario-de-funciones)
4. [Requisitos](#4--requisitos)
5. [Arrancar el HUD](#5--arrancar-el-hud-windows)
6. [Hermes en la LAN](#6--configurar-hermes-en-la-lan)
7. [Claves](#7--claves-windows)
8. [Personalidades](#8--personalidades)
9. [Variables](#9--variables-las-que-importan)
10. [Mapa del repo](#10--mapa-del-repo)
11. [Si algo falla](#11--si-algo-falla)

---

## 1. 🎯 Qué es

App de **escritorio Windows** (Electron + FastAPI). No es una pestaña del navegador.

| 🖥️ Este PC (HUD) | 🐧 El otro PC (Hermes) |
|---|---|
| Oído, voz, esfera 3D, Spotify, luces | Archivos, Chrome, terminal, ping |

- La **charla corta** («hola», la hora) la responde DeepSeek **aquí**, en unos segundos, sin agente.
- La voz es **Fish Audio** (nube). Si Fish falla, Álvaro (edge-tts). **No hace falta GPU.**

---

## 2. 🔗 Por qué dos PCs (y por qué Hermes no es localhost)

Hay **dos servidores**. No se atan igual.

| Qué | Dónde | Bind | Por qué |
|---|---|---|---|
| 🪟 HUD + FastAPI | Windows | `127.0.0.1:8080` | Kiosco **sin login**. Solo es seguro porque la red no entra. |
| 🧠 Hermes Agent | Linux | `0.0.0.0:8642` | Windows tiene que llamarlo por Wi-Fi. Si Hermes se queda en `127.0.0.1`, **este PC no lo ve**. |

> ⚠️ `HERMES_URL=http://192.168.1.100:8642/v1` en el `.env` de ejemplo es **una IP de ejemplo**. La tuya sale de `hostname -I` en el Linux. Si no la cambias, JARVIS busca un portátil que no existe.

Misma Wi-Fi. **No abras el 8642 en el router.** El firewall de Linux solo deja pasar la IPv4 de tu Windows. `HERMES_KEY` (Windows) = `API_SERVER_KEY` (Linux).

```
🪟 Windows                                          🐧 Linux (misma Wi-Fi)
──────────                                          ─────
🎤 Mic → Vosk (Yarvis) → Whisper
HUD Electron ←→ FastAPI :8080  (solo localhost)
        │
        ├─ 💬 DeepSeek / OpenRouter     charla, noticias, memoria
        ├─ 🎵 Spotify / 💡 Tuya         este Windows
        └─ 📡 HTTP  →  Hermes :8642/v1  archivos, Chrome, terminal, ping
🔊 Fish Audio ← texto final (el progreso no se habla)
```

«El escritorio» = el del Linux (`xdg-user-dir DESKTOP`, en español `~/Escritorio`). Un HTML no aparece en el Desktop de Windows. Spotify y las luces sí van aquí.

---

## 3. ✨ Inventario de funciones

### 🎙️ Oído y voz

| | Función | Cómo |
|:---:|---|---|
| 👂 | **Wake** | Vosk local espera «Yarvis» (también oye jarvis / ya vis / etc.). En pantalla el nombre es **JARVIS**. |
| 🧠 | **Orden** | Tras el wake, Whisper transcribe (`large-v3-turbo` por defecto). Modelos: `base`, `small`, `medium`, `large-v3-turbo`. Cambiar oído exige **reiniciar**. |
| 🎤 | **Micrófono** | Pulsa, habla, suelta (VAD). Sin palabra clave. |
| ⌨️ | **Texto** | Barra de chat, Enter. Atajos: Estado, Hermes, Tiempo. |
| ✋ | **Hablar encima** | Corta la voz (barge-in). |
| 🔇 | **Silenciar** | Corta TTS. |
| 🔊 | **Fish Audio** | Modelo `s2.1-pro-free`. Volumen por voz (−20…+20 dB). Emoción en etiquetas `[calm]` etc. (el HUD las quita al pintar). |
| 🎧 | **Voces** | Ajustes → añadir id de [fish.audio/discovery](https://fish.audio/discovery). Independiente de la personalidad. |
| 🛟 | **Reserva** | `es-ES-AlvaroNeural` si Fish no responde. |

### 🧩 Cerebro

| | Función | Cómo |
|:---:|---|---|
| ⚡ | **Auto** (defecto) | Charla aquí. Archivos / browser / terminal / ping → Hermes. Spotify y Tuya **nunca** salen de este Windows. |
| 🐧 | **Forzar Hermes** | Ajustes → Cerebro. Todo el chat al portátil. Spotify sigue aquí. |
| 💬 | **Forzar DeepSeek** | Charla aquí. Sin archivos ni comandos. |
| 👋 | **Charla rápida** | hola, cómo estás, qué hora es, gracias… → DeepSeek ~5 s, sin agente. |
| 🖥️ | **«En este PC»** | Captura o abrir URL en Windows (`app/local_win.py`). |
| 💻 | **«En el portátil»** | Fuerza Hermes. |
| 🛟 | **Reserva** | `HERMES_FALLBACK=1` usa OpenRouter si el gateway está caído. Por defecto **0**: dice «Hermes apagado». |
| 📰 | **Noticias** | Google News RSS (`buscar_noticias`). |
| ✅ | **Verdad** | No inventa archivos, pings, Telegram ni correo. Tras una tool: línea `RECIBO:` que el HUD recorta; tú no la oyes. |

### 🏠 Casa y música (este Windows)

| | Función | Cómo |
|:---:|---|---|
| 🎵 | **Spotify** | OAuth PKCE. Play, pausa, siguiente, buscar, dispositivo. Redirect exacta: `http://127.0.0.1:8080/api/spotify/callback`. |
| 💡 | **Tuya / Smart Life** | Luces dormitorio y salón, tele, aire. Frases: «enciende el dormitorio», «apaga las luces del salón», «enciende la tele», «apaga el aire». Access ID/Secret en [iot.tuya.com](https://iot.tuya.com). Región `eu` en Europa. |

### 🧠 Memoria y tono

| | Función | Cómo |
|:---:|---|---|
| 📝 | **Memoria** | Solo tres archivos: `memoria/recuerdos.md`, `preferencias.md`, `estado.md`. «Recuerda que…» / «olvida…». Las preferencias pisan el mayordomo. |
| 🎭 | **Personalidad** | Ajustes. No cambia las tools. JARVIS, Fermín, Kratos, Tobey, Amador, Saul, Sergio. |
| ☀️ | **Briefing** | Al abrir: saludo según personaje + grados + si Hermes vive. Si hablas encima, se corta. `JARVIS_BRIEFING=0` lo apaga. |

### 🖼️ HUD

| | Panel | Qué hace |
|:---:|---|---|
| 💠 | **Núcleo 3D** | Esfera Three.js, texto JARVIS, bloom, arrastre, pulso al pensar/hablar. |
| 📊 | **Núcleo (lista)** | Hermes, cerebro (Auto/forzado), máquina que actúa, misión, saldo OpenRouter, Spotify, recibo. |
| ⚙️ | **Sistema** | CPU, RAM, disco, uptime de **este** PC. |
| 🎵 | **Spotify** | Ahora suena, play/pause, buscar. |
| 🌤️ | **Tiempo** | Open-Meteo con `JARVIS_LAT` / `JARVIS_LON`. |
| 📷 | **Cámara** | Frame al modelo de visión (misma clave OpenRouter si no pones otra). |
| 📟 | **Consola** | Log, copiar, log del servidor. |
| 🚀 | **Arranque** | Secuencia + «Activar» para desbloquear audio. |
| 🔧 | **Ajustes** | Micrófono, cerebro, personalidad, claves, voces, probar cerebro, repetir tutorial. |

### 🐧 Hermes (el otro PC)

HTML al escritorio Linux, listar archivos, Chrome, terminal, ping, captura allí. El Núcleo enseña qué máquina actuó.

---

## 4. 📦 Requisitos

| | |
|---|---|
| 🪟 HUD | Windows 10/11, **Python 3.10–3.12** con *Add Python to PATH*, internet |
| 🐧 Manos | Linux con [Hermes Agent](https://hermes-agent.nousresearch.com/docs/getting-started/installation), misma Wi-Fi |
| 🎮 GPU | No |
| 🟢 Node.js | Solo para `compilar.bat` o Electron desde el código |

Sin Hermes: **habla**. No crea archivos.

---

## 5. 🚀 Arrancar el HUD (Windows)

### 💿 Con el `.exe`

1. Python 3.10–3.12 en PATH.
2. `JARVIS-Setup-1.0.0.exe` o portable.
3. Tutorial (claves) + `venv` la primera vez (~1–3 min).
4. Datos: `%APPDATA%\JARVIS\app` (`.env`, `venv`, `personalidades/`). Log: `%APPDATA%\JARVIS\jarvis.log`.

El `.exe` recopia el HUD (`app/`) al abrir, aunque la versión coincida. No pisa `.env`, `venv` ni `memoria/`. App sin firmar: Más información → Ejecutar de todas formas.

### 💻 Desde el código

```bat
git clone https://github.com/PoxiiTV/JARVIS.git
cd JARVIS
copy .env.example .env
```

Edita `.env` (claves + **tu** `HERMES_URL`). Luego `start.bat`.

Crea `venv\`, instala `requirements.txt`. Con Electron en `electron\node_modules` abre la ventana; si no, el panel en <http://127.0.0.1:8080> (sigue siendo localhost). `start.bat` avisa si Hermes no pinta en la URL del `.env`.

Linux solo-panel (raro): `./start.sh`.

---

## 6. 📡 Configurar Hermes en la LAN

Los dos PCs en la **misma Wi-Fi**. IPs privadas (`192.168.x`, `10.x`, `172.16–31.x`). Nada de IP pública.

### 6.1 📍 IPs

```bat
ipconfig
```

IPv4 Wi-Fi de Windows, p. ej. `192.168.1.10`.

```bash
hostname -I
```

IPv4 del Linux, p. ej. `192.168.1.20` → eso va en `HERMES_URL`.

### 6.2 📥 Instalar Hermes (Linux)

```bash
sudo apt install git curl xz-utils
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc
hermes model
```

Proveedor **OpenRouter**, modelo `deepseek/deepseek-v4-flash`. Docs: [Installation](https://hermes-agent.nousresearch.com/docs/getting-started/installation).

### 6.3 🔑 La misma clave en los dos lados

```bash
openssl rand -hex 32
```

| Sitio | Variable | Valor |
|---|---|---|
| Windows `.env` | `HERMES_KEY` | el secreto |
| Windows `.env` | `HERMES_URL` | `http://IP_LINUX:8642/v1` |
| Linux `~/.hermes/.env` | `API_SERVER_KEY` | **el mismo** secreto |
| Linux `~/.hermes/.env` | `OPENROUTER_API_KEY` | la misma que `DEEPSEEK_API_KEY` |

Plantilla: `hermes/linux.env.ejemplo`.

```env
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8642
API_SERVER_KEY=el-secreto
OPENROUTER_API_KEY=sk-or-...
```

`API_SERVER_HOST=0.0.0.0` es **obligatorio**. El default de Hermes es localhost y Windows no entra.

El modelo que el HUD manda al gateway es **`hermes-agent`**. DeepSeek se configura *dentro* de Hermes, no en `HERMES_MODEL`.

### 6.4 🪪 Identidad (Linux)

```bash
cp hermes/SOUL.md ~/.hermes/SOUL.md
mkdir -p ~/.hermes/skills
cp hermes/skills/escritorio.md ~/.hermes/skills/
```

`SOUL.md`: el HUD es un puente; archivos y comandos van **en esa máquina**; escritorio = `xdg-user-dir DESKTOP`; no inventar RECIBOs.

Telegram, si lo usas, **solo** en Linux (`TELEGRAM_BOT_TOKEN` en `~/.hermes/.env`). No dupliques el bot en Windows.

### 6.5 🛡️ Firewall

Desde el repo en el Linux, con la IP de **tu** Windows:

```bash
bash hermes/linux-lan.sh 192.168.1.10
```

Solo acepta IPs de casa. Pone `0.0.0.0` y, si `ufw` está activo, abre **8642/tcp solo desde esa IP**.

Varios Windows contra un Linux (el script sustituye la regla; añade a mano):

```bash
sudo ufw allow from 192.168.1.10 to any port 8642 proto tcp
sudo ufw allow from 192.168.1.11 to any port 8642 proto tcp
```

Mismo `HERMES_KEY` y misma `HERMES_URL` en cada Windows.

`hermes.bat` / `hermes-lan.bat` en Windows son avisos: **no** arranques Hermes en el PC del HUD.

### 6.6 ✅ Arrancar y probar

```bash
hermes gateway
# o: systemctl --user restart hermes-gateway
```

En el Linux:

```bash
curl -s http://127.0.0.1:8642/v1/models -H "Authorization: Bearer TU_CLAVE"
```

Tiene que salir `hermes-agent`. Luego desde Windows (PowerShell), con **tu** IP:

```powershell
Invoke-WebRequest http://192.168.1.20:8642/v1/models -Headers @{ Authorization = "Bearer TU_CLAVE" }
```

Si Linux sí y Windows no: Hermes aún en localhost, ufw, o `HERMES_URL` mal.

---

## 7. 🔐 Claves (Windows)

`.env.example` → `.env`, o el tutorial / Ajustes.

| Servicio | ¿Hace falta? | Dónde | Para |
|---|:---:|---|---|
| 🧠 Cerebro | sí | [openrouter.ai/keys](https://openrouter.ai/keys) | Charla aquí y el LLM de Hermes |
| 🔊 Voz | sí | [fish.audio/app/developers](https://fish.audio/app/developers) | Hablar |
| 🐧 Hermes | para actuar | `HERMES_URL` + `HERMES_KEY` | Manos en el Linux |
| 📷 Visión | no | Misma OpenRouter | Cámara |
| 🎵 Spotify | no | [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) | Música aquí |
| 💡 Tuya | no | [iot.tuya.com](https://iot.tuya.com) | Luces / tele / aire aquí |

DeepSeek v4 Flash vía OpenRouter: céntimos. Fish `s2.1-pro-free`: voz gratis (uso justo).

Spotify: Client ID (sin secret). Redirect **exacta** `http://127.0.0.1:8080/api/spotify/callback`. Luego el panel → conectar.

Tuya: Access ID, Secret, un Device ID, región `eu`. Opcional `tuya.json` con ip+key locales (más rápido que la nube). `tuya.example.json` es plantilla: **cambia los IDs**.

Tiempo: `JARVIS_LAT` / `JARVIS_LON`.

---

## 8. 🎭 Personalidades

Voz Fish y personaje van **aparte**.

| | Slug | Tono |
|:---:|---|---|
| 🤵 | `jarvis` | Mayordomo, «señor» |
| 📺 | `fermin` | Culebrón, ¿eh? |
| 🍺 | `amador` | Gañán, tío, dichos al revés |
| ⚔️ | `kratos` | Corto, grave |
| 🕷️ | `tobey` | Cercano |
| 😎 | `saul` | bro, fuera coñas |
| 🤙 | `sergio` | brother, da igual |

Otra ficha: `personalidades/<slug>.md` + alias en `mapa.json`. Opcional: `.tics.txt`, `.historia.md`, `.dichos.txt`. La ficha pisa el tono, **no** VERDAD, Hermes, Spotify, Tuya ni RECIBO.

---

## 9. ⚙️ Variables (las que importan)

Electron empaquetado escribe en `%APPDATA%\JARVIS\app\.env`.

| Variable | Default | Qué |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | OpenRouter |
| `DEEPSEEK_BASE_URL` | `https://openrouter.ai/api/v1` | |
| `DEEPSEEK_MODEL` | `deepseek/deepseek-v4-flash` | Charla directa |
| `HERMES_ENABLED` | `1` | |
| `HERMES_URL` | ejemplo `192.168.1.100` | **Cambia la IP** |
| `HERMES_KEY` | — | = `API_SERVER_KEY` |
| `HERMES_MODEL` | `hermes-agent` | Nombre en el gateway |
| `HERMES_FALLBACK` | `0` | `1` = OpenRouter si cae |
| `CEREBRO` | `auto` | `auto` / `hermes` / `deepseek` |
| `FISH_API_KEY` | — | |
| `FISH_VOICE_ID` | voz JARVIS | |
| `FISH_MODEL` | `s2.1-pro-free` | |
| `FISH_VOLUME` | `0` | dB |
| `PERSONALIDAD` | `jarvis` | |
| `JARVIS_BRIEFING` | `1` | |
| `JARVIS_WHISPER_MODEL` | `large-v3-turbo` | |
| `JARVIS_LAT` / `LON` | tu ciudad | |
| `SPOTIFY_CLIENT_ID` | — | |
| `TUYA_*` | — | |
| `JARVIS_KIOSK` | `1` en Electron | Sin login **solo** en localhost |

Si expones el panel a la LAN: kiosco **off**, cambia `JARVIS_PASSWORD` y `JARVIS_SECRET`, HTTPS. El escritorio **no** se publica en `0.0.0.0`. Hermes **no** a internet.

---

## 10. 🗺️ Mapa del repo

```
app/                 FastAPI, cerebro, voz, HUD, Tuya, wake
app/hermes_client.py Cliente HTTP a :8642
app/personalidad.py  Fichas de personalidades/
electron/            Ventana; uvicorn en 127.0.0.1:8080
hermes/              SOUL, skill escritorio, linux-lan.sh
memoria/             recuerdos, preferencias, estado
personalidades/      fichas + mapa.json
tests/               tests\run_iron.bat (sin red)
```

| Script | Qué hace |
|---|---|
| `start.bat` | Cierra instancias, ping a `HERMES_URL`, Electron o uvicorn |
| `start.sh` | Panel Linux en localhost |
| `compilar.bat` | Setup + portable en `dist-electron\` (~71 MB, sin claves) |
| `hermes/linux-lan.sh` | `0.0.0.0` + ufw desde tu Windows |
| `tests\run_iron.bat` | Suite offline |

`hermes/aplicar.py` y `hermes/lan.py` son restos de Hermes-en-Windows. El camino actual es **Linux + `linux-lan.sh`**.

Personalizar: `memoria/preferencias.md`, `personalidades/`, `hermes/SOUL.md` en el Linux, `SYSTEM_PROMPT` en `app/brain.py`, `app/static/hud.css`.

---

## 11. 🛠️ Si algo falla

| Síntoma | Causa típica |
|---|---|
| 🗣️ Voz que no es JARVIS | Fish caído o sin clave → Álvaro |
| 😶 Chat mudo | Falta `DEEPSEEK_API_KEY`. `429` = saturación OpenRouter |
| 📴 «Hermes apagado» | Gateway, IP, `0.0.0.0`, ufw, otra Wi-Fi |
| 📄 HTML «creado» y no está | Mira `~/Escritorio` en Linux |
| 🚫 Linux `curl` ok, Windows no | Localhost o firewall |
| 🔉 Kratos bajo | Ajustes → Voces → dB |
| 👂 Cambiaste Whisper y da igual | Reinicia |
| 🐍 Python | `python --version` 3.10–3.12 + PATH |
| 🔁 Tutorial otra vez | Ajustes → Repetir configuración inicial |
| 📦 `.exe` con HUD viejo | Cierra JARVIS y vuelve a abrir el `.exe` (recopia `app/`). Si sigue, borra `%APPDATA%\JARVIS\app\.version` |

---

<div align="center">

✨ *Que JARVIS te acompañe.* · **v1.0.0** · [PoxiiTV](https://github.com/PoxiiTV)

</div>

---

<a id="english"></a>

# 🇬🇧 English

**J.A.R.V.I.S. v1.0.0** is a Windows desktop HUD (Electron + FastAPI on **`127.0.0.1:8080`**).

On screen the name is **JARVIS**; the wake word is **Yarvis** (local Vosk). Speech is **Fish Audio** (`s2.1-pro-free`); fallback Álvaro. **Hands** (files, browser, shell, ping) run on **another PC on the same Wi-Fi** via [Hermes Agent](https://hermes-agent.nousresearch.com/docs/getting-started/installation) bound to **`0.0.0.0:8642`**. Short chat is DeepSeek on this PC. No GPU.

### 🔗 Why two binds

The HUD is localhost because kiosk mode has **no login**. Hermes **cannot** stay on localhost or Windows cannot reach it. Sample `HERMES_URL=http://192.168.1.100:8642/v1` is **an example IP** — use `hostname -I` on Linux. Same Wi-Fi. Do **not** forward 8642. `HERMES_KEY` = Linux `API_SERVER_KEY`. The HUD sends model name `hermes-agent`; DeepSeek is configured **inside** Hermes.

**Desktop** = Linux `xdg-user-dir DESKTOP` (often `~/Escritorio`). Spotify and Tuya stay on Windows.

Download: [Releases](https://github.com/PoxiiTV/JARVIS/releases). Packaged data: `%APPDATA%\JARVIS\app`. Each launch recopies the HUD from the exe; `.env`, `venv` and `memoria/` stay.

### ✨ What it does

Wake 👂 + Whisper · push-to-talk 🎤 · text chat · barge-in · mute · Fish voices (per-voice dB) independent of personality (JARVIS / Fermín / Kratos / Tobey / Amador / Saul / Sergio) · Auto brain (chat here, files on Linux) · force Hermes or DeepSeek · news RSS · memory · truth + receipts · Spotify · Tuya · camera · 3D core · CPU/RAM/disk · weather · boot briefing.

### 🪟 Windows

Python **3.10–3.12** on PATH. Copy `.env.example` → `.env`: `DEEPSEEK_API_KEY`, `FISH_API_KEY`, `HERMES_URL` / `HERMES_KEY`. Then `start.bat` or the installer. Rebuild: `compilar.bat`.

### 🐧 Linux Hermes

1. IPs: Windows `ipconfig`, Linux `hostname -I`.
2. `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` then `hermes model` (OpenRouter, `deepseek/deepseek-v4-flash`).
3. `~/.hermes/.env`: `API_SERVER_ENABLED=true`, `API_SERVER_HOST=0.0.0.0`, `API_SERVER_PORT=8642`, `API_SERVER_KEY=<same>`, `OPENROUTER_API_KEY=<same>`. See `hermes/linux.env.ejemplo`.
4. Copy `hermes/SOUL.md` and `hermes/skills/escritorio.md`.
5. `bash hermes/linux-lan.sh <WINDOWS_IP>` (RFC1918 only). Extra PCs: extra `ufw allow from <ip> to any port 8642 proto tcp`.
6. `hermes gateway`. Test `/v1/models` locally, then from Windows.

`CEREBRO=auto`: greetings → DeepSeek; files/shell/browser/ping → Hermes; Spotify/Tuya → this PC. `HERMES_FALLBACK=0` → “Hermes apagado” if the gateway is down.

Never commit `.env`. Do not expose the gateway to the internet. Offline tests: `tests\\run_iron.bat`. .

---

## 📜 Licencia / License

**J.A.R.V.I.S.** se distribuye bajo la **PolyForm Noncommercial License 1.0.0** 🔒.

Libre para **uso personal**: tu mayordomo de escritorio, aprender y experimentar. Prohibido el **uso comercial** — no se puede vender ni obtener beneficio económico con este proyecto.

> Uso personal, como debe ser. 🖤

📄 Texto completo en [`LICENSE`](LICENSE).
