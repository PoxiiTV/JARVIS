"""Preferencias dichas en claro: se anotan, no se duplican, recuerdos en cola."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.memoria_auto import debe_recordar, nota_desde
from app import brain


def test_no_recuerda_como_estas():
    assert debe_recordar("cómo estás") is False


def test_si_recuerda_regla():
    t = "recuerda que odio los rodeos"
    assert debe_recordar(t) is True
    assert "odio los rodeos" in nota_desde(t)


def test_no_duplica():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "p.md")
    orig = dict(brain.Config.MEMORY_FILES)
    brain.Config.MEMORY_FILES = {
        "preferencias": p,
        "recuerdos": os.path.join(d, "r.md"),
        "estado": os.path.join(d, "e.md"),
    }
    try:
        assert brain.append_memory("preferencias", "odio los rodeos") is True
        assert brain.append_memory("preferencias", "odio los rodeos") is False
        text = open(p, encoding="utf-8").read()
        assert text.count("odio los rodeos") == 1
    finally:
        brain.Config.MEMORY_FILES = orig


def test_recuerdos_solo_cola():
    d = tempfile.mkdtemp()
    rec = os.path.join(d, "recuerdos.md")
    with open(rec, "w", encoding="utf-8") as f:
        f.write("\n".join(f"L{i}" for i in range(80)) + "\n")
    orig = dict(brain.Config.MEMORY_FILES)
    brain.Config.MEMORY_FILES = {
        "recuerdos": rec,
        "preferencias": os.path.join(d, "p.md"),
        "estado": os.path.join(d, "e.md"),
    }
    open(brain.Config.MEMORY_FILES["preferencias"], "w", encoding="utf-8").write("regla\n")
    open(brain.Config.MEMORY_FILES["estado"], "w", encoding="utf-8").write("ok\n")
    try:
        bloque = brain.bloque_sistema_memoria()
        assert "L0" not in bloque
        assert "L79" in bloque
    finally:
        brain.Config.MEMORY_FILES = orig


if __name__ == "__main__":
    test_no_recuerda_como_estas()
    test_si_recuerda_regla()
    test_no_duplica()
    test_recuerdos_solo_cola()
    print("OK")
