@echo off
chcp 65001 >nul
title Сайт объявлений "Авито" - курсовая работа
cd /d "%~dp0"

echo ======================================================================
echo   Сайт объявлений "Авито"
echo   Курсовая работа по дисциплине "Базы данных"
echo ======================================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH.
    echo Установите Python 3.9 или новее и повторите запуск.
    pause
    exit /b 1
)

python -c "import flask, fdb" >nul 2>&1
if errorlevel 1 (
    echo Установка необходимых библиотек...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить библиотеки.
        pause
        exit /b 1
    )
)

echo Запуск веб-сервера...
echo После появления строки "Running on http://127.0.0.1:5000"
echo откройте этот адрес в браузере.
echo Для остановки сервера нажмите Ctrl+C.
echo.

python app.py

echo.
echo Сервер остановлен.
pause
