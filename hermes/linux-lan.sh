#!/usr/bin/env bash
# Hermes vive en ESTE Linux. El panel JARVIS de Windows habla con nosotros.
# Uso: bash hermes/linux-lan.sh <IP_DEL_WINDOWS>
# Solo IPs de casa. No abras el router.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: bash hermes/linux-lan.sh <IP_DEL_WINDOWS>"
  echo "Ejemplo: bash hermes/linux-lan.sh 192.168.1.10"
  exit 1
fi
PC_WIN="$1"
PUERTO=8642
ENV_H="${HERMES_HOME:-$HOME/.hermes}/.env"

if [[ ! "$PC_WIN" =~ ^192\.168\.|^10\.|^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
  echo "[X] Solo IPs de casa. Recibido: $PC_WIN"
  exit 1
fi

mkdir -p "$(dirname "$ENV_H")"
touch "$ENV_H"

poner() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "$ENV_H" 2>/dev/null; then
    sed -i "s|^${k}=.*|${k}=${v}|" "$ENV_H"
  else
    printf '%s=%s\n' "$k" "$v" >> "$ENV_H"
  fi
}

poner API_SERVER_ENABLED true
poner API_SERVER_HOST 0.0.0.0
poner API_SERVER_PORT "$PUERTO"

if ! grep -q '^API_SERVER_KEY=.\+' "$ENV_H"; then
  echo "[!] Pon en $ENV_H la misma HERMES_KEY del .env de JARVIS en Windows:"
  echo "    API_SERVER_KEY=..."
fi

if command -v ufw >/dev/null 2>&1; then
  if ufw status 2>/dev/null | grep -qi inactive; then
    echo "[!] ufw esta apagado. No lo enciendo yo (podria cortarte el SSH)."
    echo "    Cuando lo uses: sudo ufw allow from $PC_WIN to any port $PUERTO proto tcp"
  else
    sudo ufw delete allow "$PUERTO" >/dev/null 2>&1 || true
    sudo ufw allow from "$PC_WIN" to any port "$PUERTO" proto tcp comment 'JARVIS Windows'
    echo "ufw: $PUERTO solo desde $PC_WIN"
  fi
else
  echo "[!] No hay ufw. Añade a mano: iptables/nft solo desde $PC_WIN al $PUERTO"
fi

echo
echo "Luego:"
echo "  1) API_SERVER_KEY = HERMES_KEY de Windows (si no esta)"
echo "  2) systemctl --user restart hermes-gateway"
echo "     (o el comando con el que arranques Hermes aqui)"
echo "  3) En Windows solo start.bat  —  NO hermes.bat"
echo
echo "El panel de Windows usa: http://$(hostname -I | awk '{print $1}'):8642/v1"
