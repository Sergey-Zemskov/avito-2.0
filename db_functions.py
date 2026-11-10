import fdb
import os
import hashlib

# ============================================================
#  ПУТЬ К БАЗЕ (тот же, что в create_database.py)
# ============================================================
DB_PATH = "/opt/avito_db/AVITO.DB"

HOST     = "localhost"
USER     = "sysdba"
PASSWORD = "masterkey"
CHARSET  = "UTF8"


def get_connection():
    return fdb.connect(
        dsn=f"{HOST}:{DB_PATH}",
        user=USER,
        password=PASSWORD,
        charset=CHARSET,
    )


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ============================================================
#  ПОЛЬЗОВАТЕЛИ
# ============================================================
def register_user(login: str, password: str):
    if not login or not password:
        return None
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (login, password_hash, role) "
            "VALUES (?, ?, 'user') RETURNING id",
            (login, _hash(password)),
        )
        row = cur.fetchone()
        new_id = row[0] if row else None
        conn.commit()
        return new_id
    except fdb.DatabaseError as e:
        conn.rollback()
        print(f"register_user: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def login_user(login: str, password: str):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, login, role FROM users "
            "WHERE login = ? AND password_hash = ?",
            (login, _hash(password)),
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def get_user_by_id(user_id):
    if not user_id:
        return None
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, login, role FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


# ============================================================
#  КАТЕГОРИИ / ГОРОДА
# ============================================================
def get_all_categories():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def get_all_cities():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT city FROM ads ORDER BY city")
        return [r[0] for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


# ============================================================
#  ОБЪЯВЛЕНИЯ
# ============================================================
def get_catalog(search_query="", category_id=None, city="",
                sort_by="date", limit=200):
    conn = get_connection()
    cur = conn.cursor()
    try:
        sql = """
            SELECT a.id, a.title, a.price, a.city, a.image_url,
                   c.name AS category, u.login AS seller
            FROM ads a
            JOIN categories c ON a.category_id = c.id
            JOIN users u      ON a.user_id     = u.id
            WHERE 1=1
        """
        params = []
        if search_query:
            sql += " AND (LOWER(a.title) LIKE ? OR LOWER(a.description) LIKE ?)"
            like = f"%{search_query.lower()}%"
            params += [like, like]
        if category_id:
            sql += " AND a.category_id = ?"
            params.append(int(category_id))
        if city:
            sql += " AND a.city = ?"
            params.append(city)

        if sort_by == "price_asc":
            sql += " ORDER BY a.price ASC"
        elif sort_by == "price_desc":
            sql += " ORDER BY a.price DESC"
        else:
            sql += " ORDER BY a.id DESC"

        if limit:
            sql += " ROWS ?"
            params.append(int(limit))

        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def get_ad_details(ad_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT a.id, a.title, a.description, a.price, a.city, a.image_url,
                   c.id, c.name, u.id, u.login
            FROM ads a
            JOIN categories c ON a.category_id = c.id
            JOIN users u      ON a.user_id     = u.id
            WHERE a.id = ?
        """, (ad_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def create_ad(user_id, category_id, title, description, price, city,
              image_url=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO ads
               (user_id, category_id, title, description, price, city, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (user_id, category_id, title, description, price, city, image_url),
        )
        row = cur.fetchone()
        new_id = row[0] if row else None
        conn.commit()
        return new_id
    except fdb.DatabaseError as e:
        conn.rollback()
        print(f"create_ad: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def update_ad(ad_id, user_id, category_id, title, description, price, city,
              image_url=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE ads SET category_id=?, title=?, description=?,
                              price=?, city=?, image_url=?
               WHERE id=? AND user_id=?""",
            (category_id, title, description, price, city, image_url,
             ad_id, user_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok
    except fdb.DatabaseError as e:
        conn.rollback()
        print(f"update_ad: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def delete_ad(ad_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM ads WHERE id=? AND user_id=?",
                    (ad_id, user_id))
        ok = cur.rowcount > 0
        conn.commit()
        return ok
    finally:
        cur.close()
        conn.close()


def get_user_ads(user_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT a.id, a.title, a.price, a.city, c.name
            FROM ads a JOIN categories c ON a.category_id = c.id
            WHERE a.user_id = ?
            ORDER BY a.id DESC
        """, (user_id,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


# ============================================================
#  ИЗБРАННОЕ
# ============================================================
def add_favorite(user_id, ad_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)",
                    (user_id, ad_id))
        conn.commit()
        return True
    except fdb.DatabaseError:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def remove_favorite(user_id, ad_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM favorites WHERE user_id=? AND ad_id=?",
                    (user_id, ad_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        cur.close()
        conn.close()


def is_favorite(user_id, ad_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM favorites WHERE user_id=? AND ad_id=?",
                    (user_id, ad_id))
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def get_user_favorites(user_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT a.id, a.title, a.price, a.city, a.image_url, c.name
            FROM favorites f
            JOIN ads a        ON f.ad_id = a.id
            JOIN categories c ON a.category_id = c.id
            WHERE f.user_id = ?
            ORDER BY f.id DESC
        """, (user_id,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


# ============================================================
#  СООБЩЕНИЯ
# ============================================================
def send_message(sender_id, receiver_id, ad_id, text):
    if sender_id == receiver_id:
        return False
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO messages
               (sender_id, receiver_id, ad_id, message_text)
               VALUES (?, ?, ?, ?)""",
            (sender_id, receiver_id, ad_id, text),
        )
        conn.commit()
        return True
    except fdb.DatabaseError as e:
        conn.rollback()
        print(f"send_message: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_dialog(user_id, other_id, ad_id=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        sql = """
            SELECT m.id, m.sender_id, m.receiver_id, m.ad_id,
                   m.message_text, m.created_at, u.login
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE ((m.sender_id=? AND m.receiver_id=?)
                OR (m.sender_id=? AND m.receiver_id=?))
        """
        params = [user_id, other_id, other_id, user_id]
        if ad_id is not None:
            sql += " AND m.ad_id=?"
            params.append(ad_id)
        sql += " ORDER BY m.created_at ASC"
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def get_conversations(user_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT u.id, u.login, MAX(m.created_at)
            FROM messages m
            JOIN users u
              ON u.id = CASE WHEN m.sender_id=?
                             THEN m.receiver_id ELSE m.sender_id END
            WHERE m.sender_id=? OR m.receiver_id=?
            GROUP BY u.id, u.login
            ORDER BY 3 DESC
        """, (user_id, user_id, user_id))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()