
import fdb
import os
import hashlib
import random
from faker import Faker


# ============================================================
# НАСТРОЙКИ БАЗЫ ДАННЫХ
# ============================================================

DB_DIR = "/opt/avito_db"
DB_NAME = "AVITO.DB"
DB_PATH = os.path.join(DB_DIR, DB_NAME)

HOST = "localhost"
USER = "sysdba"
PASSWORD = "masterkey"
CHARSET = "UTF8"

DB_DSN = f"{HOST}:{DB_PATH}"


# ============================================================
# НАСТРОЙКИ ТЕСТОВЫХ ДАННЫХ
# ============================================================

fake = Faker("ru_RU")
Faker.seed(42)
random.seed(42)

NUM_USERS = 20
NUM_ADS = 50
NUM_FAVORITES = 40
NUM_MESSAGES = 80

ROLES = ["user", "user", "user", "moderator", "admin"]

CATEGORIES = [
    ("Электроника", "Телефоны, ноутбуки, планшеты и другая техника"),
    ("Транспорт", "Автомобили, мотоциклы, запчасти"),
    ("Недвижимость", "Квартиры, дома, коммерческая недвижимость"),
    ("Услуги", "Ремонт, обучение, консультации и другие услуги"),
    ("Работа", "Вакансии и резюме"),
    ("Личные вещи", "Одежда, обувь, аксессуары"),
]


# ============================================================
# УДАЛЕНИЕ СТАРОЙ БАЗЫ
# ============================================================

def delete_old_database():
    print("Проверка старой базы данных...")

    connection = None

    try:
        # Пытаемся подключиться к существующей базе
        connection = fdb.connect(
            dsn=DB_DSN,
            user=USER,
            password=PASSWORD,
            charset=CHARSET
        )

        # Удаляем базу средствами Firebird
        connection.drop_database()
        connection = None

        print("Старая база данных успешно удалена.")

    except fdb.DatabaseError as error:
        if connection is not None:
            connection.close()
            connection = None

        # Если файл существует, но подключиться к нему не удалось,
        # не пытаемся создавать базу поверх существующего файла.
        if os.path.exists(DB_PATH):
            raise RuntimeError(
                "Не удалось удалить существующую базу данных.\n"
                "Проверь, что Flask-приложение остановлено и "
                "у пользователя firebird есть доступ к файлу.\n"
                f"Ошибка Firebird: {error}"
            )

        print("Старой базы данных нет. Будет создана новая.")


# ============================================================
# ЗАПОЛНЕНИЕ ТЕСТОВЫМИ ДАННЫМИ
# ============================================================

def fill_test_data(cursor):

    # ---------- USERS ----------

    for _ in range(NUM_USERS):
        login = fake.unique.user_name()

        password_hash = hashlib.sha256(
            fake.password().encode("utf-8")
        ).hexdigest()

        role = random.choice(ROLES)

        cursor.execute(
            """
            INSERT INTO users (login, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (login, password_hash, role)
        )

    cursor.execute("SELECT id FROM users ORDER BY id")
    user_ids = [row[0] for row in cursor.fetchall()]

    # ---------- CATEGORIES ----------

    for name, description in CATEGORIES:
        cursor.execute(
            """
            INSERT INTO categories (name, description)
            VALUES (?, ?)
            """,
            (name, description)
        )

    cursor.execute("SELECT id FROM categories ORDER BY id")
    category_ids = [row[0] for row in cursor.fetchall()]

    # ---------- ADS ----------

    for _ in range(NUM_ADS):
        cursor.execute(
            """
            INSERT INTO ads
                (user_id, category_id, title, description,
                 price, city, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                random.choice(user_ids),
                random.choice(category_ids),
                fake.sentence(nb_words=4).rstrip(".").capitalize(),
                fake.text(max_nb_chars=500),
                round(
                    float(
                        fake.pydecimal(
                            left_digits=6,
                            right_digits=2,
                            positive=True
                        )
                    ),
                    2
                ),
                fake.city_name(),
                None
            )
        )

    cursor.execute("SELECT id FROM ads ORDER BY id")
    ad_ids = [row[0] for row in cursor.fetchall()]

    # ---------- FAVORITES ----------

    pairs = set()

    while len(pairs) < NUM_FAVORITES:
        pair = (
            random.choice(user_ids),
            random.choice(ad_ids)
        )

        if pair in pairs:
            continue

        pairs.add(pair)

        cursor.execute(
            """
            INSERT INTO favorites (user_id, ad_id)
            VALUES (?, ?)
            """,
            pair
        )

    # ---------- MESSAGES ----------

    for _ in range(NUM_MESSAGES):
        sender_id = random.choice(user_ids)
        receiver_id = random.choice(user_ids)

        while receiver_id == sender_id:
            receiver_id = random.choice(user_ids)

        cursor.execute(
            """
            INSERT INTO messages
                (sender_id, receiver_id, ad_id,
                 message_text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                sender_id,
                receiver_id,
                random.choice(ad_ids) if random.random() < 0.7 else None,
                fake.text(max_nb_chars=300),
                fake.date_time_between(
                    start_date="-30d",
                    end_date="now"
                )
            )
        )

    print()
    print("Тестовые данные добавлены:")
    print(f"Пользователей: {len(user_ids)}")
    print(f"Категорий:     {len(category_ids)}")
    print(f"Объявлений:    {len(ad_ids)}")
    print(f"Избранного:    {len(pairs)}")
    print(f"Сообщений:     {NUM_MESSAGES}")


# ============================================================
# СОЗДАНИЕ БАЗЫ ДАННЫХ
# ============================================================

def create_database():

    connection = None
    cursor = None

    try:
        print("====================================")
        print("ПЕРЕСОЗДАНИЕ БАЗЫ AVITO")
        print("====================================")

        # Проверяем наличие папки
        os.makedirs(DB_DIR, exist_ok=True)

        # Удаляем старую базу
        delete_old_database()

        # Создаём новую базу
        print()
        print("Создание новой базы данных...")

        connection = fdb.create_database(
            database=DB_DSN,
            user=USER,
            password=PASSWORD,
            charset=CHARSET
        )

        cursor = connection.cursor()

        print("Файл базы данных создан.")

        # ---------- USERS ----------

        cursor.execute("""
            CREATE TABLE users (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                login VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL
            )
        """)

        # ---------- CATEGORIES ----------

        cursor.execute("""
            CREATE TABLE categories (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description VARCHAR(1000)
            )
        """)

        # ---------- ADS ----------

        cursor.execute("""
            CREATE TABLE ads (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                description VARCHAR(2000),
                price NUMERIC(12, 2) NOT NULL,
                city VARCHAR(100) NOT NULL,
                image_url VARCHAR(500),

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (category_id)
                    REFERENCES categories(id)
                    ON DELETE CASCADE
            )
        """)

        # ---------- FAVORITES ----------

        cursor.execute("""
            CREATE TABLE favorites (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                user_id INTEGER NOT NULL,
                ad_id INTEGER NOT NULL,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (ad_id)
                    REFERENCES ads(id)
                    ON DELETE CASCADE,

                UNIQUE (user_id, ad_id)
            )
        """)

        # ---------- MESSAGES ----------

        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                ad_id INTEGER,
                message_text VARCHAR(2000) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (sender_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (receiver_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (ad_id)
                    REFERENCES ads(id)
                    ON DELETE CASCADE
            )
        """)

        connection.commit()

        print("Все таблицы успешно созданы.")

        # Заполняем базу тестовыми данными
        print()
        print("Заполнение тестовыми данными...")

        fill_test_data(cursor)

        connection.commit()

        print()
        print("====================================")
        print("БАЗА ДАННЫХ УСПЕШНО СОЗДАНА")
        print("====================================")
        print(f"Путь: {DB_PATH}")

    except Exception as error:
        if connection is not None:
            connection.rollback()

        print()
        print("ОШИБКА ПРИ СОЗДАНИИ БАЗЫ:")
        print(error)

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

        print()
        print("Соединение с базой данных закрыто.")


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    create_database()
