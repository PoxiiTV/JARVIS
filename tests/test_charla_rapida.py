"""Charla corta no pasa por el agente de Hermes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain import es_charla_rapida
from app import brain
from app import hermes_client as hc


def test_detecta_como_estas():
    for t in ("cómo estás", "¿cómo estás?", "que tal", "hola", "estás ahí"):
        assert es_charla_rapida(t), t


def test_no_es_charla_tareas():
    for t in (
        "pon quevedo",
        "mañana juega el barça",
        "lista los archivos del escritorio",
        "busca noticias",
    ):
        assert not es_charla_rapida(t), t


def test_como_estas_no_llama_hermes():
    orig_h = hc.chat
    orig_d = brain._chat_completion
    orig_key = brain.Config.DEEPSEEK_API_KEY
    hc.chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Hermes"))
    brain.Config.DEEPSEEK_API_KEY = "test"

    def fake_ds(messages, model, tools=None, timeout=60):
        assert tools is None
        return {"choices": [{"message": {"content": "En forma, señor.", "role": "assistant"}}], "usage": {}}

    brain._chat_completion = fake_ds
    brain.reset_history()
    try:
        out = brain.chat("cómo estás")
        assert out.get("reply") == "En forma, señor."
    finally:
        hc.chat = orig_h
        brain._chat_completion = orig_d
        brain.Config.DEEPSEEK_API_KEY = orig_key
        brain.reset_history()


if __name__ == "__main__":
    test_detecta_como_estas()
    test_no_es_charla_tareas()
    test_como_estas_no_llama_hermes()
    print("OK")
