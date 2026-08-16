"""Voz del dashboard: TTS (PC F5-TTS → fallback Álvaro edge-tts) y STT (Whisper).

Reglas de texto (aprendidas): texto plano seguido, sin párrafos ni saltos de
línea; evitar empezar la frase con "¿Qué" (suena "qe"); convertir números a
palabras en español (F5 lee los dígitos en inglés: "10.17" → "diez coma diecisiete").
"""
import io
import os
import re
import time as _time
import urllib.request
import urllib.error

from .config import Config


# ---------------------------------------------------------------- números a español

_UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
             "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
             "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve"]
_DECENAS = ["", "diez", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta",
            "setenta", "ochenta", "noventa"]
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos",
             "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"]
_VEINTI = ["veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco",
           "veintiséis", "veintisiete", "veintiocho", "veintinueve"]


def _int_to_es(n: int) -> str:
    if n < 0:
        return "menos " + _int_to_es(-n)
    if n < 20:
        return _UNIDADES[n]
    if n < 30:
        return _VEINTI[n - 20]
    if n < 100:
        d, u = divmod(n, 10)
        return _DECENAS[d] + (" y " + _UNIDADES[u] if u else "")
    if n < 1000:
        c, r = divmod(n, 100)
        if n == 100:
            return "cien"
        return _CENTENAS[c] + (" " + _int_to_es(r) if r else "")
    if n < 1_000_000:
        m, r = divmod(n, 1000)
        base = "mil" if m == 1 else _int_to_es(m) + " mil"
        return base + (" " + _int_to_es(r) if r else "")
    if n < 1_000_000_000:
        M, r = divmod(n, 1_000_000)
        base = "un millón" if M == 1 else _int_to_es(M) + " millones"
        return base + (" " + _int_to_es(r) if r else "")
    return str(n)  # no soportado, dejarlo como está


def _num_words(raw: str, cents_after: bool) -> str:
    """'10.17' → 'diez coma diecisiete' o, si es dinero, 'diez con diecisiete'."""
    if "." in raw:
        ent, dec = raw.split(".", 1)
        ent_w = _int_to_es(int(ent)) if ent else "cero"
        dec_w = _int_to_es(int(dec)) if dec else "cero"
        return f"{ent_w} coma {dec_w}"
    return _int_to_es(int(raw))


def _money_words(raw: str) -> str:
    """'10.17' → 'diez dólares con diecisiete centavos'."""
    if "." in raw:
        ent, dec = raw.split(".", 1)
        ent_w = _int_to_es(int(ent)) if ent else "cero"
        cents = int(dec) if dec else 0
        if cents == 0:
            return f"{ent_w} dólares"
        cents_w = _int_to_es(cents) if cents != 1 else "un"
        return f"{ent_w} dólares con {cents_w} centavos"
    return f"{_int_to_es(int(raw))} dólares"


_NUM_RE = re.compile(
    r"(\$\s*)?(\d+(?:\.\d+)?)(\s*(?:%|dólares|dolares|euros|€))?"
)


def _replace_numbers(text: str) -> str:
    def repl(m):
        money = m.group(1)          # "$ " delante
        num = m.group(2)
        suffix = (m.group(3) or "").strip()
        if money:
            return _money_words(num)
        if suffix == "%":
            return _int_to_es(int(float(num))) + " por ciento"
        if suffix:
            return _num_words(num, False) + " " + suffix
        return _num_words(num, False)
    return _NUM_RE.sub(repl, text)


def _expand_dots(text: str) -> str:
    """Expande puntos de dominios/web para que el TTS no se los coma.

    'midominio.com' → 'midominio punto com' (CosyVoice tiende a omitir
    el punto unido a palabras). También limpia esquemas y www.
    """
    # URL completa: https://www.algo.es/x → www.algo.es/x (se expande abajo)
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"\bwww\.", "www punto ", text, flags=re.IGNORECASE)
    # Dominios: algo.com → algo punto com (solo cuando va unido a una palabra)
    text = re.sub(
        r"\b([a-zA-Z0-9-]+)\.(com|es|org|net|io|dev|app|ai|me|tv|info|eu|mobi)\b",
        r"\1 punto \2", text, flags=re.IGNORECASE)
    return text


_FISH_TAG_INI = re.compile(r"^\s*\[[^\]]+\]")


def _humanizar_rutas(text: str) -> str:
    """Rutas de archivo en palabras: la voz no debe leer ~, / ni backticks."""
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(
        r"(?i)~/(Desktop|Escritorio)/(\S+)",
        r"el escritorio, \2",
        text,
    )
    text = re.sub(
        r"(?i)(?:[A-Za-z]:[\\/])?(?:Users|home)[^\\/\s]+[\\/](?:Desktop|Escritorio)[\\/](\S+)",
        r"el escritorio, \1",
        text,
    )
    text = re.sub(r"(?i)(?<!\w)~/", "la carpeta de usuario, ", text)
    text = re.sub(
        r"\.(html?|pdf|txt|md|json|css|js)\b",
        r" \1",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _strip_markup(text: str) -> str:
    """Quita markdown, emojis y símbolos para que la voz no los lea."""
    text = text or ""
    tag = ""
    m = _FISH_TAG_INI.match(text)
    if m:
        tag = m.group(0).strip() + " "
        text = text[m.end():]
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = _humanizar_rutas(text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[`*_#|\\<>^~]", "", text)
    text = text.replace("“", "").replace("”", "").replace("«", "").replace("»", "")
    text = text.replace("‘", "").replace("’", "")
    text = re.sub(r'"([^"]*)"', r"\1", text)
    text = re.sub(
        r"[\U0001F000-\U0001FAFF☀-➿️‍←-⇿⬀-⯿]",
        "", text)
    text = re.sub(r"\s+", " ", tag + text).strip()
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def prepare_fish_text(text: str) -> str:
    """Texto para Fish: limpia markup, conserva [emociones] y aplica la de ajustes."""
    text = normalize_for_cv3(text or "")
    emo = (Config.FISH_EMOTION or "").strip().strip("[]")
    if emo and emo not in ("none", "-") and not _FISH_TAG_INI.match(text):
        text = f"[{emo}] {text}"
    return text


def normalize_for_cv3(text: str) -> str:
    """Texto limpio para CosyVoice 3 y XTTS: numeros a palabras + aplanar.

    CV3 y XTTS pronuncian el espanol correctamente por si mismos (NO necesitan
    los trucos fonéticos de F5: ni qu→k ni prefijo 'Señor,').
    """
    text = _strip_markup(text)
    text = _replace_numbers(text)
    text = _expand_dots(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_tts(text: str) -> str:
    """Texto fonético para F5-TTS: numeros, qu→k, arranque 'Señor,'."""
    text = normalize_for_cv3(text)
    # Evitar arranques problemáticos con F5 ("¿Qué" suena "qe"): anteponer un
    # arranque natural para que el modelo no pronuncie mal la primera palabra.
    if re.match(r"^¿?Qué ", text, re.IGNORECASE):
        text = "Señor, " + text
    # F5-Spanish pronuncia "que/qui" con la U ("qüe"): forzar el sonido /k/
    # reescribiendo fonéticamente qu → k (que→ke, qué→ke, qui→ki, quí→ki).
    # En español la u tras q es muda salvo diéresis (qüe/qüi, casi inexistente),
    # así que el reemplazo es fonéticamente correcto en todo el texto.
    text = re.sub(r"qu(?=[eiéí])", "k", text, flags=re.IGNORECASE)
    return text


def fish_prosody():
    """speed 0.5–2.0 y volume -20..20 dB, como pide la API de Fish."""
    try:
        speed = float(Config.FISH_SPEED or 1.0)
    except (TypeError, ValueError):
        speed = 1.0
    try:
        vol = float(getattr(Config, "FISH_VOLUME", 0) or 0)
    except (TypeError, ValueError):
        vol = 0.0
    return {
        "speed": max(0.5, min(2.0, speed)),
        "volume": max(-20.0, min(20.0, vol)),
    }


def _fish(text: str):
    """Genera audio con Fish Audio (nube). Devuelve bytes WAV o None.

    Es el motor principal: responde en menos de un segundo, no necesita GPU
    ni descargar nada. Se pide WAV (44,1 kHz) en vez de MP3 porque el chat de
    voz concatena frases sueltas, y eso solo funciona con PCM.
    """
    if not Config.FISH_API_KEY:
        return None
    payload = {
        "text": text,
        "reference_id": Config.FISH_VOICE_ID,
        "format": "wav",
        "prosody": fish_prosody(),
    }
    req = urllib.request.Request(
        Config.FISH_URL,
        data=json_dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {Config.FISH_API_KEY}",
            "Content-Type": "application/json",
            "model": Config.FISH_MODEL,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=Config.FISH_TIMEOUT) as r:
        return r.read()


def tts(text: str):
    """Genera audio. Devuelve (bytes, content_type, fuente). Fish, siempre."""
    text_cv3 = normalize_for_cv3(text)
    try:
        wav = _fish(prepare_fish_text(text))
        if wav and len(wav) > 1000:
            return wav, "audio/wav", "fish"
    except Exception:
        pass
    try:
        import asyncio
        import edge_tts

        async def _gen():
            communicate = edge_tts.Communicate(text_cv3, Config.FALLBACK_VOICE)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()

        mp3 = asyncio.run(_gen())
        if mp3 and len(mp3) > 1000:
            return mp3, "audio/mpeg", "alvaro"
    except Exception:
        pass
    try:
        mp3 = _google_tts(text_cv3)
        if mp3:
            return mp3, "audio/mpeg", "google"
    except Exception:
        pass
    return None, None, "error"


def voz_lista() -> bool:
    """¿Hay voz de JARVIS disponible? (Fish configurado y respondiendo)"""
    if not Config.FISH_API_KEY:
        return False
    try:
        return bool(_fish("Listo."))
    except Exception:
        return False


def warmup():
    """Fish no necesita calentamiento."""
    return


def _google_tts(text: str, lang: str = "es"):
    """TTS de Google Translate (sin clave). Máx ~180 caracteres por llamada."""
    import urllib.parse

    chunks = [text[i:i + 180] for i in range(0, len(text), 180)]
    out = io.BytesIO()
    for ch in chunks:
        url = (
            "https://translate.google.com/translate_tts"
            f"?ie=UTF-8&client=tw-ob&tl={lang}&q={urllib.parse.quote(ch)}"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/120.0 Safari/537.36"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            out.write(r.read())
    data = out.getvalue()
    return data if data else None


def json_dumps(obj):
    import json
    return json.dumps(obj)


# ---------------------------------------------------------------- STT

_stt_model = None


def _get_stt():
    """Carga faster-whisper una sola vez (large-v3-turbo por defecto)."""
    global _stt_model
    if _stt_model is None:
        from faster_whisper import WhisperModel
        _stt_model = WhisperModel(Config.WHISPER_MODEL, device="cpu", compute_type="int8")
    return _stt_model


def stt(audio_bytes: bytes):
    """Transcribe audio (wav/ogg/mp3) a texto.

    Optimizado para conversación: vad_filter recorta silencios.
    beam_size viene de Config (3 con el modelo small).
    """
    try:
        model = _get_stt()
    except Exception as e:
        return {"error": f"Whisper no disponible: {e}"}
    try:
        import tempfile
        import os
        # MediaRecorder manda webm/opus, no wav. El sufijo tiene que coincidir
        # o PyAV a veces no abre el contenedor.
        if audio_bytes[:4] == b"RIFF":
            sufijo = ".wav"
        elif audio_bytes[:4] == b"OggS":
            sufijo = ".ogg"
        else:
            sufijo = ".webm"
        with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as f:
            f.write(audio_bytes)
            path = f.name
        try:
            segments, info = model.transcribe(
                path,
                language="es",
                beam_size=Config.WHISPER_BEAM,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            return {"text": text, "language": info.language}
        finally:
            os.unlink(path)
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------- voice chat

import re as _re
import queue as _queue
import threading as _threading
import base64 as _b64
import wave as _wave


def _concat_wavs(chunks, gap_s: float = 0.09):
    """Concatena WAVs PCM (misma tasa/canales/anchura) con silencio entre medias.

    Devuelve bytes del WAV final, o None si algún chunk no es WAV o los
    formatos no coinciden (entonces no se puede concatenar).
    """
    params = None
    frames = b""
    for i, c in enumerate(chunks):
        try:
            w = _wave.open(io.BytesIO(c), "rb")
        except Exception:
            return None
        p = w.getparams()
        if params is None:
            params = p
        elif (p.nchannels, p.sampwidth, p.framerate) != (params.nchannels, params.sampwidth, params.framerate):
            w.close()
            return None
        frames += w.readframes(w.getnframes())
        w.close()
        if i < len(chunks) - 1:
            n = int(params.framerate * gap_s)
            frames += b"\x00" * (n * params.nchannels * params.sampwidth)
    out = io.BytesIO()
    w = _wave.open(out, "wb")
    w.setparams(params)
    w.writeframes(frames)
    w.close()
    return out.getvalue()


def _extract_sentences(acc_text: str, sent_marker: str, min_len: int = 15):
    """Devuelve (frases_listas, nuevo_marker).

    acc_text es el texto acumulado del LLM (prefijos estables en streaming).
    sent_marker es el prefijo ya enviado al TTS. Divide el texto nuevo en
    frases completas (terminadas en . ! ? ; …) y envía todas las que sean
    estables: si la ÚLTIMA frase completa es corta (< min_len) se retiene para
    que coja contexto con lo que viene; las anteriores se envían agrupadas
    (una frase corta se une a la siguiente en una misma tanda).
    """
    if not acc_text.startswith(sent_marker):
        sent_marker = ""
    new = acc_text[len(sent_marker):]
    parts = []
    rest = new
    while True:
        m = _re.search(r"[.!?;…]\s*", rest)
        if not m:
            break
        parts.append(rest[:m.end()])
        rest = rest[m.end():]
    if not parts:
        return [], sent_marker
    send = list(parts)
    if len(parts[-1].strip()) < min_len:
        send = parts[:-1]  # la última es corta e inestable: retenerla
    if not send:
        return [], sent_marker
    ready = " ".join(p.strip() for p in send).strip()
    new_marker = acc_text[:len(sent_marker) + sum(len(p) for p in send)]
    return [ready], new_marker


def voice_chat(audio_bytes: bytes, context: dict = None):
    """STT → LLM (streaming) → TTS por frases SOLAPADO. Devuelve dict:

    {text, reply, audio_b64, ctype, source, cost_usd, timings} o {error}.

    El solapamiento: el hilo del LLM va entregando frases completas mientras
    DeepSeek sigue generando; cada frase se sintetiza al vuelo y los WAVs se
    concatenan. Así la primera voz sale ~3-5 s antes que esperando a todo.
    """
    from . import brain as _brain

    timings = {}

    # 1) STT
    t0 = _time.time()
    tr = stt(audio_bytes)
    timings["stt_s"] = round(_time.time() - t0, 1)
    if "error" in tr or not (tr.get("text") or "").strip():
        return {"error": tr.get("error") or "No se entendió el audio",
                "text": tr.get("text", ""), "timings": timings}
    text = tr["text"].strip()
    # Contexto SOLO de los servicios que la pregunta de voz menciona
    # (tiempo, fútbol, saldo...). Las preguntas recientes del usuario
    # resuelven referencias ("¿y mañana?" tras hablar del tiempo).
    ctx = None
    try:
        from . import services as _svc
        recent = [c for r, c, _ in _brain._history if r == "user"][-2:]
        ctx = _svc.smart_context(text, recent)
    except Exception:
        pass

    # 2) LLM streaming → cola de frases
    q = _queue.Queue()
    llm_result = {}
    sent_marker = ""
    whole = Config.VOICE_CHAT_WHOLE

    def _on_fragment(acc):
        nonlocal sent_marker
        if whole:
            return  # modo texto completo: no solapar
        frases, sent_marker = _extract_sentences(acc, sent_marker)
        for f in frases:
            q.put(f)

    def _llm_worker():
        try:
            res = _brain.chat_stream(text, ctx, on_fragment=_on_fragment, voice_mode=True)
            llm_result.update(res)
        except Exception as e:  # defensivo: chat_stream ya captura casi todo
            llm_result["error"] = str(e)
        finally:
            q.put(None)  # centinela

    t_llm0 = _time.time()
    th = _threading.Thread(target=_llm_worker, daemon=True)
    th.start()

    # 3) Consumidor: TTS de cada frase (o del texto completo al final)
    audio_chunks = []
    source = None
    tts_total = 0.0
    first_audio = None
    while True:
        item = q.get()
        if item is None:
            break
        t0 = _time.time()
        wav, ctype, src = tts(item)
        tts_total += _time.time() - t0
        if wav and len(wav) > 1000:
            if first_audio is None:
                first_audio = (wav, ctype, src)
            audio_chunks.append(wav)
            if source is None:
                source = src
    timings["llm_s"] = round(_time.time() - t_llm0, 1)

    reply = (llm_result.get("reply") or "").strip()
    if "error" in llm_result and not reply:
        return {"error": llm_result["error"], "text": text, "timings": timings}

    # Flush final: texto que quedó sin enviar (frase corta retenida o resto
    # sin terminador) — el LLM ya terminó, ya no va a crecer.
    if not whole and reply and reply.startswith(sent_marker):
        resto = reply[len(sent_marker):].strip()
        if resto:
            t0 = _time.time()
            wav, ctype, src = tts(resto)
            tts_total += _time.time() - t0
            if wav and len(wav) > 1000:
                if first_audio is None:
                    first_audio = (wav, ctype, src)
                audio_chunks.append(wav)
                if source is None:
                    source = src
    timings["tts_s"] = round(tts_total, 1)

    # 4) Montar el audio
    if whole or not audio_chunks:
        # Modo texto completo (o sin frases sueltas): una sola síntesis de todo
        wav, ctype, src = tts(reply)
        timings["tts_s"] = round(tts_total + (1 if wav else 0), 1)
        if wav and len(wav) > 1000:
            return {
                "text": text, "reply": reply,
                "audio_b64": _b64.b64encode(wav).decode(),
                "ctype": ctype, "source": src,
                "cost_usd": llm_result.get("cost_usd", 0),
                "timings": timings,
            }
        return {"error": "No se pudo generar voz", "text": text, "reply": reply,
                "timings": timings}

    audio = _concat_wavs(audio_chunks)
    if audio:
        return {
            "text": text, "reply": reply,
            "audio_b64": _b64.b64encode(audio).decode(),
            "ctype": "audio/wav", "source": source or "cosyvoice3",
            "cost_usd": llm_result.get("cost_usd", 0),
            "timings": timings,
        }
    # No se pudieron concatenar (p.ej. fallback MP3): devolver la primera frase
    if first_audio:
        wav, ctype, src = first_audio
        return {
            "text": text, "reply": reply,
            "audio_b64": _b64.b64encode(wav).decode(),
            "ctype": ctype, "source": src,
            "cost_usd": llm_result.get("cost_usd", 0),
            "timings": timings,
        }
    return {"error": "No se pudo generar voz", "text": text, "reply": reply,
            "timings": timings}
