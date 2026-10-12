@echo off
rem ---------------------------------------------------------------
rem  Zapusk sajta "Avito".  Prost zakrojte etot fajl.
rem  Vsya podgotovka vypolnyaetsya skriptom start.py
rem ---------------------------------------------------------------
chcp 65001 >nul
title Avito - kursovaya rabota
cd /d "%~dp0"

set "PY=python"
where python >nul 2>&1
if errorlevel 1 set "PY=py -3"

%PY% --version >nul 2>&1
if errorlevel 1 goto nopython

%PY% start.py
pause
exit /b 0

:nopython
echo.
echo  Python 3 not found.
echo  Install it from https://www.python.org/downloads/
echo  and check "Add Python to PATH" during setup.
echo.
pause
exit /b 1
