@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title J.A.R.V.I.S.

echo ============================================
echo  J.A.R.V.I.S.
echo ============================================
echo.

if not exist ".env" goto falta_env

rem --- Preparar el entorno (solo la primera vez) ---
if exist "venv\Scripts\python.exe" goto app

echo [1/2] Creando el entorno... solo la primera vez
python -m venv venv
if errorlevel 1 goto error_venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet --no-cache-dir
pip install --no-cache-dir -r requirements.txt
if errorlevel 1 goto error_pip
echo.

:app
rem Cierra el .exe viejo, Electron de este proyecto y el Python del panel.
rem Si no, el puerto 8080 sigue ocupado y se ve la version anterior.
call :cerrar_instancias

rem Hermes vive en el otro PC (Linux). La IP sale de HERMES_URL en .env.
set "HERMES_URL_VAL=http://192.168.1.100:8642/v1"
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if /i "%%a"=="HERMES_URL" if not "%%~b"=="" set "HERMES_URL_VAL=%%b"
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $u=[Uri]$env:HERMES_URL_VAL; $h=$u.Host; $p=if($u.Port -gt 0){$u.Port}else{8642}; if (-not (Test-NetConnection -ComputerName $h -Port $p -WarningAction SilentlyContinue).TcpTestSucceeded) { Write-Output ('Aviso: Hermes no responde en ' + $h + ':' + $p + '. Arranca el gateway en el Linux (misma Wi-Fi).') } } catch { }"

rem Electron con el codigo actual. El .exe compilado se queda atras hasta
rem que vuelvas a pasar por compilar.bat.
if exist "electron\node_modules\electron\dist\electron.exe" goto app_dev

echo [2/2] Arrancando solo el panel web (sin la app de escritorio)...
echo      Para tener la app: compilar.bat
echo.
call venv\Scripts\activate.bat
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    if not "%%~b"=="" set "%%a=%%b"
)
set "JARVIS_KIOSK=1"
echo Abre http://localhost:8080 en el navegador.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
goto fin

:app_dev
echo [2/2] Abriendo J.A.R.V.I.S. ...
cd electron
node_modules\electron\dist\electron.exe .
cd ..
goto fin

:cerrar_instancias
echo Cerrando instancias anteriores...
taskkill /F /T /IM "J.A.R.V.I.S.exe" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ( ($_.Name -eq 'electron.exe' -and $_.CommandLine -like '*jarvismejorao*electron*node_modules*electron*') -or ($_.Name -match 'python' -and $_.CommandLine -like '*uvicorn*' -and $_.CommandLine -like '*app.main:app*') ) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $n = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName; if ($n -match 'python|J.A.R.V.I.S') { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 1 /nobreak >nul
echo.
exit /b 0

:fin
echo.
echo J.A.R.V.I.S. se ha cerrado.
pause
exit /b 0

:falta_env
echo [X] No existe el archivo .env en esta carpeta.
echo     Copia .env.example a .env y pon tus claves.
echo.
echo     Necesitas:
echo       DEEPSEEK_API_KEY  ^(el cerebro^)  -^> openrouter.ai/keys
echo       FISH_API_KEY      ^(la voz^)      -^> fish.audio/app/developers
echo.
pause
exit /b 1

:error_venv
echo [X] No se pudo crear el entorno. Comprueba que Python esta instalado.
pause
exit /b 1

:error_pip
echo [X] Fallo la instalacion de dependencias.
pause
exit /b 1
