"""El cliente Hermes solo habla texto final, nunca tool-progress."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.hermes_client import (
    parse_sse_text, hermes_disponible, texto_hablable,
    iter_sse_text, texto_progreso,
)
from app.config import Config


def test_parse_sse_ignora_tool_progress():
    raw = (
        "data: " + json.dumps({
            "choices": [{"delta": {"content": "Señor, "}}]
        }) + "\n\n"
        "event: hermes.tool.progress\n"
        "data: " + json.dumps({"tool": "web_search", "status": "start"}) + "\n\n"
        "data: " + json.dumps({
            "choices": [{"delta": {"content": "hecho."}}]
        }) + "\n\n"
        "data: [DONE]\n\n"
    )
    text, usage = parse_sse_text(raw)
    assert text == "Señor, hecho."
    assert "web_search" not in text


def test_hermes_caido_devuelve_false():
    old_url = Config.HERMES_URL
    old_on = Config.HERMES_ENABLED
    Config.HERMES_URL = "http://127.0.0.1:1/v1"
    Config.HERMES_ENABLED = True
    try:
        assert hermes_disponible() is False
    finally:
        Config.HERMES_URL = old_url
        Config.HERMES_ENABLED = old_on


def test_texto_hablable_quita_envoltorio_hermes():
    raw = (
        "⚠️ The model produced only internal reasoning and no final answer, "
        "despite retries. Its last reasoning, which may contain the answer:\n\n"
        "[happy] No me pico, hombre. Carvis o JARVIS, me da igual."
    )
    assert texto_hablable(raw) == (
        "[happy] No me pico, hombre. Carvis o JARVIS, me da igual."
    )


def test_texto_hablable_envoltorio_con_basura_delante():
    raw = (
        "status\n⚠️ The model produced only internal reasoning and no final "
        "answer, despite retries. Its last reasoning, which may contain the "
        "answer:\n\nListo, señor."
    )
    assert texto_hablable(raw) == "Listo, señor."


def test_texto_hablable_vacio_usa_razonamiento():
    assert texto_hablable("", "Hola, señor.") == "Hola, señor."


def test_texto_hablable_normal():
    assert texto_hablable("En ello, señor.") == "En ello, señor."


def test_progreso_web_no_se_habla_en_el_texto():
    assert "Consultando la red" in texto_progreso({"tool": "web_search"})
    raw = (
        "data: " + json.dumps({
            "choices": [{"delta": {"content": "Señor, "}}]
        }) + "\n\n"
        "event: hermes.tool.progress\n"
        "data: " + json.dumps({"tool": "web_search", "status": "start"}) + "\n\n"
        "data: " + json.dumps({
            "choices": [{"delta": {"content": "hecho."}}]
        }) + "\n\n"
        "data: [DONE]\n\n"
    )
    visto = []

    class Resp:
        def __init__(self):
            self.b = raw.encode()

        def read(self, n):
            if not self.b:
                return b""
            c, self.b = self.b[:n], self.b[n:]
            return c

    ultimo = ""
    for t, _u in iter_sse_text(Resp(), on_progress=visto.append):
        ultimo = t
    assert visto and visto[0].get("tool") == "web_search"
    assert ultimo == "Señor, hecho."


if __name__ == "__main__":
    test_parse_sse_ignora_tool_progress()
    test_hermes_caido_devuelve_false()
    test_texto_hablable_quita_envoltorio_hermes()
    test_texto_hablable_envoltorio_con_basura_delante()
    test_texto_hablable_vacio_usa_razonamiento()
    test_texto_hablable_normal()
    test_progreso_web_no_se_habla_en_el_texto()
    print("OK")
