"""MCP jarvis llama a las funciones que ya existen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mcp_jarvis import dispatch


def test_recordar_preferencias():
    seen = {}
    import app.mcp_jarvis as m
    orig = m.append_memory

    def fake(cat, nota):
        seen.update(cat=cat, nota=nota)
        return True

    m.append_memory = fake
    try:
        out = dispatch("recordar", {"categoria": "preferencias", "nota": "si te insulto, igual"})
        assert out["ok"] is True
        assert seen["cat"] == "preferencias"
        assert "insulto" in seen["nota"]
    finally:
        m.append_memory = orig


def test_tool_desconocida():
    out = dispatch("format_c", {})
    assert out["ok"] is False


def test_avisar_queda_en_status():
    import tempfile
    from pathlib import Path
    from app import mcp_jarvis, services
    d = Path(tempfile.mkdtemp())
    orig = getattr(services, "AVISOS_FILE", None)
    services.AVISOS_FILE = d / "avisos.json"
    try:
        out = mcp_jarvis.dispatch("avisar", {"texto": "el backup acabo"})
        assert out.get("ok") is True
        avisos = services.leer_avisos()
        assert avisos[0]["texto"] == "el backup acabo"
    finally:
        services.AVISOS_FILE = orig


if __name__ == "__main__":
    test_recordar_preferencias()
    test_tool_desconocida()
    test_avisar_queda_en_status()
    print("OK")
