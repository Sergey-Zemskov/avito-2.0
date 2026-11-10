import fdb
import hashlib
import os

# Путь к базе данных, которую создают createdatabase.py / createdb2.py
# Можно переопределить переменной окружения AVITO_DB_PATH
DB_PATH = os.getenv("AVITO_DB_PATH", "/opt/avito_db/AVITO.DB")

USER = "sysdba"
PASSWORD = "masterkey"


def get_connection():
    return fdb.connect(
        host="localhost",
        database=DB_PATH,
        user=USER,
        password=PASSWORD,
        charset="UTF8"
    )


# --- Пользователи ---
def register_user(login, password):
    conn = get_connection()
    cur = conn.cursor()
    try:
        pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        cur.execute(
            "INSERT INTO users (login, password_hash, role) VALUES (?, ?, 'user')",
            (login, pwd_hash)
        )
        conn.commit()
        return True
    except fdb.DatabaseError:
        return False
    finally:
        cur.close()
        conn.close()


def login_user(login, password):
    conn = get_connection()
    cur = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    cur.execute(
        "SELECT id, login FROM users WHERE login = ? AND password_hash = ?",
        (login, pwd_hash)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, login FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# --- Каталог ---
def get_catalog(search_query="", category_id=None, city=None, sort_by="date"):
    conn = get_connection()
    cur = conn.cursor()
    sql = """
        SELECT a.id, a.title, a.price, a.city, c.name, u.login
        FROM ads a
        JOIN categories c ON a.category_id = c.id
        JOIN users u ON a.user_id = u.id
        WHERE 1=1
    """
    params = []
    if search_query:
        sql += " AND a.title LIKE ?"
        params.append(f"%{search_query}%")
    if category_id:
        sql += " AND a.category_id = ?"
        params.append(category_id)
    if city:
        sql += " AND a.city = ?"
        params.append(city)
    sql += " ORDER BY a.price ASC" if sort_by == "price" else " ORDER BY a.id DESC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_all_categories():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# --- Объявления ---
def create_ad(user_id, category_id, title, description, price, city, image_data=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ads (user_id, category_id, title, description, price, city, image)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, category_id, title, description, price, city, image_data))
    conn.commit()
    cur.close()
    conn.close()


def get_ad_details(ad_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.title, a.description, a.price, a.city,
               c.name, u.login, a.user_id, a.category_id
        FROM ads a
        JOIN categories c ON a.category_id = c.id
        JOIN users u ON a.user_id = u.id
        WHERE a.id = ?
    """, (ad_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def get_ad_image(ad_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT image FROM ads WHERE id = ?", (ad_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def update_ad(ad_id, user_id, category_id, title, description, price, city, image_data=None):
    conn = get_connection()
    cur = conn.cursor()
    # ... (дальше без изменений)