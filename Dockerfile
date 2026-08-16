FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Europe/Madrid \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias del sistema (edge-tts necesita libgcc; whisper int8 no necesita GPU)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgcc-s1 curl \
    && rm -rf /var/lib/apt/lists/*

# cloudflared para exponer el dashboard con un túnel con nombre (opcional)
RUN curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -o /usr/local/bin/cloudflared \
    && chmod +x /usr/local/bin/cloudflared

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Usuario no root
RUN useradd -m jarvis && chown -R jarvis:jarvis /app
USER jarvis

EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s --start-period=120s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/ping', timeout=5)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
