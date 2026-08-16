"""Las reglas del señor tienen que pisar el tono de mayordomo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain import bloque_sistema_memoria


def test_bloque_obliga_preferencias():
    t = bloque_sistema_memoria()
    assert "OBLIGATORIAS" in t
    assert "preferencias" in t.lower()
    assert "insult" in t.lower() or "tono" in t.lower()


if __name__ == "__main__":
    test_bloque_obliga_preferencias()
    print("OK")
