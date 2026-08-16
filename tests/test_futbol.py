"""Barça no dispara APIs de fútbol ni Docker."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import services


def test_barca_no_pide_futbol():
    ctx = services.smart_context("mañana juega el barça")
    assert "football" not in ctx
    assert "docker" not in ctx


if __name__ == "__main__":
    test_barca_no_pide_futbol()
    print("OK")
