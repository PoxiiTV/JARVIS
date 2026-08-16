"""Órdenes de Spotify van al widget local, no a Hermes."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import orden_spotify


def test_pon_cancion():
    o = orden_spotify("pon comfortably numb")
    assert o == {"action": "play", "query": "comfortably numb"}


def test_pon_quevedo():
    assert orden_spotify("pon quevedo") == {"action": "play", "query": "quevedo"}
    assert orden_spotify("Yarvis pon quevedo") == {"action": "play", "query": "quevedo"}


def test_ponme_musica_reanuda():
    o = orden_spotify("ponme música")
    assert o == {"action": "play"}


def test_pausa():
    assert orden_spotify("para la música")["action"] == "pause"
    assert orden_spotify("pausa")["action"] == "pause"


def test_salta():
    assert orden_spotify("salta")["action"] == "next"


def test_que_suena():
    assert orden_spotify("qué suena ahora")["action"] == "status"


def test_no_es_musica():
    assert orden_spotify("qué hora es") is None
    assert orden_spotify("mañana juega el barça") is None
    assert orden_spotify("busca noticias") is None


def test_en_el_pc():
    o = orden_spotify("pon queen en el pc")
    assert o["action"] == "play"
    assert o["query"] == "queen"
    assert o["device"] == "pc"


def test_chat_usa_widget_no_hermes():
    from unittest.mock import patch
    from app import brain
    from app import hermes_client as hc
    from app import services

    orig = hc.chat
    hc.chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe ir a Hermes"))
    brain.reset_history()
    try:
        with patch.object(services, "spotify_action", return_value={}):
            out = brain.chat("pon comfortably numb")
        assert "Pongo comfortably numb" in (out.get("reply") or "")
    finally:
        hc.chat = orig
        brain.reset_history()


if __name__ == "__main__":
    test_pon_cancion()
    test_pon_quevedo()
    test_ponme_musica_reanuda()
    test_pausa()
    test_salta()
    test_que_suena()
    test_no_es_musica()
    test_en_el_pc()
    test_chat_usa_widget_no_hermes()
    print("OK")
