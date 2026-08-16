"""La LAN de Hermes solo admite IPs de casa, nunca internet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes.lan import es_rfc1918, parsear_ips


def test_rfc1918_casa():
    assert es_rfc1918("192.168.1.45")
    assert es_rfc1918("10.0.0.8")
    assert es_rfc1918("172.16.5.2")


def test_rfc1918_rechaza_internet_y_localhost():
    assert not es_rfc1918("8.8.8.8")
    assert not es_rfc1918("1.1.1.1")
    assert not es_rfc1918("127.0.0.1")
    assert not es_rfc1918("0.0.0.0")
    assert not es_rfc1918("100.64.1.1")


def test_parsear_lista():
    assert parsear_ips("192.168.1.45, 10.0.0.2") == ["192.168.1.45", "10.0.0.2"]


def test_parsear_publica_explota():
    try:
        parsear_ips("8.8.8.8")
    except ValueError:
        return
    raise AssertionError("tenia que rechazar 8.8.8.8")


if __name__ == "__main__":
    test_rfc1918_casa()
    test_rfc1918_rechaza_internet_y_localhost()
    test_parsear_lista()
    test_parsear_publica_explota()
    print("OK")
