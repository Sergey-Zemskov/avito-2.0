# -*- coding: utf-8 -*-
"""
Настройки сайта объявлений "Авито".

Курсовая работа по базам данных.
"""

import os

# --- Подключение к базе данных Firebird ---
DB_HOST = "localhost"
DB_PATH = r"D:\AVITO_DB\AVITO.DB"
DB_USER = "sysdba"
DB_PASSWORD = "masterkey"
DB_CHARSET = "UTF8"

# Сколько соединений с базой держать открытыми
DB_POOL_SIZE = 5

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
