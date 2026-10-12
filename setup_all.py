# -*- coding: utf-8 -*-
"""
Создание и подготовка базы данных «Авито» (курсовая работа).

Что делает скрипт:
  1) проверяет, существует ли файл базы данных;
  2) если файла нет — создаёт его и пять базовых таблиц;
  3) применяет расширенную схему из schema.py: последовательности,
     триггеры автонумерации, индексы, ограничения целостности,
     представления и хранимые процедуры;
  4) по ключу --demo наполняет базу демонстрационными данными (seed.py).

Запуск:
    python setup_all.py            создать базу (если её нет) и обновить схему
    python setup_all.py --demo     то же самое плюс демонстрационные данные
    python setup_all.py --reset    удалить базу и создать её заново (данные пропадут)
"""

import os
import sys

import fdb

import config
import db
import schema

# Базовые таблицы предметной области (описаны в пояснительной записке)
BASE_TABLES = [
    ("users", """
        CREATE TABLE users (
            id            INTEGER PRIMARY KEY,
            login         VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role          VARCHAR(20) NOT NULL
        )"""),
    ("categories", """
        CREATE TABLE categories (
            id          INTEGER PRIMARY KEY,
            name        VARCHAR(100) UNIQUE NOT NULL,
            description VARCHAR(1000)
        )"""),
    ("ads", """
        CREATE TABLE ads (
            id          INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            title       VARCHAR(255) NOT NULL,
            description VARCHAR(2000),
            price       NUMERIC(12, 2) NOT NULL,
            city        VARCHAR(100) NOT NULL,
            image_url   VARCHAR(500),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
        )"""),
    ("favorites", """
        CREATE TABLE favorites (
            id      INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            ad_id   INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (ad_id) REFERENCES ads (id) ON DELETE CASCADE,
            UNIQUE (user_id, ad_id)
        )"""),
    ("messages", """
        CREATE TABLE messages (
            id           INTEGER PRIMARY KEY,
            sender_id    INTEGER NOT NULL,
            receiver_id  INTEGER NOT NULL,
            ad_id        INTEGER,
            message_text VARCHAR(2000) NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (ad_id) REFERENCES ads (id) ON DELETE CASCADE
        )"""),
]


def database_exists():
    """Проверяет, отвечает ли сервер базы данных по указанному пути."""
    try:
        connection = fdb.connect(
            host=config.DB_HOST, database=config.DB_PATH,
            user=config.DB_USER, password=config.DB_PASSWORD,
            charset=config.DB_CHARSET)
        connection.close()
        return True
    except Exception:
        return False


def remove_database():
    """Удаляет файл базы данных (используется только с ключом --reset)."""
    if not os.path.isfile(config.DB_PATH):
        return
    try:
        os.remove(config.DB_PATH)
        print("  старый файл базы удалён")
    except OSError:
        print("  не удалось удалить файл базы: %s" % config.DB_PATH)
        if os.name != "nt":
            print("  попробуйте так:  sudo rm -f %s" % config.DB_PATH)


def create_database():
    """Создаёт файл базы данных и базовые таблицы."""
    folder = os.path.dirname(config.DB_PATH)
    if folder and not os.path.isdir(folder) and os.name == "nt":
        os.makedirs(folder, exist_ok=True)
        print("  создана папка %s" % folder)

    connection = fdb.create_database(
        database="%s:%s" % (config.DB_HOST, config.DB_PATH),
        user=config.DB_USER, password=config.DB_PASSWORD,
        charset=config.DB_CHARSET)
    cursor = connection.cursor()
    try:
        for name, statement in BASE_TABLES:
            cursor.execute(statement)
            print("  + таблица %s" % name)
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    print("  файл базы данных создан: %s" % config.DB_PATH)


def main():
    reset = "--reset" in sys.argv
    demo = "--demo" in sys.argv

    print("=" * 70)
    print("  Подготовка базы данных «Авито»")
    print("  Сервер : %s" % config.DB_HOST)
    print("  База   : %s" % config.DB_PATH)
    print("=" * 70)

    if reset:
        answer = input("Ключ --reset удалит базу данных со всеми записями. "
                       "Продолжить? (y/N): ")
        if answer.strip().lower() not in ("y", "yes", "д", "да"):
            print("Отменено.")
            return 1
        print("Удаление существующей базы...")
        remove_database()

    if database_exists():
        print("База данных уже есть — структура будет только дополнена.")
    else:
        print("Создание базы данных...")
        try:
            create_database()
        except Exception as exc:
            print()
            print("НЕ УДАЛОСЬ СОЗДАТЬ БАЗУ ДАННЫХ")
            print("Причина: %s" % exc)
            print()
            print(config.firebird_help())
            return 1

    print()
    try:
        schema.upgrade()
    except db.DatabaseError as exc:
        print("Ошибка при обновлении структуры: %s" % exc)
        return 1

    if demo:
        print()
        print("Наполнение демонстрационными данными...")
        import seed
        seed.main()

    print()
    print("=" * 70)
    print("  Готово. Теперь можно запускать сайт:  python app.py")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
