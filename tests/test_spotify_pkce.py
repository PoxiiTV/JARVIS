"""PKCE de Spotify no lleva secret; el challenge no lleva padding."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import _pkce_challenge, spotify_login_url
from app.config import Config


def test_pkce_challenge_estable():
    c = _pkce_challenge("abc")
    assert "=" not in c
    assert len(c) >= 40
    assert _pkce_challenge("abc") == c


def test_login_sin_client_id():
    prev = Config.SPOTIFY_CLIENT_ID
    Config.SPOTIFY_CLIENT_ID = ""
    try:
        url, err = spotify_login_url()
        assert url is None
        assert "Client ID" in err
    finally:
        Config.SPOTIFY_CLIENT_ID = prev


if __name__ == "__main__":
    test_pkce_challenge_estable()
    test_login_sin_client_id()
    print("OK")
