"""El cerebro a veces deja content vacío y mete el texto en reasoning."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain import _reply_from_msg


def test_reply_usa_content():
    assert _reply_from_msg({"content": "Hola señor."}) == "Hola señor."


def test_reply_vacio_usa_razonamiento():
    msg = {
        "content": "",
        "reasoning_content": "Voy a mirar el calendario.\nEl Barça juega mañana a las 21:00.",
    }
    assert _reply_from_msg(msg) == "El Barça juega mañana a las 21:00."


def test_reply_todo_vacio():
    assert _reply_from_msg({"content": None}) == ""
    assert _reply_from_msg({}) == ""


def test_reply_quita_envoltorio_hermes():
    msg = {
        "content": (
            "⚠️ The model produced only internal reasoning and no final answer, "
            "despite retries. Its last reasoning, which may contain the answer:\n\n"
            "No me pico, hombre."
        )
    }
    assert _reply_from_msg(msg) == "No me pico, hombre."


def test_prompt_pide_emocion():
    from app.brain import SYSTEM_PROMPT
    assert "[confident]" in SYSTEM_PROMPT
    assert "[angry]" in SYSTEM_PROMPT
    assert "Una sola etiqueta" in SYSTEM_PROMPT


if __name__ == "__main__":
    test_reply_usa_content()
    test_reply_vacio_usa_razonamiento()
    test_reply_todo_vacio()
    test_reply_quita_envoltorio_hermes()
    test_prompt_pide_emocion()
    print("OK")
