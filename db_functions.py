import fdb
import hashlib


# Настройки подключения к Firebird
DB_PATH = "/opt/avito_db/AVITO.DB"
HOST = "localhost"
USER = "sysdba"
PASSWORD = "masterkey"
CHARSET = "UTF8"


def get_connection():
    return fdb.connect(
        dsn=f"{HOST}:{DB_PATH}",
        user=USER,
        password=PASSWORD,
        charset=CHARSET
    )


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(login, password):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (login, password_hash, role) VALUES (?, ?, ?) RETURNING id",
            (login, hash_password(password), "user")
        )
        user_id = cursor.fetchone()[0]
        connection.commit()
        return user_id
    except fdb.DatabaseError:
        connection.rollback()
        return None
    finally:
        cursor.close()
        connection.close()


def login_user(login, password):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT id, login, role FROM users WHERE login = ? AND password_hash = ?",
            (login, hash_password(password))
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def get_user_by_id(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT id, login, role FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def get_all_categories():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT id, name, description FROM categories ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_all_cities():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT DISTINCT city FROM ads WHERE city IS NOT NULL ORDER BY city")
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def get_catalog(search_query="", category_id=None, city="", sort_by="date"):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        sql = """
            SELECT ads.id, ads.title, ads.price, ads.city,
                   CASE WHEN ads.image IS NULL THEN 0 ELSE 1 END,
                   categories.name, users.login
            FROM ads
            JOIN categories ON ads.category_id = categories.id
            JOIN users ON ads.user_id = users.id
            WHERE 1 = 1
        """
        params = []
        if search_query:
            sql += " AND (LOWER(ads.title) LIKE ? OR LOWER(ads.description) LIKE ?)"
            search = "%" + search_query.lower() + "%"
            params.extend([search, search])
        if category_id:
            sql += " AND ads.category_id = ?"
            params.append(category_id)
        if city:
            sql += " AND ads.city = ?"
            params.append(city)
        if sort_by == "price_asc":
            sql += " ORDER BY ads.price ASC"
        elif sort_by == "price_desc":
            sql += " ORDER BY ads.price DESC"
        else:
            sql += " ORDER BY ads.id DESC"
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_ad_details(ad_id):
    """Порядок полей сохранён для совместимости с HTML-шаблонами."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT ads.id, ads.title, ads.description, ads.price, ads.city,
                   CASE WHEN ads.image IS NULL THEN 0 ELSE 1 END,
                   ads.category_id, categories.name, ads.user_id, users.login
            FROM ads
            JOIN categories ON ads.category_id = categories.id
            JOIN users ON ads.user_id = users.id
            WHERE ads.id = ?
            """,
            (ad_id,)
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def get_ad_image(ad_id):
    """Читает BLOB до закрытия соединения и возвращает (байты, MIME-тип)."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT image, image_type FROM ads WHERE id = ?", (ad_id,))
        row = cursor.fetchone()
        if not row or row[0] is None:
            return None, None
        blob = row[0]
        image_data = blob.read() if hasattr(blob, "read") else bytes(blob)
        return image_data, row[1] or "application/octet-stream"
    finally:
        cursor.close()
        connection.close()


def create_ad(user_id, category_id, title, description, price, city,
              image_data=None, image_type=None):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO ads (user_id, category_id, title, description, price, city, image, image_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, category_id, title, description, price, city, image_data, image_type)
        )
        connection.commit()
        return True
    except fdb.DatabaseError as error:
        connection.rollback()
        print("Ошибка создания объявления в Firebird:", error)
        return False
    finally:
        cursor.close()
        connection.close()


def update_ad(ad_id, user_id, category_id, title, description, price, city,
              image_data=None, image_type=None, replace_image=False):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if replace_image:
            cursor.execute(
                """
                UPDATE ads SET category_id = ?, title = ?, description = ?, price = ?,
                    city = ?, image = ?, image_type = ?
                WHERE id = ? AND user_id = ?
                """,
                (category_id, title, description, price, city, image_data,
                 image_type, ad_id, user_id)
            )
        else:
            cursor.execute(
                """
                UPDATE ads SET category_id = ?, title = ?, description = ?, price = ?, city = ?
                WHERE id = ? AND user_id = ?
                """,
                (category_id, title, description, price, city, ad_id, user_id)
            )
        changed = cursor.rowcount > 0
        connection.commit()
        return changed
    except fdb.DatabaseError:
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()


def delete_ad(ad_id, user_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM ads WHERE id = ? AND user_id = ?", (ad_id, user_id))
        changed = cursor.rowcount > 0
        connection.commit()
        return changed
    finally:
        cursor.close()
        connection.close()


def get_user_ads(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT ads.id, ads.title, ads.price, ads.city, categories.name
            FROM ads JOIN categories ON ads.category_id = categories.id
            WHERE ads.user_id = ? ORDER BY ads.id DESC
            """,
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def add_favorite(user_id, ad_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)", (user_id, ad_id))
        connection.commit()
        return True
    except fdb.DatabaseError:
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()


def remove_favorite(user_id, ad_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM favorites WHERE user_id = ? AND ad_id = ?", (user_id, ad_id))
        connection.commit()
        return True
    finally:
        cursor.close()
        connection.close()


def is_favorite(user_id, ad_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT id FROM favorites WHERE user_id = ? AND ad_id = ?", (user_id, ad_id))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        connection.close()


def get_user_favorites(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT ads.id, ads.title, ads.price, ads.city,
                   CASE WHEN ads.image IS NULL THEN 0 ELSE 1 END,
                   categories.name
            FROM favorites
            JOIN ads ON favorites.ad_id = ads.id
            JOIN categories ON ads.category_id = categories.id
            WHERE favorites.user_id = ? ORDER BY favorites.id DESC
            """,
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def send_message(sender_id, receiver_id, ad_id, message_text):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO messages (sender_id, receiver_id, ad_id, message_text, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (sender_id, receiver_id, ad_id, message_text)
        )
        connection.commit()
        return True
    except fdb.DatabaseError:
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()


def get_dialog(user_id, other_id, ad_id=None):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        sql = """
            SELECT messages.id, messages.sender_id, messages.receiver_id,
                   messages.ad_id, messages.message_text, messages.created_at, users.login
            FROM messages JOIN users ON messages.sender_id = users.id
            WHERE ((messages.sender_id = ? AND messages.receiver_id = ?)
                OR (messages.sender_id = ? AND messages.receiver_id = ?))
        """
        params = [user_id, other_id, other_id, user_id]
        if ad_id is not None:
            sql += " AND messages.ad_id = ?"
            params.append(ad_id)
        sql += " ORDER BY messages.created_at, messages.id"
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_conversations(user_id):
    """Список диалогов: отдельная переписка по каждому объявлению."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT messages.sender_id, messages.receiver_id, messages.ad_id,
                   messages.message_text, messages.created_at,
                   sender.login, receiver.login, ads.title
            FROM messages
            JOIN users sender ON sender.id = messages.sender_id
            JOIN users receiver ON receiver.id = messages.receiver_id
            LEFT JOIN ads ON ads.id = messages.ad_id
            WHERE messages.sender_id = ? OR messages.receiver_id = ?
            ORDER BY messages.created_at DESC, messages.id DESC
            """,
            (user_id, user_id)
        )
        rows = cursor.fetchall()
        conversations = []
        seen = set()
        for row in rows:
            other_id = row[1] if row[0] == user_id else row[0]
            ad_id = row[2]
            key = (other_id, ad_id)
            if key in seen:
                continue
            seen.add(key)
            other_login = row[6] if row[0] == user_id else row[5]
            # Tuple: other user ID, login, ad ID, ad title, latest message, time
            conversations.append((other_id, other_login, ad_id, row[7], row[3], row[4]))
        return conversations
    finally:
        cursor.close()
        connection.close()
