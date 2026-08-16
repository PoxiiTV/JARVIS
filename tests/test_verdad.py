"""El HUD Windows es puente: ping y navegador los hace Hermes, no este PC."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain import SYSTEM_PROMPT, _mensajes_base


def test_prompt_hermes_no_inventar():
    t = SYSTEM_PROMPT.lower()
    assert "no tienes terminal" not in t
    assert "nunca inventes" in t
    assert "hermes" in t
    assert "puente" in t


def test_mensajes_no_miden_en_windows():
    msgs = _mensajes_base("haz ping a google.com", None)
    bloque = "\n".join(m["content"] for m in msgs if m["role"] == "system")
    assert "HECHOS MEDIDOS" not in bloque
    assert "tiempo=15ms" not in bloque


if __name__ == "__main__":
    test_prompt_hermes_no_inventar()
    test_mensajes_no_miden_en_windows()
    print("OK")
