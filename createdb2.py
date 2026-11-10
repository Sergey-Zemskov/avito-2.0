import fdb
import os
import shutil
import hashlib
import random
from faker import Faker

# ============================================================
#  НАСТРОЙКА ПУТИ К БАЗЕ
# ============================================================
# Укажите ЯВНО папку, в которой будет лежать файл базы данных.
# Именно этой папке нужно будет выдать права пользователю Firebird.
#
# Пример для Linux:
#
#   sudo mkdir -p /opt/avito_db
#   sudo chown -R firebird:firebird /opt/avito_db
#   sudo chmod -R 775 /opt/avito_db
#
# Пример для Windows — путь вида r"D:\AVITO_DB". Тогда права выдавать не нужно,
# но папка должна быть доступна на запись пользователю сервиса Firebird.

# Создаём каталог (пока от root)
#sudo mkdir -p /opt/avito_db

# Назначаем владельца и группу
#sudo chown firebird:firebird /opt/avito_db

# Права: владелец и группа могут читать/писать/входить.
# Для каталога это стандартная рекомендация для Firebird (770)[reference:1].
#sudo chmod 770 /opt/avito_db

#sudo usermod -aG firebird "$USER"
# ------------------------------------------------------------
DB_DIR  = "/opt/avito_db"     # <-- ПАПКА с базой (сюда выдавать права)
DB_NAME = "AVITO.DB"          # <-- ИМЯ файла базы
DB_PATH = os.path.join(DB_DIR, DB_NAME)

HOST     = "localhost"
USER     = "sysdba"
PASSWORD = "masterkey"
# ============================================================


# ============================================================
#  ГЕНЕРАТОР ТЕСТОВЫХ ДАННЫХ
# ============================================================
# Установка: pip install Faker
# ------------------------------------------------------------
fake = Faker("ru_RU")
Faker.seed(42)     # фиксируем сид, чтобы данные были воспроизводимы
random.seed(42)

NUM_USERS      = 20
NUM_ADS        = 50
NUM_FAVORITES  = 40
NUM_MESSAGES   = 80

ROLES = ["user", "user", "user", "moderator", "admin"]

# Базовые категории (по смыслу Avito), остальные (если нужно больше) добираются из Faker
CATEGORIES = [
    ("Электроника",   "Телефоны, ноутбуки, планшеты и другая техника"),
    ("Транспорт",     "Автомобили, мотоциклы, запчасти"),
    ("Недвижимость",  "Квартиры, дома, коммерческая недвижимость"),
    ("Услуги",        "Ремонт, обучение, консультации и другие услуги"),
    ("Работа",        "Вакансии и резюме"),
    ("Личные вещи",   "Одежда, обувь, аксессуары"),
]


def fill_test_data(cursor):
    """Заполняет все таблицы случайными данными через Faker."""

    # ---------- users ----------
    user_ids = []
    for uid in range(1, NUM_USERS + 1):
        login         = fake.unique.user_name()
        password_hash = hashlib.sha256(fake.password().encode("utf-8")).hexdigest()
        role          = random.choice(ROLES)
        cursor.execute(
            "INSERT INTO users (id, login, password_hash, role) VALUES (?, ?, ?, ?)",
            (uid, login, password_hash, role),
        )
        user_ids.append(uid)

    # ---------- categories ----------
    category_ids = []
    for cid in range(1, len(CATEGORIES) + 1):
        name, description = CATEGORIES[cid - 1]
        cursor.execute(
            "INSERT INTO categories (id, name, description) VALUES (?, ?, ?)",
            (cid, name, description),
        )
        category_ids.append(cid)

    # ---------- ads ----------
    ad_ids = []
    for aid in range(1, NUM_ADS + 1):
        title       = fake.sentence(nb_words=4).rstrip(".").capitalize()
        description = fake.text(max_nb_chars=500)
        price       = round(
            float(fake.pydecimal(left_digits=6, right_digits=2, positive=True)), 2
        )
        city        = fake.city_name()
        image_url   = fake.image_url()
        cursor.execute(
            """INSERT INTO ads
               (id, user_id, category_id, title, description, price, city, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                aid,
                random.choice(user_ids),
                random.choice(category_ids),
                title,
                description,
                price,
                city,
                image_url,
            ),
        )
        ad_ids.append(aid)

    # ---------- favorites ----------
    pairs = set()
    fid   = 1
    attempts = 0
    max_attempts = NUM_FAVORITES * 20
    while len(pairs) < NUM_FAVORITES and attempts < max_attempts:
        attempts += 1
        pair = (random.choice(user_ids), random.choice(ad_ids))
        if pair in pairs:
            continue
        pairs.add(pair)
        cursor.execute(
            "INSERT INTO favorites (id, user_id, ad_id) VALUES (?, ?, ?)",
            (fid, pair[0], pair[1]),
        )
        fid += 1

    # ---------- messages ----------
    for mid in range(1, NUM_MESSAGES + 1):
        sender_id   = random.choice(user_ids)
        receiver_id = random.choice(user_ids)
        while receiver_id == sender_id and len(user_ids) > 1:
            receiver_id = random.choice(user_ids)
        ad_id      = random.choice(ad_ids) if random.random() < 0.7 else None
        text       = fake.text(max_nb_chars=300)
        created_at = fake.date_time_between(start_date="-30d", end_date="now")
        cursor.execute(
            """INSERT INTO messages
               (id, sender_id, receiver_id, ad_id, message_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mid, sender_id, receiver_id, ad_id, text, created_at),
        )

    print(f"Пользователей: {len(user_ids)}")
    print(f"Категорий:     {len(category_ids)}")
    print(f"Объявлений:    {len(ad_ids)}")
    print(f"Избранного:    {len(pairs)}")
    print(f"Сообщений:     {NUM_MESSAGES}")


# ============================================================
#  СОЗДАНИЕ БАЗЫ
# ============================================================
def create_database():
    # Автоматическая очистка: удаляем старую папку с базой, если она есть
    if os.path.exists(DB_DIR):
        print(f"Удаляем старые файлы из {DB_DIR}...")
        shutil.rmtree(DB_DIR)

    # Создаём папку заново
    os.makedirs(DB_DIR, exist_ok=True)
    print(f"Папка для базы готова: {DB_DIR}")

    conn   = None
    cursor = None
    try:
        # Подключаемся (файл создастся автоматически)
        conn = fdb.create_database(
            database=f"{HOST}:{DB_PATH}",
            user=USER,
            password=PASSWORD,
            charset="UTF8",
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

        # ----- ЗАПОЛНЕНИЕ ТЕСТОВЫМИ ДАННЫМИ -----
        print("Заполнение базы тестовыми данными через Faker...")
        fill_test_data(cursor)
        conn.commit()

        print(f"Файл базы данных сохранен по пути: {DB_PATH}")

    except fdb.DatabaseError as e:
        if conn:
            conn.rollback()
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