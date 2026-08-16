"""Órdenes de casa van a Tuya en este PC, no a Hermes."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tuya import cumplir_tuya, orden_tuya


def test_enciende_dormitorio():
    assert orden_tuya("enciende el dormitorio") == {"device": "dormitorio", "on": True}
    assert orden_tuya("apaga luz dormitorio") == {"device": "dormitorio", "on": False}


def test_enciende_leds_salon():
    assert orden_tuya("enciende leds salon") == {"device": "luces_salon", "on": True}


def test_codigo_onoff_tira_led():
    from app.tuya import _codigo_onoff
    st = {"result": [{"code": "switch_led", "value": False}, {"code": "work_mode", "value": "colour"}]}
    assert _codigo_onoff(st) == "switch_led"


def test_codigo_onoff_enchufe():
    from app.tuya import _codigo_onoff
    assert _codigo_onoff({"result": [{"code": "switch_1", "value": True}]}) == "switch_1"


def test_apaga_luces_salon():
    assert orden_tuya("apaga las luces del salón") == {"device": "luces_salon", "on": False}


def test_pon_luces_es_casa_no_spotify():
    assert orden_tuya("pon las luces del salón") == {"device": "luces_salon", "on": True}


def test_enciende_salon_son_las_luces():
    assert orden_tuya("enciende el salón") == {"device": "luces_salon", "on": True}


def test_typo_enciede_luz_salon():
    assert orden_tuya("enciede luz salon") == {"device": "luces_salon", "on": True}


def test_luz_y_luces_salon_son_el_mismo():
    assert orden_tuya("enciende luz salon") == {"device": "luces_salon", "on": True}
    assert orden_tuya("apaga luz salon") == {"device": "luces_salon", "on": False}
    assert orden_tuya("apaga luces salon") == {"device": "luces_salon", "on": False}


def test_whisper_tuerce_leds():
    for t in (
        "enciende lets salon",
        "enciende les salon",
        "enciende led salon",
        "apaga the salon",
        "enciende las luces",
    ):
        o = orden_tuya(t)
        assert o and o["device"] == "luces_salon", t


def test_tele_y_aire():
    assert orden_tuya("enciende la tele") == {"device": "tele", "on": True}
    assert orden_tuya("apaga el aire") == {"device": "aire", "on": False}
    assert orden_tuya("apaga el aire acondicionado") == {"device": "aire", "on": False}


def test_ids_salen_de_tuya_json_no_del_codigo():
    from app.tuya import APARATOS, _id_de
    assert set(APARATOS) == {"dormitorio", "luces_salon", "tele", "aire"}
    for d in APARATOS.values():
        assert not d.get("id")
    assert "luz_salon" not in APARATOS
    with patch("app.tuya._mapa_local", return_value={}):
        assert _id_de("dormitorio") == ""


def test_no_es_casa():
    assert orden_tuya("qué hora es") is None
    assert orden_tuya("pon comfortably numb") is None
    assert orden_tuya("pon quevedo") is None
    assert orden_tuya("crea un html en el escritorio") is None


def test_nube_avisa_si_esta_offline():
    from app.tuya import _nube_switch

    class Fake:
        def getstatus(self, _did):
            return {"result": [{"code": "switch_1", "value": False}], "success": True}

        def getconnectstatus(self, _did):
            return False

        def sendcommand(self, *_a, **_k):
            raise AssertionError("no mandar a un aparato sin conexion")

    with patch("app.tuya._cloud", return_value=Fake()), patch("app.tuya._id_de", return_value="x"):
        try:
            _nube_switch("luces_salon", True)
            assert False, "debia fallar"
        except RuntimeError as e:
            assert "conexion" in str(e).lower() or "conexión" in str(e).lower()


def test_cumplir_sin_clave_es_honesto():
    with patch("app.tuya._enviar", side_effect=RuntimeError("falta tuya")):
        r = cumplir_tuya("enciende el dormitorio")
    assert "Tuya" in r or "tuya" in r.lower()


def test_cumplir_enciende():
    with patch("app.tuya._enviar", return_value=None):
        r = cumplir_tuya("apaga las luces del salón")
    assert "salón" in r.lower() or "salon" in r.lower()


def test_chat_no_va_a_hermes():
    from app import brain
    from app import hermes_client as hc

    orig = hc.chat
    hc.chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe ir a Hermes"))
    brain.reset_history()
    try:
        with patch("app.tuya._enviar", return_value=None):
            out = brain.chat("enciende el dormitorio")
        assert "Dormitorio" in (out.get("reply") or "")
        assert out.get("cost_usd") == 0
    finally:
        hc.chat = orig
        brain.reset_history()


if __name__ == "__main__":
    test_enciende_dormitorio()
    test_enciende_leds_salon()
    test_codigo_onoff_tira_led()
    test_codigo_onoff_enchufe()
    test_apaga_luces_salon()
    test_pon_luces_es_casa_no_spotify()
    test_enciende_salon_son_las_luces()
    test_typo_enciede_luz_salon()
    test_luz_y_luces_salon_son_el_mismo()
    test_whisper_tuerce_leds()
    test_tele_y_aire()
    test_ids_salen_de_tuya_json_no_del_codigo()
    test_no_es_casa()
    test_nube_avisa_si_esta_offline()
    test_cumplir_sin_clave_es_honesto()
    test_cumplir_enciende()
    test_chat_no_va_a_hermes()
    print("OK")
