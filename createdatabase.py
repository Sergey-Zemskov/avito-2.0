import fdb
import os
import ctypes.util

# ---------- Настройки подключения ----------
HOST = "localhost"
USER = "sysdba"
PASSWORD = "masterkey"          # при необходимости замените
CHARSET = "UTF8"

# Имя файла БД
DB_FILENAME = "AVITO.DB"

# Возможные места для файла БД (скрипт выберет первое доступное для записи)
DB_DIRS = [
    os.path.expanduser("~/avito_db"),               # домашняя папка
    "/var/lib/reddatabase",                         # типичное место для РЕД БД
    "/var/lib/firebird/3.0/data",                    # типичное место для Firebird
    "/tmp",                                          # запасной вариант
]


def find_client_library():
    """Ищет клиентскую библиотеку РЕД БД / Firebird в стандартных местах."""
    # 1. Пробуем через ctypes (системный поиск)
    for name in ("fbclient", "fclient", "gds"):
        path = ctypes.util.find_library(name)
        if path:
            return path

    # 2. Явно проверяем стандартные пути РЕД ОС
    candidates = [
        "/opt/RedDatabase/lib/libfbclient.so",
        "/opt/RedDatabase/lib/libfclient.so",
        "/opt/RedDatabase/lib/libfbclient.so.2",
        "/usr/lib/libfbclient.so",
        "/usr/lib64/libfbclient.so",
        "/usr/lib/x86_64-linux-gnu/libfbclient.so",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    return None


def pick_db_dir():
    """Выбирает первую папку, в которую можно писать."""
    for d in DB_DIRS:
        try:
            os.makedirs(d, exist_ok=True)
            # Проверяем, что можем создать файл
            test_file = os.path.join(d, ".write_test")
            with open(test_file, "w") as f:
                f.write("")
            os.remove(test_file)
            return d
        except OSError:
            continue
    raise RuntimeError(
        "Не найдено папки, доступной для записи. "
        "Создайте вручную, например: mkdir -p ~/avito_db"
    )


def create_database():
    # 1. Ищем клиентскую библиотеку
    lib_path = find_client_library()
    if not lib_path:
        print("ВНИМАНИЕ: не удалось автоматически найти libfbclient.so.")
        print("Укажите путь вручную в переменной LIB_PATH или установите клиент РЕД БД.")
        lib_path = input("Введите полный путь к libfbclient.so (или Enter, чтобы продолжить без указания): ").strip()
        if not lib_path:
            lib_path = None

    if lib_path:
        print("Используется клиентская библиотека: " + lib_path)
        fdb.load_api(lib_path)   # явно загружаем библиотеку

    # 2. Выбираем папку для БД
    db_dir = pick_db_dir()
    db_path = os.path.join(db_dir, DB_FILENAME)
    print("Файл БД будет создан: " + db_path)

    # 3. Если файл уже есть — удаляем
    if os.path.exists(db_path):
        os.remove(db_path)

    # 4. Создаём базу
    conn = fdb.create_database(
        dsn=HOST + ":" + db_path,
        user=USER,
        password=PASSWORD,
        charset=CHARSET
    )
    cur = conn.cursor()
    print("База данных создана.")

    # ---------- Таблицы ----------
    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            login VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description VARCHAR(1000)
        )
    """)

    cur.execute("""
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
    """)

    cur.execute("""
        CREATE TABLE favorites (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            ad_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE CASCADE,
            UNIQUE (user_id, ad_id)
        )
    """)

    cur.execute("""
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
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Все таблицы созданы.")
    print("Путь к базе: " + db_path)


if __name__ == "__main__":
    create_database()