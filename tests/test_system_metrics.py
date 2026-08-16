"""Las metricas del sistema tienen que funcionar en Windows y en Linux."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import system_metrics


def test_metricas():
    m = system_metrics()
    assert "error" not in m, f"devolvio error: {m.get('error')}"
    for clave in ("cpu", "mem", "disk"):
        assert clave in m, f"falta {clave}"
        assert 0 <= m[clave] <= 100, f"{clave} fuera de rango: {m[clave]}"
    # El panel pinta ram_pct / disk_pct y los GB usados: hay que conservarlos.
    for clave in ("ram_pct", "disk_pct"):
        assert clave in m, f"falta {clave}"
        assert 0 <= m[clave] <= 100, f"{clave} fuera de rango: {m[clave]}"
    assert m["uptime"], "uptime vacio"
    assert "ram_used_gb" in m and "ram_total_gb" in m
    assert "disk_used_gb" in m and "disk_total_gb" in m


if __name__ == "__main__":
    test_metricas()
    print("OK")
