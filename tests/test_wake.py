"""Palabra clave en castellano: yarvis / yarbis y variantes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.wake import SesionWake, es_palabra_clave, quitar_clave


def test_detecta_castellano():
    for t in (
        "yarvis",
        "Yarvis",
        "yarbis",
        "YARBIS",
        "jarvis",
        "jarbis",
        "harvis",
        "harbis",
        "llarvis",
        "llarbis",
        "yavis",
        "oye yarvis",
        "a ver yarvis qué hora es",
        "yarbis pon musica",
        "ya vis",
        "ya bis",
        "ya vis qué hora es",
    ):
        assert es_palabra_clave(t), t


def test_no_detecta_otras():
    for t in (
        "",
        "hola",
        "qué hora es",
        "llaves",
        "ya ves",
        "servicio",
        "jar",
    ):
        assert not es_palabra_clave(t), t


def test_quitar_clave():
    assert quitar_clave("yarvis qué hora es") == "qué hora es"
    assert quitar_clave("yarbis") == ""
    assert quitar_clave("oye yarvis pon música") == "pon música"
    assert quitar_clave("ya vis qué hora es") == "qué hora es"
    assert quitar_clave("ya bis pon musica") == "pon musica"
    assert quitar_clave("Yarvis pon quevedo") == "pon quevedo"
    # Whisper a veces escribe mal Yarvis; no es el nombre, se recorta igual.
    assert quitar_clave("Garbis pon quevedo") == "pon quevedo"


def test_silencio_ordena_a_0_5s():
    assert SesionWake.SILENCIO_S == 0.5


if __name__ == "__main__":
    test_detecta_castellano()
    test_no_detecta_otras()
    test_quitar_clave()
    test_silencio_ordena_a_0_5s()
    print("OK")
