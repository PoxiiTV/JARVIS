#!/bin/bash
# Entrypoint del dashboard JARVIS (contenedor propio).
# - Carga secretos desde /data/hermes.env (el .env de Hermes, montado RO)
# - Si existe JARVIS_TUNNEL_ID y credenciales de Cloudflare, arranca el túnel nombrado
# - Lanza uvicorn en primer plano
set -e

if [ -f /data/hermes.env ]; then
    set -a
    . /data/hermes.env
    set +a
fi

# Túnel Cloudflare con nombre (opcional):
#  A) Token del panel Zero Trust (recomendado): JARVIS_TUNNEL_TOKEN
#  B) ID + config.yml (cloudflared tunnel create): JARVIS_TUNNEL_ID
if [ -n "$JARVIS_TUNNEL_TOKEN" ]; then
    echo "[entrypoint] Arrancando túnel Cloudflare (token)..."
    cloudflared tunnel run --token "$JARVIS_TUNNEL_TOKEN" &
elif [ -n "$JARVIS_TUNNEL_ID" ] && [ -f "/home/jarvis/.cloudflared/config.yml" ]; then
    echo "[entrypoint] Arrancando túnel Cloudflare: $JARVIS_TUNNEL_ID"
    cloudflared tunnel --config /home/jarvis/.cloudflared/config.yml run "$JARVIS_TUNNEL_ID" --no-autoupdate &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8080
