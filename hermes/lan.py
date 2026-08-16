"""Abre Hermes en la LAN solo a IPs privadas concretas. Nunca a internet.

Uso (como administrador):
  venv\\Scripts\\python.exe hermes\\lan.py 192.168.1.45
  venv\\Scripts\\python.exe hermes\\lan.py --off
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
REGLA_LAN = "JARVIS Hermes 8642 LAN"
REGLA_BLOQUEO = "JARVIS Hermes 8642 no-internet"
PRIVADAS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _leer_env(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _upsert(path: Path, cambios: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    lineas = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pendientes = dict(cambios)
    nuevas = []
    for ln in lineas:
        if "=" in ln and not ln.strip().startswith("#"):
            k = ln.split("=", 1)[0].strip()
            if k in pendientes:
                nuevas.append(f"{k}={pendientes.pop(k)}")
                continue
        nuevas.append(ln)
    if pendientes:
        nuevas.append("")
        nuevas.append("# --- JARVIS LAN ---")
        for k, v in pendientes.items():
            nuevas.append(f"{k}={v}")
    path.write_text("\n".join(nuevas) + "\n", encoding="utf-8")


def es_rfc1918(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    if addr.is_loopback or addr.is_unspecified or addr.is_multicast:
        return False
    return any(addr in red for red in PRIVADAS)


def parsear_ips(texto: str) -> list[str]:
    partes = [p.strip() for p in (texto or "").replace(";", ",").split(",") if p.strip()]
    malas = [p for p in partes if not es_rfc1918(p)]
    if malas:
        raise ValueError(
            "Solo IPs de casa (10.x, 172.16-31.x, 192.168.x). Rechazadas: "
            + ", ".join(malas)
        )
    return list(dict.fromkeys(partes))


def ips_lan_pc() -> list[str]:
    vistas = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if es_rfc1918(ip):
                vistas.append(ip)
    except OSError:
        pass
    return sorted(set(vistas))


def ip_wifi_pc() -> str:
    ips = ips_lan_pc()
    for ip in ips:
        if ip.startswith("192.168.1."):
            return ip
    return ips[0] if ips else ""


def _ps(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _admin() -> bool:
    r = _ps("([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)")
    return (r.stdout or "").strip().lower() == "true"


def _borrar_reglas():
    for nombre in (REGLA_LAN, REGLA_BLOQUEO):
        _ps(f"Remove-NetFirewallRule -DisplayName '{nombre}' -ErrorAction SilentlyContinue")


def aplicar_firewall(ips: list[str]) -> None:
    if not _admin():
        raise PermissionError(
            "El firewall pide administrador. Cierra esto y ejecuta hermes-lan.bat "
            "como administrador."
        )
    _borrar_reglas()
    remotas = ",".join(ips)
    allow = (
        f"New-NetFirewallRule -DisplayName '{REGLA_LAN}' -Direction Inbound "
        f"-Action Allow -Protocol TCP -LocalPort 8642 -Profile Private "
        f"-RemoteAddress {remotas} -ErrorAction Stop"
    )
    block = (
        f"New-NetFirewallRule -DisplayName '{REGLA_BLOQUEO}' -Direction Inbound "
        f"-Action Block -Protocol TCP -LocalPort 8642 -Profile Public "
        f"-ErrorAction Stop"
    )
    for cmd in (allow, block):
        r = _ps(cmd)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout or "fallo firewall").strip())


def aviso_portproxy() -> str:
    r = subprocess.run(
        ["netsh", "interface", "portproxy", "show", "all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    txt = (r.stdout or "") + (r.stderr or "")
    if "8642" in txt:
        return "AVISO: hay un portproxy de Windows al 8642. Quitalo, no es LAN."
    return ""


def activar(ips: list[str]) -> list[str]:
    aplicar_firewall(ips)
    _upsert(HERMES_HOME / ".env", {
        "API_SERVER_HOST": "0.0.0.0",
        "API_SERVER_PORT": "8642",
        "API_SERVER_ENABLED": "true",
    })
    _upsert(REPO / ".env", {"HERMES_LAN_ALLOW": ",".join(ips)})
    return ips_lan_pc()


def desactivar() -> None:
    if _admin():
        _borrar_reglas()
    else:
        print("Sin admin: no pude borrar las reglas del firewall. Hazlo a mano.")
    _upsert(HERMES_HOME / ".env", {"API_SERVER_HOST": "127.0.0.1"})
    _upsert(REPO / ".env", {"HERMES_LAN_ALLOW": ""})


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Hermes solo por LAN, IPs concretas.")
    p.add_argument("ips", nargs="*", help="IP del portatil (192.168.x.x)")
    p.add_argument("--off", action="store_true", help="Volver a solo este PC (127.0.0.1)")
    args = p.parse_args(argv)

    if args.off:
        desactivar()
        print("Hermes otra vez solo en este PC (127.0.0.1).")
        print("Cierra hermes.bat y abrilo de nuevo.")
        return 0

    crudas = args.ips
    if not crudas:
        guardadas = _leer_env(REPO / ".env").get("HERMES_LAN_ALLOW") or "192.168.1.100"
        crudas = [guardadas]

    try:
        ips = parsear_ips(",".join(crudas))
        activar(ips)
    except (ValueError, PermissionError, RuntimeError) as e:
        print("[X]", e)
        return 1

    extra = aviso_portproxy()
    if extra:
        print("[!]", extra)

    destino = ip_wifi_pc() or "192.168.1.100"
    print("Listo. Firewall: 8642 solo desde", ", ".join(ips), "(red privada).")
    print("Internet (perfil publico): bloqueado.")
    print()
    print("En el PORTATIL, el .env de JARVIS:")
    print(f"  HERMES_ENABLED=1")
    print(f"  HERMES_URL=http://{destino}:8642/v1")
    print("  HERMES_KEY=   (la misma que en este PC)")
    print("NO abras hermes.bat ni pongas el token de Telegram en el portatil.")
    print("NO abras el 8642 en el router.")
    print()
    print("En ESTE PC: cierra hermes.bat y abrilo otra vez para que escuche la LAN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
