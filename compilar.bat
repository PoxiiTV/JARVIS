@echo off
setlocal
cd /d "%~dp0"
title J.A.R.V.I.S. - Compilar

echo ============================================
echo  J.A.R.V.I.S. - Generar los .exe
echo ============================================
echo.
echo  Genera en dist-electron\:
echo    JARVIS-Setup-1.0.0.exe      instalador
echo    JARVIS-Portable-1.0.0.exe   sin instalar
echo.
echo  Los .exe salen SIN claves: cada uno pone
echo  las suyas desde Ajustes ^> Claves y servicios.
echo.

where node >nul 2>&1
if errorlevel 1 goto sin_node

cd electron

if exist "node_modules\electron\dist\electron.exe" goto compilar
echo [1/2] Instalando dependencias de Electron... solo la primera vez
call npm install --no-audit --no-fund
call npm approve-scripts electron 2>nul
call npm rebuild electron
echo.

:compilar
if not exist "build\icon.ico" (
    echo Falta el icono. Generandolo...
    ..\venv\Scripts\python.exe build\make_icon.py
)

echo [2/2] Compilando... tarda unos minutos
call npx electron-builder --win portable nsis
if errorlevel 1 goto error

cd ..
echo.
echo ============================================
echo  Listo. Los .exe estan en dist-electron\
echo ============================================
echo.
dir /b dist-electron\*.exe
echo.
pause
exit /b 0

:sin_node
echo [X] Falta Node.js. Instalalo desde https://nodejs.org
echo.
pause
exit /b 1

:error
cd ..
echo [X] Fallo la compilacion.
pause
exit /b 1
