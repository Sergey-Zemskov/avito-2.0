# -*- coding: utf-8 -*-
"""
Настройки сайта объявлений "Авито".

Курсовая работа по базам данных.
Путь к базе данных определяется автоматически: отдельно для Windows,
отдельно для Linux. При необходимости его можно задать переменной
окружения AVITO_DB_PATH.
"""

import os
import sys

# --- Подключение к базе данных Firebird ---
DB_HOST = "localhost"
DB_USER = "sysdba"
DB_PASSWORD = "masterkey"
DB_CHARSET = "UTF8"

# Сколько соединений с базой держать открытыми
DB_POOL_SIZE = 5


def _default_db_path():
    """Куда положить файл базы данных на этой системе."""
    if os.name == "nt":
        # Windows: сначала пробуем диск D, если его нет - диск C
        for disk in ("D:", "C:"):
            if os.path.isdir(disk + "\\"):
                return disk + "\\AVITO_DB\\AVITO.DB"
        return "C:\\AVITO_DB\\AVITO.DB"

    # Linux (РЕД ОС, CentOS, Fedora, Debian):
    # файл должен лежать в папке, куда может писать служба Firebird
    for folder in ("/var/lib/firebird/3.0/data",
                   "/var/lib/firebird/data",
                   "/var/lib/reddatabase/data",
                   "/var/lib/firebird"):
        if os.path.isdir(folder):
            return os.path.join(folder, "avito.fdb")
    return "/var/lib/firebird/data/avito.fdb"


DB_PATH = os.environ.get("AVITO_DB_PATH") or _default_db_path()

# --- Веб-сервер ---
# Секретный ключ нужен Flask для работы сессии (кто вошёл на сайт)
SECRET_KEY = "avito-kursovaya-2026"

WEB_HOST = "127.0.0.1"
WEB_PORT = 5000
DEBUG = True

# --- Папки ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")

# Самый большой размер загружаемой фотографии - 8 МБ
MAX_CONTENT_LENGTH = 8 * 1024 * 1024

# Какие расширения фотографий разрешены
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")


def make_upload_dir():
    """Создаёт папку для фотографий, если её ещё нет."""
    if not os.path.isdir(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)


def firebird_help():
    """Что написать пользователю, если база данных недоступна."""
    if os.name == "nt":
        return (
            "Похоже, не запущена служба Firebird или RedDatabase.\n"
            "  Откройте «Службы» (Win+R -> services.msc) и запустите\n"
            "  «RedDatabase Server - DefaultInstance» или «Firebird Server».\n"
            "  Либо выполните в командной строке от администратора:\n"
            "      net start RedDatabaseServerDefaultInstance\n"
            "      net start FirebirdServerDefaultInstance"
        )
    return (
        "Похоже, на компьютере не установлен или не запущен сервер Firebird.\n"
        "  Установка (РЕД ОС, CentOS, Fedora):\n"
        "      sudo dnf install -y firebird firebird-utils\n"
        "  Если такого пакета нет, попробуйте:\n"
        "      sudo dnf install -y firebird-superserver\n"
        "  Запуск службы:\n"
        "      sudo systemctl enable --now firebird\n"
        "  Проверить, что сервер работает:\n"
        "      systemctl status firebird"
    )


# Чтобы русские сообщения скриптов правильно выводились в консоль
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
