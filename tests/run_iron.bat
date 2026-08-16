@echo off
setlocal
cd /d "%~dp0\.."
set PY=venv\Scripts\python.exe
if not exist "%PY%" set PY=python
for %%T in (
  tests\test_cerebro_forzado.py
  tests\test_intencion.py
  tests\test_charla_rapida.py
  tests\test_brain_hermes.py
  tests\test_spotify_orden.py
  tests\test_fish_volumen.py
  tests\test_recibo.py
  tests\test_voice_norm.py
  tests\test_hermes_client.py
  tests\test_mcp_jarvis.py
  tests\test_memoria_auto.py
  tests\test_briefing.py
  tests\test_personalidad.py
  tests\test_local_win.py
  tests\test_primera_frase.py
  tests\test_hud_three.py
) do (
  echo -- %%T
  "%PY%" "%%T"
  if errorlevel 1 exit /b 1
)
echo OK
