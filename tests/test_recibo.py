"""Recibo: una linea para el HUD, nunca para el TTS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.recibo import parse_recibo, formatear_recibo, recortar_recibo


def test_parse_ok_write():
    r = parse_recibo("WROTE /home/usuario/Escritorio/hola-mundo.html")
    assert r["ok"] is True
    assert r["machine"] == "linux"
    assert r["tool"] == "write"
    assert "hola-mundo" in r["detail"]


def test_formatear_sin_ruta_cruda():
    t = formatear_recibo({
        "ok": True, "machine": "linux", "tool": "write",
        "detail": "Escritorio, hola-mundo.html",
    })
    assert "home" not in t
    assert "hola-mundo" in t


def test_recortar_no_se_habla():
    t = recortar_recibo("Hecho, senor.\nRECIBO: ok write Escritorio/hola.html")
    assert "RECIBO" not in t
    assert "Hecho" in t


def test_parse_linea_recibo():
    r = parse_recibo("Hecho.\nRECIBO: ok write Escritorio/hola-mundo.html")
    assert r["ok"] is True
    assert r["tool"] == "write"
    assert "hola-mundo" in r["detail"]


def test_parse_fail():
    r = parse_recibo("RECIBO: fail write no hay permiso")
    assert r["ok"] is False
    assert r["tool"] == "write"


if __name__ == "__main__":
    test_parse_ok_write()
    test_formatear_sin_ruta_cruda()
    test_recortar_no_se_habla()
    test_parse_linea_recibo()
    test_parse_fail()
    print("OK")
