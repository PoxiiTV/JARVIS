@echo off
setlocal
cd /d "%~dp0"

set "DEST=deploy-hosting"

echo ============================================
echo  JARVIS - Preparando carpeta de produccion
echo ============================================
echo.

if not exist ".env" goto error_env

rem --- Limpiar la carpeta anterior ---
if exist "%DEST%" (
    echo Borrando "%DEST%" anterior...
    rmdir /s /q "%DEST%"
)
mkdir "%DEST%"

rem robocopy: /E subcarpetas (incluidas vacias), /XD excluye directorios,
rem /NFL /NDL /NJH /NJS silencian el listado. Codigos < 8 = exito.
echo [1/3] Copiando la aplicacion...
robocopy "app" "%DEST%\app" /E /XD __pycache__ /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto error

echo [2/3] Copiando la memoria de JARVIS...
robocopy "memoria" "%DEST%\memoria" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto error

echo [3/3] Copiando configuracion y arranque...
rem El .env REAL va incluido. Contiene tus claves: no lo subas a git.
robocopy "." "%DEST%" requirements.txt Dockerfile docker-compose.yml entrypoint.sh .dockerignore README.md start.bat .env /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto error

echo.
echo ============================================
echo  Listo. Carpeta generada: %DEST%\
echo ============================================
echo.
echo  NO se han copiado (desarrollo): venv, __pycache__,
echo  tests, .git, .gitignore, .env.example, deploy.bat
echo.
echo  AVISO: "%DEST%\.env" contiene tus claves reales.
echo  No lo subas a git ni lo compartas.
echo.
pause
exit /b 0

:error_env
echo [X] No existe el archivo .env — no se puede preparar el deploy.
echo     Copia .env.example a .env y rellena tus claves.
pause
exit /b 1

:error
echo [X] Fallo copiando archivos (robocopy devolvio %errorlevel%).
pause
exit /b 1
