"""Briefing de arranque: hora, tiempo, Hermes. Sin LLM."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.briefing import texto_briefing
from app.config import Config


def test_briefing_manana():
    orig = getattr(Config, "PERSONALIDAD", "jarvis")
    try:
        Config.PERSONALIDAD = "jarvis"
        t = texto_briefing({"weather": {"temp": 18.2}, "cerebro": "hermes"}, 9)
        assert t.startswith("Buenos días")
        assert "18" in t
        assert "orden" in t
    finally:
        Config.PERSONALIDAD = orig


def test_briefing_hermes_caido():
    orig = getattr(Config, "PERSONALIDAD", "jarvis")
    try:
        Config.PERSONALIDAD = "jarvis"
        t = texto_briefing({"weather": {}, "cerebro": "apagado"}, 21)
        assert t.startswith("Buenas noches")
        assert "Hermes no responde" in t
    finally:
        Config.PERSONALIDAD = orig


def test_briefing_fermin_tutea():
    orig = getattr(Config, "PERSONALIDAD", "jarvis")
    try:
        Config.PERSONALIDAD = "fermin"
        t = texto_briefing({"weather": {"temp": 18.2}, "cerebro": "hermes"}, 9)
        assert t.startswith("Buenos días, ¿eh?")
        assert "18" in t
        assert "orden" in t
        assert "tío" not in t
        Config.PERSONALIDAD = "jarvis"
        t = texto_briefing({"weather": {}, "cerebro": "apagado"}, 21)
        assert t.startswith("Buenas noches, señor")
        assert "tío" not in t
    finally:
        Config.PERSONALIDAD = orig


def test_briefing_kratos_y_tobey_no_dicen_senor():
    orig = getattr(Config, "PERSONALIDAD", "jarvis")
    try:
        Config.PERSONALIDAD = "kratos"
        t = texto_briefing({"weather": {"temp": 18.2}, "cerebro": "hermes"}, 9)
        assert "señor" not in t
        assert "tío" not in t
        assert "18" in t
        Config.PERSONALIDAD = "tobey"
        t = texto_briefing({"weather": {}, "cerebro": "apagado"}, 21)
        assert "señor" not in t
        assert "Hermes no responde" in t
        Config.PERSONALIDAD = "amador"
        t = texto_briefing({"weather": {"temp": 18.2}, "cerebro": "hermes"}, 9)
        assert "señor" not in t
        assert "18" in t
        Config.PERSONALIDAD = "saul"
        t = texto_briefing({"weather": {"temp": 18.2}, "cerebro": "hermes"}, 9)
        assert "señor" not in t
        assert "bro" in t.lower()
        assert "18" in t
        Config.PERSONALIDAD = "sergio"
        t = texto_briefing({"weather": {"temp": 18.2}, "cerebro": "hermes"}, 9)
        assert "señor" not in t
        assert "brother" in t.lower()
        assert "18" in t
    finally:
        Config.PERSONALIDAD = orig


if __name__ == "__main__":
    test_briefing_manana()
    test_briefing_hermes_caido()
    test_briefing_fermin_tutea()
    test_briefing_kratos_y_tobey_no_dicen_senor()
    print("OK")
