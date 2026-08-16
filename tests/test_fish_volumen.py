"""Volumen de Fish por voz: dB en prosody, acotado a -20..20."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config
from app.voice import fish_prosody


def test_volumen_por_defecto_cero():
    prev = getattr(Config, "FISH_VOLUME", 0)
    Config.FISH_VOLUME = 0
    try:
        p = fish_prosody()
        assert p["volume"] == 0
        assert 0.5 <= p["speed"] <= 2.0
    finally:
        Config.FISH_VOLUME = prev


def test_volumen_kratos_positivo():
    prev = getattr(Config, "FISH_VOLUME", 0)
    Config.FISH_VOLUME = 8
    try:
        assert fish_prosody()["volume"] == 8
    finally:
        Config.FISH_VOLUME = prev


def test_volumen_se_acota():
    prev = getattr(Config, "FISH_VOLUME", 0)
    try:
        Config.FISH_VOLUME = 99
        assert fish_prosody()["volume"] == 20
        Config.FISH_VOLUME = -40
        assert fish_prosody()["volume"] == -20
        Config.FISH_VOLUME = "6.5"
        assert fish_prosody()["volume"] == 6.5
    finally:
        Config.FISH_VOLUME = prev


if __name__ == "__main__":
    test_volumen_por_defecto_cero()
    test_volumen_kratos_positivo()
    test_volumen_se_acota()
    print("OK")
