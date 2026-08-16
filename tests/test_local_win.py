"""Acciones de este Windows: solo URLs http(s), sin fingir."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.local_win import url_permitida


def test_url_http_ok():
    assert url_permitida("https://example.com")
    assert url_permitida("http://127.0.0.1:8080")
    assert not url_permitida("file:///c:/windows/system32")
    assert not url_permitida("javascript:alert(1)")
    assert not url_permitida("")


if __name__ == "__main__":
    test_url_http_ok()
    print("OK")
