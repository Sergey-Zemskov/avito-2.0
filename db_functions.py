import fdb
import hashlib
import os

DB_PATH = os.path.expanduser("~/avito_db/AVITO.DB")
DB_USER = "sysdba"
DB_PASSWORD = "masterkey"
DB_CHARSET = "UTF8"

def get_connection():
    return fdb.connect(
        host="localhost", database=DB_PATH,
        user=DB_USER, password=DB_PASSWORD, charset=DB_CHARSET
    )

# --- Пользователи ---
def register_user(login, password):
    conn = get_connection()
    cur = conn.cursor()
    try:
        pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        # ID генерируется автоматически (IDENTITY)
        cur.execute("INSERT INTO users (login, password_hash, role) VALUES (?, ?, 'user')", 
                    (login, pwd_hash))
        conn.commit()
        return True
    except fdb.DatabaseError:
        return False # Логин уже существует
    finally:
        cur.close(); conn.close()

def login_user(login, password):
    conn = get_connection()
    cur = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    cur.execute("SELECT id, login FROM users WHERE login = ? AND password_hash = ?", (login, pwd_hash))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, login FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
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
    cur.close(); conn.close()
    return rows

def get_all_categories():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

# --- Карточка ---
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
    cur.close(); conn.close()
    return row

def get_ad_image(ad_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT image FROM ads WHERE id = ?", (ad_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row[0] if row else None

# --- Избранное ---
def add_to_favorites(user_id, ad_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)", (user_id, ad_id))
        conn.commit()
        return True
    except fdb.DatabaseError:
        return False
    finally:
        cur.close(); conn.close()

def remove_from_favorites(user_id, ad_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM favorites WHERE user_id = ? AND ad_id = ?", (user_id, ad_id))
    conn.commit()
    cur.close(); conn.close()

def get_favorites(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.title, a.price, a.city
        FROM favorites f JOIN ads a ON f.ad_id = a.id
        WHERE f.user_id = ? ORDER BY f.id DESC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

# --- Управление объявлениями ---
def create_ad(user_id, category_id, title, description, price, city, image_data=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ads (user_id, category_id, title, description, price, city, image)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, category_id, title, description, price, city, image_data))
    conn.commit()
    cur.close(); conn.close()

def delete_ad(ad_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM ads WHERE id = ?", (ad_id,))
    owner = cur.fetchone()
    if owner and owner[0] == user_id:
        cur.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        conn.commit()
        ok = True
    else:
        ok = False
    cur.close(); conn.close()
    return ok

def get_user_ads(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.title, a.price, a.city, c.name
        FROM ads a JOIN categories c ON a.category_id = c.id
        WHERE a.user_id = ? ORDER BY a.id DESC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

# --- Чат ---
def send_message(sender_id, receiver_id, ad_id, text):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (sender_id, receiver_id, ad_id, message_text)
        VALUES (?, ?, ?, ?)
    """, (sender_id, receiver_id, ad_id, text))
    conn.commit()
    cur.close(); conn.close()

def get_chat_history(user1_id, user2_id, ad_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sender_id, message_text, created_at
        FROM messages
        WHERE ad_id = ? AND ((sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?))
        ORDER BY created_at ASC
    """, (ad_id, user1_id, user2_id, user2_id, user1_id))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def get_messages_list(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.ad_id, 
               CASE WHEN m.sender_id = ? THEN m.receiver_id ELSE m.sender_id END AS other_id,
               MAX(m.created_at) AS last_time
        FROM messages m
        WHERE m.sender_id = ? OR m.receiver_id = ?
        GROUP BY m.ad_id, other_id
        ORDER BY last_time DESC
    """, (user_id, user_id, user_id))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows