"""Comprobación mínima de la normalización de texto para TTS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.voice import normalize_for_cv3, normalize_for_tts


def test_normalize():
    # Markdown y emojis fuera, números en palabras
    assert normalize_for_cv3("**Hola** ☀️ tienes 3 avisos") == "Hola tienes tres avisos"
    assert normalize_for_cv3("- Punto uno") == "Punto uno"
    assert normalize_for_cv3("cuesta $10.17") == "cuesta diez dólares con diecisiete centavos"
    assert normalize_for_cv3("sube 20%") == "sube veinte por ciento"
    assert normalize_for_cv3("mira midominio.com") == "mira midominio punto com"
    # F5 además aplica qu→k y el arranque 'Señor,'
    assert normalize_for_tts("¿Qué tal?").startswith("Señor, ")
    assert "ke" in normalize_for_tts("que tal")
    # Sin markdown ni números, el texto se respeta
    assert normalize_for_cv3("Buenos días, Alexis.") == "Buenos días, Alexis."
    # Las etiquetas de emocion de Fish ([happy], [calm]...) tienen que llegar
    # al motor: si se recortan, la voz sale plana.
    assert normalize_for_cv3("[happy] Hola, senor.") == "[happy] Hola, senor."


def test_normalize_no_lee_backticks_ni_rutas():
    t = normalize_for_cv3(
        "El archivo está en `~/Desktop/hola.html`."
    )
    assert "`" not in t
    assert "~" not in t
    assert "el escritorio" in t
    assert "html" in t
    assert "punto" not in t or "html" in t


def test_prepare_fish_text():
    from app.config import Config
    from app.voice import prepare_fish_text
    prev = Config.FISH_EMOTION
    Config.FISH_EMOTION = "calm"
    try:
        assert prepare_fish_text("Hola senor.") == "[calm] Hola senor."
        # Si el cerebro ya puso etiqueta, no se duplica.
        assert prepare_fish_text("[happy] Buenas noticias.") == "[happy] Buenas noticias."
    finally:
        Config.FISH_EMOTION = prev


def test_whisper_turbo_por_defecto():
    from app.config import Config, _whisper_modelo
    assert Config.WHISPER_MODEL == "large-v3-turbo"
    assert Config.WHISPER_BEAM == 3
    assert _whisper_modelo("turbo") == "large-v3-turbo"
    assert _whisper_modelo("small") == "small"
    assert _whisper_modelo("no-existe") == "large-v3-turbo"


if __name__ == "__main__":
    test_normalize()
    test_prepare_fish_text()
    test_normalize_no_lee_backticks_ni_rutas()
    test_whisper_turbo_por_defecto()
    print("OK")
