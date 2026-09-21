@echo off
setlocal

title WE Automation Suite - Enterprise Web

cd /d "%~dp0"

echo [..] Checking for application updates...
python updater.py

if errorlevel 1 (
    echo [WARN] Updater returned an error.
    echo Continuing with current application...
)

echo [OK] Update check completed.

set "HOST=127.0.0.1"
set "PORT=8010"
set "URL=http://%HOST%:%PORT%/"

echo.
echo ================================================================
echo   WE Automation Suite - Enterprise Web
echo ================================================================
echo   Project: %CD%
echo   URL:     %URL%
echo.

set "PY="

py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"

if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo [ERROR] Python was not found.
    pause
    exit /b 1
)

echo [OK] Python: %PY%

echo [..] Checking backend dependencies...

%PY% -c "import fastapi,uvicorn,requests" >nul 2>&1

if errorlevel 1 (
    echo [..] Installing missing backend packages...
    %PY% -m pip install fastapi "uvicorn[standard]" requests python-multipart

    if errorlevel 1 (
        echo [ERROR] Could not install backend dependencies.
        pause
        exit /b 1
    )
)

echo [OK] Backend dependencies satisfied.

echo [..] Checking port %PORT%...

%PY% -c "import socket,sys;s=socket.socket();s.settimeout(.5);sys.exit(0 if s.connect_ex(('%HOST%',%PORT%))==0 else 1)" >nul 2>&1

if not errorlevel 1 (
    echo [ERROR] Port %PORT% is already in use.
    pause
    exit /b 1
)

echo [..] Starting Enterprise Web backend...

start "WE ECRM Professional Web Server" /min "%ComSpec%" /c "%PY% -m uvicorn webapp.server:app --host %HOST% --port %PORT% > webapp\professional_server.log 2>&1"

set /a TRIES=0

:wait

set /a TRIES+=1

%PY% -c "import socket,sys;s=socket.socket();s.settimeout(1);sys.exit(0 if s.connect_ex(('%HOST%',%PORT%))==0 else 1)" >nul 2>&1

if not errorlevel 1 goto ready

if %TRIES% GEQ 25 goto fail

%PY% -c "import time;time.sleep(1)" >nul 2>&1

goto wait

:ready

echo [OK] Professional Web server is ready.

echo [..] Opening %URL%

start "" "%URL%"

echo.

echo ================================================================
echo   Enterprise UI is running on PORT %PORT%
echo ================================================================

pause

exit /b 0

:fail

echo [ERROR] Server did not start.

echo Check: webapp\professional_server.log

pause

exit /b 1