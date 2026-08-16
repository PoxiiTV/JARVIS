"""Config carga el .env sin pisar variables ya puestas."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import _cargar_dotenv


def test_cargar_env_no_pisa_lo_ya_puesto():
    d = Path(tempfile.mkdtemp())
    f = d / ".env"
    f.write_text("HERMES_KEY=desde-archivo\nFOO_TEST_JARVIS=abc\n", encoding="utf-8")
    os.environ["HERMES_KEY"] = "ya-estaba"
    os.environ.pop("FOO_TEST_JARVIS", None)
    try:
        _cargar_dotenv(str(f))
        assert os.environ["HERMES_KEY"] == "ya-estaba"
        assert os.environ["FOO_TEST_JARVIS"] == "abc"
    finally:
        os.environ.pop("FOO_TEST_JARVIS", None)
        if os.environ.get("HERMES_KEY") == "ya-estaba":
            os.environ.pop("HERMES_KEY", None)


if __name__ == "__main__":
    test_cargar_env_no_pisa_lo_ya_puesto()
    print("OK")
