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


if __name__ == "__main__":
    test_primera_frase_estable()
    print("OK")
