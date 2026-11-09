import fdb
import os
import shutil

# Путь, где будет создан файл базы данных (оставляю ваш путь с диска D)
DB_PATH = r"D:\AVITO_DB\AVITO.DB"
DB_DIR = os.path.dirname(DB_PATH)

def create_database():
    # 🔥 АВТОМАТИЧЕСКАЯ ОЧИСТКА: Удаляем старую папку/файл, если они есть
    if os.path.exists(DB_DIR):
        print(f"🗑️ Удаляем старые файлы из {DB_DIR}...")
        shutil.rmtree(DB_DIR) # Удаляем папку целиком
        
    # Создаем папку заново
    os.makedirs(DB_DIR, exist_ok=True)

    try:
        # Подключаемся (файл создастся автоматически, так как мы его только что удалили)
        conn = fdb.create_database(
            database=f"localhost:{DB_PATH}", 
            user="sysdba", 
            password="masterkey", 
            charset="UTF8"
        )
        cursor = conn.cursor()
        print("✅ Файл базы данных успешно создан!")

        print("📝 Создание пустых таблиц для ER-диаграммы...")

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
        print("✅ Все таблицы успешно созданы!")
        print(f"📂 Файл базы данных сохранен по пути: {DB_PATH}")

    except fdb.DatabaseError as e:
        print(f"❌ Ошибка базы данных: {e}")
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
        print("🔒 Соединение закрыто.")

if __name__ == "__main__":
    create_database()