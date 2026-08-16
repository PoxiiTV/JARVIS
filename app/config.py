"""Configuración del dashboard JARVIS. Todo se lee de variables de entorno."""
import os


def _cargar_dotenv(ruta=None):
    """Carga clave=valor del .env. No pisa variables ya definidas (Electron gana)."""
    if not ruta:
        ruta = os.environ.get("JARVIS_ENV_FILE") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )
    try:
        with open(ruta, encoding="utf-8") as f:
            lineas = f.readlines()
    except OSError:
        return
    for raw in lineas:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


_cargar_dotenv()


def _env(name, default=None):
    return os.environ.get(name, default)


def _whisper_modelo(raw):
    n = (raw or "").strip().lower()
    if n in ("turbo", "large-v3-turbo"):
        return "large-v3-turbo"
    if n in ("base", "small", "medium"):
        return n
    return "large-v3-turbo"


class Config:
    # --- Auth ---
    # Modo kiosco (app de escritorio): sin login. Solo es seguro porque en ese
    # modo el backend se ata a 127.0.0.1 y no lo alcanza nadie desde la red.
    # NO lo actives si expones el panel por túnel o a la LAN.
    KIOSK = _env("JARVIS_KIOSK", "0") == "1"
    USER = _env("JARVIS_USER", "jarvis")
    PASSWORD = _env("JARVIS_PASSWORD", "jarvis2026")
    SECRET = _env("JARVIS_SECRET", "cambia-este-secreto")
    # Cookie solo por HTTPS (el túnel es https; en tests locales http se apaga)
    COOKIE_SECURE = _env("JARVIS_COOKIE_SECURE", "1") == "1"
    # Límite de intentos de login fallidos por IP
    LOGIN_MAX_FAILURES = int(_env("JARVIS_LOGIN_MAX_FAILURES", "5"))
    LOGIN_WINDOW = int(_env("JARVIS_LOGIN_WINDOW", "900"))

    # --- DeepSeek (saldo + cerebro) ---
    DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = _env("DEEPSEEK_MODEL", "deepseek-v4-flash")
    # Hermes (agente en el portatil). El LLM sigue siendo OpenRouter/DeepSeek
    # detras de Hermes. Sin gateway: avisa, salvo HERMES_FALLBACK=1.
    HERMES_ENABLED = _env("HERMES_ENABLED", "1") == "1"
    HERMES_URL = _env("HERMES_URL", "http://192.168.1.100:8642/v1")
    HERMES_KEY = _env("HERMES_KEY", "")
    HERMES_MODEL = _env("HERMES_MODEL", "hermes-agent")
    HERMES_FALLBACK = _env("HERMES_FALLBACK", "0") == "1"
    # auto = semáforo. hermes/deepseek = forzado desde Ajustes.
    CEREBRO = (_env("CEREBRO", "auto") or "auto").strip().lower()
    # Pricing para estimar coste por mensaje (USD por millón de tokens)
    PRICE_CACHE = float(_env("PRICE_CACHE", "0.0028"))
    PRICE_INPUT = float(_env("PRICE_INPUT", "0.14"))
    PRICE_OUTPUT = float(_env("PRICE_OUTPUT", "0.28"))

    # --- Portainer / Docker (estado de contenedores) ---
    DOCKER_SOCKET = _env("JARVIS_DOCKER_SOCKET", "/var/run/docker.sock")
    PORTAINER_URL = _env("JARVIS_PORTAINER_URL", "https://172.19.0.1:9443")
    PORTAINER_KEY = _env("JARVIS_PORTAINER_KEY", "")

    # --- Proxy DeepSeek-Cursor (opcional) ---
    PROXY_URL = _env("JARVIS_PROXY_URL", "http://127.0.0.1:9000")
    TUNNEL_URL_FILE = _env("JARVIS_TUNNEL_URL_FILE", "tunnel_url.txt")

    # --- URL pública del DASHBOARD (para mostrar enlaces) ---
    PUBLIC_URL = _env("JARVIS_PUBLIC_URL", "http://localhost:8080")

    # --- Cron (jobs.json) ---
    CRON_JOBS_FILE = _env("JARVIS_CRON_JOBS_FILE", "cron/jobs.json")

    # --- Menú semanal ---
    MENU_FILE = _env("JARVIS_MENU_FILE", "menu_diario.md")

    # --- Estado del sistema (caché por servicio) ---
    # Cada servicio (tiempo, fútbol, saldo, docker...) se consulta como mucho
    # cada STATUS_TTL segundos. El chat usa smart_context(): solo consulta los
    # servicios que la pregunta menciona; el panel comparte la misma caché.
    STATUS_TTL = int(_env("JARVIS_STATUS_TTL", "120"))

    # --- Memoria persistente de JARVIS (whitelist: SOLO estos 3 archivos) ---
    MEMORY_DIR = _env("JARVIS_MEMORY_DIR", "memoria")
    MEMORY_FILES = {
        "recuerdos": os.path.join(MEMORY_DIR, "recuerdos.md"),
        "preferencias": os.path.join(MEMORY_DIR, "preferencias.md"),
        "estado": os.path.join(MEMORY_DIR, "estado.md"),
    }

    # --- Voz: Fish Audio (nube) ---
    # Es el motor principal. Sustituye a los TTS locales (XTTS/CosyVoice/F5):
    # no hay que descargar 3 GB de PyTorch ni hace falta GPU, y responde en
    # menos de un segundo en vez de tardar 30 s en arrancar.
    FISH_API_KEY = _env("FISH_API_KEY", "")
    FISH_VOICE_ID = _env("FISH_VOICE_ID", "5bb94403e2a44a0fb0ae2829e97cdeda")
    FISH_SPEED = float(_env("FISH_SPEED", "1.0"))
    try:
        FISH_VOLUME = float(_env("FISH_VOLUME", "0") or 0)
    except ValueError:
        FISH_VOLUME = 0.0
    FISH_EMOTION = _env("FISH_EMOTION", "calm")
    PERSONALIDAD = (_env("PERSONALIDAD", "jarvis") or "jarvis").strip().lower()[:40]
    VOZ_NOMBRE = _env("VOZ_NOMBRE", "")[:80]
    FISH_MODEL = _env("FISH_MODEL", "s2.1-pro-free")
    FISH_URL = _env("FISH_URL", "https://api.fish.audio/v1/tts")
    FISH_TIMEOUT = float(_env("FISH_TIMEOUT", "45"))
    FALLBACK_VOICE = _env("JARVIS_FALLBACK_VOICE", "es-ES-AlvaroNeural")
    BRIEFING = _env("JARVIS_BRIEFING", "1") == "1"

    # --- Oído (Whisper). turbo oye nombres; cambiar en Ajustes exige reiniciar. ---
    WHISPER_MODELOS = ("base", "small", "medium", "large-v3-turbo")
    WHISPER_MODEL = _whisper_modelo(_env("JARVIS_WHISPER_MODEL", "large-v3-turbo"))
    WHISPER_BEAM = int(_env("JARVIS_WHISPER_BEAM", "3"))
    # Voice-chat: por defecto TTS por frases SOLAPADO con el LLM (más rápido).
    # Con "1" el TTS espera a la respuesta completa (máxima calidad prosódica).
    VOICE_CHAT_WHOLE = _env("JARVIS_VOICE_CHAT_WHOLE", "0") == "1"

    # Estudio CosyVoice (apagado). Las rutas /api/studio no se usan con Fish.
    CV3_URL = ""
    PC_TTS_URL = ""
    F5_CFG = 2.0
    F5_NFE = 32
    F5_SPEED = 1.0

    # --- Visión (OpenRouter) ---
    OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY", "")
    VISION_MODEL = _env("JARVIS_VISION_MODEL", "google/gemma-4-31b-it:free")

    # --- Coordenadas (el tiempo). Pon las de tu ciudad en el .env. ---
    LAT = _env("JARVIS_LAT", "40.4168")
    LON = _env("JARVIS_LON", "-3.7038")

    # --- Spotify (auth.json — OAuth PKCE; si no existe, la sección se desactiva) ---
    AUTH_FILE = _env("JARVIS_AUTH_FILE", "auth.json")
    SPOTIFY_API = "https://api.spotify.com/v1"
    SPOTIFY_ACCOUNTS = "https://accounts.spotify.com"
    SPOTIFY_CLIENT_ID = _env("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_REDIRECT = _env(
        "SPOTIFY_REDIRECT", "http://127.0.0.1:8080/api/spotify/callback"
    )

    # --- Tuya (luces, tele, aire). LAN si tuya.json tiene ip+key; si no, nube. ---
    TUYA_ACCESS_ID = _env("TUYA_ACCESS_ID", "")
    TUYA_ACCESS_SECRET = _env("TUYA_ACCESS_SECRET", "")
    TUYA_REGION = (_env("TUYA_REGION", "eu") or "eu").strip() or "eu"
    TUYA_DEVICE_ID = _env("TUYA_DEVICE_ID", "")
    TUYA_FILE = _env("TUYA_FILE", "tuya.json")
