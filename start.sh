#!/bin/bash
# ---------------------------------------------------------------
#  Запуск сайта "Авито". Просто выполните:  ./start.sh
#  Вся подготовка выполняется скриптом start.py
# ---------------------------------------------------------------

cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1; then
    PY="python"
else
    echo "Python не найден. Установите его командой:"
    echo "    sudo dnf install -y python3 python3-pip"
    exit 1
fi

"$PY" start.py
