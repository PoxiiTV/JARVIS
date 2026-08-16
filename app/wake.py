"""Detector local de 'Yarvis' (castellano) con Vosk. Cero API hasta la orden."""
import io
import json
import re
import unicodedata
import wave
import zipfile
from pathlib import Path

PALABRAS = (
    "yarvis", "yarbis", "jarvis", "jarbis",
    "harvis", "harbis", "llarvis", "llarbis",
    "yavis",
)

# Así suele escribir Vosk el nombre (no está en su diccionario).
_BIGRAMAS = {
    ("ya", "vis"), ("ya", "bis"),
    ("lla", "vis"), ("lla", "bis"),
    ("ja", "vis"), ("ja", "bis"),
    ("ha", "vis"), ("ha", "bis"),
    ("yar", "vis"), ("yar", "bis"),
    ("jar", "vis"), ("jar", "bis"),
}

_MODELO_URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
_MODELO_DIR = Path(__file__).resolve().parents[1] / "models" / "vosk-es-small"

_modelo = None


def _norm(texto: str) -> str:
    s = unicodedata.normalize("NFD", texto or "").lower()
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9ñ\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def es_palabra_clave(texto: str) -> bool:
    n = _norm(texto)
    if not n:
        return False
    compact = n.replace(" ", "")
    for p in PALABRAS:
        if p == "yavis":
            if re.search(r"\byavis\b", n):
                return True
            continue
        if p in compact:
            return True
    toks = n.split()
    for a, b in zip(toks, toks[1:]):
        if (a, b) in _BIGRAMAS:
            return True
        if (a + b) in PALABRAS:
            return True
    return bool(re.search(r"\b(?:ll)?[jhy]ar[vb]is\b", n))


def quitar_clave(texto: str) -> str:
    orig = texto or ""
    m = re.search(
        r"(?:oye\s+)?(?:ll)?[jhyg]ar[vb]is\b|"
        r"(?:oye\s+)?(?:ya|lla|ja|ha|yar|jar|gar)\s+[rb]?[vb]is\b|"
        r"\byavis\b",
        orig,
        re.I,
    )
    if not m:
        return orig.strip()
    return orig[m.end():].lstrip(" ,.:;")


def pcm16_a_wav(pcm: bytes, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _rms(pcm: bytes) -> float:
    if len(pcm) < 4:
        return 0.0
    n = len(pcm) // 2
    acc = 0
    for i in range(0, n * 2, 2):
        s = int.from_bytes(pcm[i:i + 2], "little", signed=True)
        acc += s * s
    return (acc / n) ** 0.5 / 32768.0


def asegurar_modelo(aviso=None):
    """Descarga el modelo español pequeño la primera vez. Devuelve la ruta."""
    marca = _MODELO_DIR / "am" / "final.mdl"
    if marca.exists():
        return str(_MODELO_DIR)
    if aviso:
        aviso("Descargando detector de Yarvis (una vez, ~40 MB)…")
    _MODELO_DIR.parent.mkdir(parents=True, exist_ok=True)
    zip_path = _MODELO_DIR.parent / "vosk-es-small.zip"
    import urllib.request
    urllib.request.urlretrieve(_MODELO_URL, zip_path)
    if aviso:
        aviso("Preparando el detector…")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(_MODELO_DIR.parent)
    zip_path.unlink(missing_ok=True)
    extraido = _MODELO_DIR.parent / "vosk-model-small-es-0.42"
    if extraido.exists() and extraido != _MODELO_DIR:
        if _MODELO_DIR.exists():
            import shutil
            shutil.rmtree(_MODELO_DIR)
        extraido.rename(_MODELO_DIR)
    if not marca.exists():
        raise RuntimeError("El modelo Vosk no se descomprimió bien")
    return str(_MODELO_DIR)


def _get_modelo():
    global _modelo
    if _modelo is None:
        from vosk import Model
        _modelo = Model(asegurar_modelo())
    return _modelo


def _nuevo_reconocedor():
    from vosk import KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    rec = KaldiRecognizer(_get_modelo(), 16000)
    rec.SetWords(True)
    return rec


class SesionWake:
    """Una conexión de micro: Vosk para el nombre, Whisper solo para la orden."""

    RATE = 16000
    PRE_ROLL = RATE * 2 * 2          # 2 s en bytes int16
    UMBRAL = 0.015
    SILENCIO_S = 0.5
    MAX_ORDEN_S = 8.0

    def __init__(self):
        self.rec = _nuevo_reconocedor()
        self.ring = bytearray()
        self.acc = bytearray()
        self.fase = "wake"           # wake | rec
        self.orden = bytearray()
        self.t_fase = 0.0
        self.silencio_s = 0.0
        self.pausado = False

    def _texto_vosk(self, pcm: bytes) -> str:
        partes = []
        if self.rec.AcceptWaveform(pcm):
            partes.append(json.loads(self.rec.Result()).get("text") or "")
        else:
            partes.append(json.loads(self.rec.PartialResult()).get("partial") or "")
        return " ".join(partes).strip()

    def _reset_wake(self):
        self.rec = _nuevo_reconocedor()
        self.fase = "wake"
        self.orden = bytearray()
        self.acc = bytearray()
        self.t_fase = 0.0
        self.silencio_s = 0.0

    def _push_ring(self, pcm: bytes):
        self.ring += pcm
        extra = len(self.ring) - self.PRE_ROLL
        if extra > 0:
            del self.ring[:extra]

    def feed(self, pcm: bytes, dt: float):
        """Procesa un trozo PCM s16le 16 kHz. Devuelve un evento o None."""
        if self.pausado or not pcm:
            return None
        self.acc += pcm
        ev = None
        # Vosk trabaja mejor con ~0.25 s (8000 bytes int16).
        while len(self.acc) >= 8000:
            trozo = bytes(self.acc[:8000])
            del self.acc[:8000]
            dt_t = (len(trozo) / 2) / 16000.0
            ev2 = self._feed_trozo(trozo, dt_t)
            if ev2:
                ev = ev2
        return ev

    def _feed_trozo(self, pcm: bytes, dt: float):
        self._push_ring(pcm)
        rms = _rms(pcm)

        if self.fase == "wake":
            texto = self._texto_vosk(pcm)
            if es_palabra_clave(texto):
                self.fase = "rec"
                self.orden = bytearray(self.ring)
                self.t_fase = 0.0
                self.silencio_s = 0.0
                return {"event": "wake", "heard": texto}
            return None

        self.orden += pcm
        self.t_fase += dt
        if rms >= self.UMBRAL:
            self.silencio_s = 0.0
        else:
            self.silencio_s += dt
        if self.silencio_s >= self.SILENCIO_S or self.t_fase >= self.MAX_ORDEN_S:
            return self._cerrar_orden()
        return None

    def _cerrar_orden(self):
        wav = pcm16_a_wav(bytes(self.orden), self.RATE)
        self._reset_wake()
        if len(wav) < 400:
            return {"event": "timeout"}
        from . import voice
        tr = voice.stt(wav)
        if tr.get("error"):
            return {"event": "error", "text": tr["error"]}
        bruto = (tr.get("text") or "").strip()
        orden = quitar_clave(bruto).strip()
        if not orden:
            return {"event": "timeout"}
        return {"event": "order", "text": orden, "heard": bruto}
