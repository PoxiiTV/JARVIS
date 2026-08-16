"""Si Hermes esta arriba, brain no llama a DeepSeek directo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import brain
from app import hermes_client as hc


def test_chat_por_hermes():
    orig_disp = hc.hermes_disponible
    orig_chat = hc.chat
    orig_ds = brain._chat_completion
    called = {"deepseek": False}

    hc.hermes_disponible = lambda: True

    def fake_chat(messages, timeout=180, stream=False, on_fragment=None, on_progress=None):
        return {"reply": "A la orden.", "usage": {"prompt_tokens": 10, "completion_tokens": 4}}

    hc.chat = fake_chat

    def boom(*a, **k):
        called["deepseek"] = True
        raise AssertionError("no deberia llamar a DeepSeek")

    brain._chat_completion = boom
    brain.reset_history()
    try:
        out = brain.chat("lista los archivos del escritorio")
        assert called["deepseek"] is False
        assert out.get("reply") == "A la orden."
        assert "error" not in out
    finally:
        hc.hermes_disponible = orig_disp
        hc.chat = orig_chat
        brain._chat_completion = orig_ds
        brain.reset_history()


def test_hermes_apagado_avisa():
    orig_disp = hc.hermes_disponible
    orig_fb = brain.Config.HERMES_FALLBACK
    orig_ds = brain._chat_completion
    hc.hermes_disponible = lambda: False
    brain.Config.HERMES_FALLBACK = False

    def boom(*a, **k):
        raise AssertionError("no deberia llamar a OpenRouter")

    brain._chat_completion = boom
    brain.reset_history()
    try:
        out = brain.chat("lista los archivos del escritorio")
        assert "Hermes apagado" in (out.get("error") or "")
        assert "reply" not in out
    finally:
        hc.hermes_disponible = orig_disp
        brain.Config.HERMES_FALLBACK = orig_fb
        brain._chat_completion = orig_ds
        brain.reset_history()


def test_hermes_apagado_con_reserva():
    orig_disp = hc.hermes_disponible
    orig_fb = brain.Config.HERMES_FALLBACK
    orig_key = brain.Config.DEEPSEEK_API_KEY
    orig_ds = brain._chat_completion
    hc.hermes_disponible = lambda: False
    brain.Config.HERMES_FALLBACK = True
    brain.Config.DEEPSEEK_API_KEY = "test"

    def fake_ds(messages, model, tools=None, timeout=60):
        return {"choices": [{"message": {"content": "Reserva.", "role": "assistant"}}], "usage": {}}

    brain._chat_completion = fake_ds
    brain.reset_history()
    try:
        out = brain.chat("hola")
        assert out.get("reply") == "Reserva."
    finally:
        hc.hermes_disponible = orig_disp
        brain.Config.HERMES_FALLBACK = orig_fb
        brain.Config.DEEPSEEK_API_KEY = orig_key
        brain._chat_completion = orig_ds
        brain.reset_history()


if __name__ == "__main__":
    test_chat_por_hermes()
    test_hermes_apagado_avisa()
    test_hermes_apagado_con_reserva()
    print("OK")
