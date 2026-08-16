"""Hermes solo si hace falta el portátil. El resto va en este PC."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain import necesita_hermes, quiere_hermes, pide_vision, maquina_objetivo
from app import brain
from app import hermes_client as hc


def test_hermes_para_el_portatil():
    for t in (
        "haz ping a google.com",
        "abre chrome",
        "crea un html en el escritorio",
        "lista los archivos del escritorio",
        "abre el navegador",
        "ejecuta un comando en linux",
        "necesito que me crees un .html que ponga hola mundo pero estilo apple en el escritorio",
        "crea un html de hola mundo estilo apple",
        "crees un archivo txt con la lista",
    ):
        assert necesita_hermes(t), t


def test_seguimiento_tras_hermes():
    """Si Hermes acaba de actuar, el reproche sigue en el portátil."""
    brain._ultimo_hermes = True
    try:
        assert necesita_hermes("no has creado nada")
        assert necesita_hermes("hazlo de verdad")
        assert not necesita_hermes("cómo estás")
    finally:
        brain._ultimo_hermes = False


def test_local_para_lo_demas():
    for t in (
        "cómo estás",
        "qué tiempo hace",
        "busca noticias del barça",
        "recuerda que odio los rodeos",
        "qué hora es",
        "qué hay de menú hoy",
    ):
        assert not necesita_hermes(t), t


def test_noticias_no_van_a_hermes():
    orig_h = hc.chat
    orig_d = brain._chat_completion
    orig_key = brain.Config.DEEPSEEK_API_KEY
    orig_disp = hc.hermes_disponible
    hc.hermes_disponible = lambda: True
    hc.chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Hermes"))
    brain.Config.DEEPSEEK_API_KEY = "test"

    def fake_ds(messages, model, tools=None, timeout=60):
        return {
            "choices": [{"message": {"content": "Según Marca, juega mañana.", "role": "assistant"}}],
            "usage": {},
        }

    brain._chat_completion = fake_ds
    brain.reset_history()
    try:
        out = brain.chat("busca noticias del barça")
        assert "Marca" in (out.get("reply") or "")
    finally:
        hc.chat = orig_h
        brain._chat_completion = orig_d
        brain.Config.DEEPSEEK_API_KEY = orig_key
        hc.hermes_disponible = orig_disp
        brain.reset_history()


def test_escritorio_es_xdg_no_carpeta_nueva():
    m = brain._MSG_HERMES_ACCION.lower()
    assert "xdg-user-dir" in m
    assert "desktop" in m
    assert "no crees una carpeta" in m or "nunca crees una carpeta" in m


def test_reproche_sigue_en_hermes():
    orig_h = hc.chat
    orig_d = brain._chat_completion
    orig_disp = hc.hermes_disponible
    called = {"hermes": 0, "deepseek": 0}
    hc.hermes_disponible = lambda: True

    def fake_h(messages, timeout=180, stream=False, on_fragment=None, on_progress=None):
        called["hermes"] += 1
        joined = " ".join(m.get("content") or "" for m in messages if m.get("role") == "system")
        assert "MODO VOZ" not in joined
        assert "LINUX" in joined.upper() or "portátil" in joined.lower() or "tool" in joined.lower()
        return {"reply": "Creado.", "usage": {}}

    def boom(*a, **k):
        called["deepseek"] += 1
        raise AssertionError("no deberia llamar a DeepSeek")

    hc.chat = fake_h
    brain._chat_completion = boom
    brain.reset_history()
    try:
        brain.chat("crea un html de hola mundo estilo apple")
        brain.chat("no has creado nada")
        assert called["hermes"] == 2
        assert called["deepseek"] == 0
    finally:
        hc.chat = orig_h
        brain._chat_completion = orig_d
        hc.hermes_disponible = orig_disp
        brain.reset_history()


def test_vision_es_local():
    orig = brain.Config.CEREBRO
    brain.Config.CEREBRO = "auto"
    try:
        for t in ("qué ves", "mira la cámara", "describe lo que hay", "qué tengo delante"):
            assert pide_vision(t), t
        assert not pide_vision("cómo estás")
        assert not pide_vision("crea un html en el escritorio")
    finally:
        brain.Config.CEREBRO = orig


def test_captura_este_pc_no_es_hermes():
    orig = brain.Config.CEREBRO
    brain.Config.CEREBRO = "auto"
    try:
        t = "haz una captura de este pc"
        assert not quiere_hermes(t)
    finally:
        brain.Config.CEREBRO = orig


def test_maquina_objetivo():
    assert maquina_objetivo("abre chrome en el portátil") == "linux"
    assert maquina_objetivo("sube el volumen de este pc") == "windows"
    assert maquina_objetivo("cómo estás") == "auto"


if __name__ == "__main__":
    test_hermes_para_el_portatil()
    test_seguimiento_tras_hermes()
    test_local_para_lo_demas()
    test_noticias_no_van_a_hermes()
    test_escritorio_es_xdg_no_carpeta_nueva()
    test_reproche_sigue_en_hermes()
    test_vision_es_local()
    test_captura_este_pc_no_es_hermes()
    test_maquina_objetivo()
    print("OK")
