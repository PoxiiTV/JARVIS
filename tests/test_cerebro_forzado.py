"""Selector Auto / Hermes / DeepSeek: fuerza el cerebro sin tocar Spotify."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import brain
from app import hermes_client as hc
from app import services
from app.brain import estado_cerebro, modo_cerebro, quiere_hermes
from app.brain import etiqueta_status_stream


def _guardar():
    return (
        getattr(brain.Config, "CEREBRO", "auto"),
        hc.hermes_disponible,
        hc.chat,
        brain._chat_completion,
        brain.Config.DEEPSEEK_API_KEY,
        brain.Config.HERMES_FALLBACK,
    )


def _restaurar(orig):
    cerebro, disp, chat, ds, key, fb = orig
    brain.Config.CEREBRO = cerebro
    hc.hermes_disponible = disp
    hc.chat = chat
    brain._chat_completion = ds
    brain.Config.DEEPSEEK_API_KEY = key
    brain.Config.HERMES_FALLBACK = fb
    brain.reset_history()


def test_modo_normaliza():
    orig = brain.Config.CEREBRO if hasattr(brain.Config, "CEREBRO") else "auto"
    try:
        brain.Config.CEREBRO = "HERMES"
        assert modo_cerebro() == "hermes"
        brain.Config.CEREBRO = "foo"
        assert modo_cerebro() == "auto"
        brain.Config.CEREBRO = "deepseek"
        assert modo_cerebro() == "deepseek"
    finally:
        brain.Config.CEREBRO = orig


def test_quiere_hermes_segun_modo():
    orig = brain.Config.CEREBRO if hasattr(brain.Config, "CEREBRO") else "auto"
    try:
        brain.Config.CEREBRO = "auto"
        assert not quiere_hermes("cómo estás")
        assert quiere_hermes("crea un html en el escritorio")
        brain.Config.CEREBRO = "hermes"
        assert quiere_hermes("cómo estás")
        brain.Config.CEREBRO = "deepseek"
        assert not quiere_hermes("crea un html en el escritorio")
        assert not quiere_hermes("cómo estás")
    finally:
        brain.Config.CEREBRO = orig
        brain._ultimo_hermes = False


def test_forzar_hermes_manda_charla():
    orig = _guardar()
    hc.hermes_disponible = lambda: True
    brain.Config.CEREBRO = "hermes"
    called = {"h": 0}

    def fake_h(*a, **k):
        called["h"] += 1
        return {"reply": "En forma, señor.", "usage": {}}

    hc.chat = fake_h
    brain._chat_completion = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no DeepSeek")
    )
    brain.reset_history()
    try:
        out = brain.chat("cómo estás")
        assert called["h"] == 1
        assert out.get("reply") == "En forma, señor."
    finally:
        _restaurar(orig)


def test_forzar_deepseek_salta_hermes():
    orig = _guardar()
    hc.hermes_disponible = lambda: True
    brain.Config.CEREBRO = "deepseek"
    brain.Config.DEEPSEEK_API_KEY = "test"
    hc.chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Hermes"))

    def fake_ds(messages, model, tools=None, timeout=60):
        return {
            "choices": [{"message": {"content": "Sin tools aquí.", "role": "assistant"}}],
            "usage": {},
        }

    brain._chat_completion = fake_ds
    brain.reset_history()
    try:
        out = brain.chat("crea un html en el escritorio")
        assert "tools" in (out.get("reply") or "").lower() or "Sin tools" in (out.get("reply") or "")
        assert "error" not in out
    finally:
        _restaurar(orig)


def test_spotify_con_hermes_forzado():
    orig = _guardar()
    brain.Config.CEREBRO = "hermes"
    hc.hermes_disponible = lambda: True
    hc.chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Hermes"))
    brain.reset_history()
    try:
        with patch.object(services, "spotify_action", return_value={}):
            out = brain.chat("pon comfortably numb")
        assert "Pongo comfortably numb" in (out.get("reply") or "")
    finally:
        _restaurar(orig)


def test_estado_forzado():
    orig = _guardar()
    try:
        hc.hermes_disponible = lambda: True
        brain.Config.CEREBRO = "deepseek"
        e = estado_cerebro()
        assert e["cerebro"] == "deepseek"
        assert e["cerebro_modo"] == "deepseek"
        brain.Config.CEREBRO = "hermes"
        e = estado_cerebro()
        assert e["cerebro"] == "hermes"
        assert e["cerebro_modo"] == "hermes"
        brain.Config.CEREBRO = "auto"
        e = estado_cerebro()
        assert e["cerebro"] == "hermes"
        assert e["cerebro_modo"] == "auto"
    finally:
        _restaurar(orig)


def test_stream_status_usa_quiere_hermes():
    orig = brain.Config.CEREBRO
    brain.Config.CEREBRO = "hermes"
    try:
        assert brain.quiere_hermes("cómo estás") is True
        # El worker del stream debe usar quiere_hermes, no necesita_hermes.
        assert brain.necesita_hermes("cómo estás") is False
    finally:
        brain.Config.CEREBRO = orig


def test_etiqueta_status_respeta_forzado():
    orig = brain.Config.CEREBRO
    try:
        brain.Config.CEREBRO = "hermes"
        assert brain.etiqueta_status_stream("cómo estás") == "Hermes…"
        brain.Config.CEREBRO = "deepseek"
        assert brain.etiqueta_status_stream("crea un html en el escritorio") == "Respondiendo…"
        brain.Config.CEREBRO = "auto"
        assert brain.etiqueta_status_stream("cómo estás") == "Respondiendo…"
        assert brain.etiqueta_status_stream("haz ping a google.com") == "Hermes…"
    finally:
        brain.Config.CEREBRO = orig


if __name__ == "__main__":
    test_modo_normaliza()
    test_quiere_hermes_segun_modo()
    test_forzar_hermes_manda_charla()
    test_forzar_deepseek_salta_hermes()
    test_spotify_con_hermes_forzado()
    test_estado_forzado()
    test_stream_status_usa_quiere_hermes()
    test_etiqueta_status_respeta_forzado()
    print("OK")
