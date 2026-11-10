import fdb
import os
import shutil

# ============================================================
#  НАСТРОЙКА ПУТИ К БАЗЕ
# ============================================================
# Укажите ЯВНО папку, в которой будет лежать файл базы данных.
# Именно этой папке нужно будет выдать права пользователю Firebird.
#
# Пример для Linux (пользователь, под которым работает Firebird, обычно 'firebird'):
#
#   sudo mkdir -p /opt/avito_db
#   sudo chown -R firebird:firebird /opt/avito_db
#   sudo chmod -R 775 /opt/avito_db
#
# Если Firebird запускается под другим пользователем — замените 'firebird'
# на нужного (см. `ps aux | grep firebird` или `systemctl status firebird`).
#
# Пример для Windows — путь вида r"D:\AVITO_DB". Тогда права выдавать не нужно,
# но папка должна быть доступна на запись пользователю, под которым запущен сервис Firebird.
# ------------------------------------------------------------
DB_DIR  = "/opt/avito_db"     # <-- ПАПКА с базой (сюда выдавать права)
DB_NAME = "AVITO.DB"          # <-- ИМЯ файла базы
DB_PATH = os.path.join(DB_DIR, DB_NAME)

HOST     = "localhost"
USER     = "sysdba"
PASSWORD = "masterkey"
# ============================================================


def create_database():
    # Автоматическая очистка: удаляем старую папку с базой, если она есть
    if os.path.exists(DB_DIR):
        print(f"Удаляем старые файлы из {DB_DIR}...")
        shutil.rmtree(DB_DIR)

    # Создаём папку заново
    os.makedirs(DB_DIR, exist_ok=True)
    print(f"Папка для базы готова: {DB_DIR}")

    conn = None
    cursor = None
    try:
        # Подключаемся (файл создастся автоматически)
        conn = fdb.create_database(
            database=f"{HOST}:{DB_PATH}",
            user=USER,
            password=PASSWORD,
            charset="UTF8"
        )
        cursor = conn.cursor()
        print("Файл базы данных успешно создан!")

        print("Создание пустых таблиц для ER-диаграммы...")

        # 1. Пользователи
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                login VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL
            )
        ''')

        # 2. Категории
        cursor.execute('''
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description VARCHAR(1000)
            )
        ''')

        # 3. Объявления
        cursor.execute('''
            CREATE TABLE ads (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                description VARCHAR(2000),
                price NUMERIC(12, 2) NOT NULL,
                city VARCHAR(100) NOT NULL,
                image_url VARCHAR(500),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        ''')

        # 4. Избранное
        cursor.execute('''
            CREATE TABLE favorites (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                ad_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE CASCADE,
                UNIQUE (user_id, ad_id)
            )
        ''')

        # 5. Сообщения (Чат)
        cursor.execute('''
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                ad_id INTEGER,
                message_text VARCHAR(2000) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        print("Все таблицы успешно созданы!")
        print(f"Файл базы данных сохранен по пути: {DB_PATH}")

    except fdb.DatabaseError as e:
        print(f"Ошибка базы данных: {e}")
    except Exception as e:
        print(f"Общая ошибка: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("Соединение закрыто.")


if __name__ == "__main__":
    create_database()