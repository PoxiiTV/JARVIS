#!/usr/bin/env bash
# Panel JARVIS en Linux (opcional). El cerebro Hermes ya es ESTE equipo.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "[X] Falta .env"
  exit 1
fi

if [[ ! -x venv/bin/python ]]; then
  echo "[1/2] Creando el entorno... solo la primera vez"
  python3 -m venv venv
  venv/bin/pip install -U pip
  venv/bin/pip install -r requirements.txt
fi

set -a
# shellcheck disable=SC1091
source .env
set +a
export JARVIS_KIOSK=1

echo "Abre http://127.0.0.1:8080"
echo "Hermes tiene que estar en marcha en esta maquina (:8642)."
exec venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
