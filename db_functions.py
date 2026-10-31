import fdb
import hashlib
import os

# Настройки подключения к БД (замените под свои)
DB_HOST = "localhost"
DB_PATH = "/home/user/avito_db/AVITO.DB"
DB_USER = "sysdba"
DB_PASSWORD = "masterkey"
DB_CHARSET = "UTF8"


def get_connection():
    """Возвращает соединение с базой данных."""
    return fdb.connect(
        host=DB_HOST,
        database=DB_PATH,
        user=DB_USER,
        password=DB_PASSWORD,
        charset=DB_CHARSET
    )


def get_next_id(cursor, table_name):
    """Вспомогательная функция для получения следующего ID (так как в Firebird нет автоинкремента по умолчанию)."""
    cursor.execute(f"SELECT MAX(id) FROM {table_name}")
    row = cursor.fetchone()
    if row[0] is None:
        return 1
    return row[0] + 1


# ==========================================
# 1. Регистрация и авторизация
# ==========================================

def register_user(login, password):
    """Создает нового пользователя с хэшированным паролем."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        new_id = get_next_id(cur, "USERS")
        # Хэшируем пароль перед сохранением (безопасность)
        pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        
        cur.execute(
            "INSERT INTO USERS (ID, LOGIN, PASSWORD_HASH, ROLE) VALUES (?, ?, ?, ?)",
            (new_id, login, pwd_hash, 'user')
        )
        conn.commit()
        return True
    except fdb.DatabaseError:
        # Если логин уже существует (UNIQUE constraint)
        return False
    finally:
        cur.close()
        conn.close()


def login_user(login, password):
    """Проверяет логин и пароль. Возвращает ID пользователя, если вход успешен."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        cur.execute(
            "SELECT ID FROM USERS WHERE LOGIN = ? AND PASSWORD_HASH = ?",
            (login, pwd_hash)
        )
        row = cur.fetchone()
        if row:
            return row[0] # Возвращаем ID пользователя
        return None
    finally:
        cur.close()
        conn.close()


# ==========================================
# 2. Просмотр, поиск, фильтрация и сортировка (Каталог)
# ==========================================

def get_catalog(search_query="", category_id=None, city=None, sort_by="date"):
    """Возвращает список объявлений с фильтрацией и сортировкой."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Базовый запрос с JOIN для получения названия категории и логина продавца
    sql = """
        SELECT a.ID, a.TITLE, a.PRICE, a.CITY, c.NAME as CATEGORY, u.LOGIN as SELLER
        FROM ADS a
        JOIN CATEGORIES c ON a.CATEGORY_ID = c.ID
        JOIN USERS u ON a.USER_ID = u.ID
        WHERE 1=1
    """
    params = []

    if search_query:
        sql += " AND a.TITLE LIKE ?"
        params.append(f"%{search_query}%")
    if category_id:
        sql += " AND a.CATEGORY_ID = ?"
        params.append(category_id)
    if city:
        sql += " AND a.CITY = ?"
        params.append(city)

    # Сортировка (по цене или по дате (ID))
    if sort_by == "price":
        sql += " ORDER BY a.PRICE ASC"
    else:
        sql += " ORDER BY a.ID DESC" # Сначала новые

    cur.execute(sql, params)
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


def get_all_categories():
    """Возвращает все категории для выпадающего списка фильтра."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ID, NAME FROM CATEGORIES")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# ==========================================
# 3. Просмотр карточки объявления
# ==========================================

def get_ad_details(ad_id):
    """Возвращает полную информацию об объявлении (включая фото BLOB)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.ID, a.TITLE, a.DESCRIPTION, a.PRICE, a.CITY, 
               c.NAME as CATEGORY, u.LOGIN as SELLER, a.USER_ID, a.IMAGE
        FROM ADS a
        JOIN CATEGORIES c ON a.CATEGORY_ID = c.ID
        JOIN USERS u ON a.USER_ID = u.ID
        WHERE a.ID = ?
    """, (ad_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# ==========================================
# 4. Избранное
# ==========================================

def add_to_favorites(user_id, ad_id):
    """Добавляет объявление в избранное."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        new_id = get_next_id(cur, "FAVORITES")
        cur.execute("INSERT INTO FAVORITES (ID, USER_ID, AD_ID) VALUES (?, ?, ?)", (new_id, user_id, ad_id))
        conn.commit()
        return True
    except fdb.DatabaseError:
        return False # Уже добавлено
    finally:
        cur.close()
        conn.close()


def get_favorites(user_id):
    """Возвращает избранные объявления пользователя."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.ID, a.TITLE, a.PRICE, a.CITY
        FROM FAVORITES f
        JOIN ADS a ON f.AD_ID = a.ID
        WHERE f.USER_ID = ?
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# ==========================================
# 5. Управление объявлениями (Добавление, Редактирование, Удаление)
# ==========================================

def create_ad(user_id, category_id, title, description, price, city, image_path=None):
    """Создает новое объявление. Читает картинку как BLOB."""
    image_data = None
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_data = f.read() # Читаем байты

    conn = get_connection()
    cur = conn.cursor()
    new_id = get_next_id(cur, "ADS")
    cur.execute("""
        INSERT INTO ADS (ID, USER_ID, CATEGORY_ID, TITLE, DESCRIPTION, PRICE, CITY, IMAGE)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (new_id, user_id, category_id, title, description, price, city, image_data))
    conn.commit()
    cur.close()
    conn.close()


def update_ad(ad_id, user_id, title, description, price, city, category_id, image_path=None):
    """Редактирует объявление (только если это владелец)."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Проверка, что объявление принадлежит этому пользователю
    cur.execute("SELECT USER_ID FROM ADS WHERE ID = ?", (ad_id,))
    owner = cur.fetchone()
    if not owner or owner[0] != user_id:
        cur.close()
        conn.close()
        return False

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_data = f.read()
        cur.execute("""
            UPDATE ADS SET TITLE=?, DESCRIPTION=?, PRICE=?, CITY=?, CATEGORY_ID=?, IMAGE=? WHERE ID=?
        """, (title, description, price, city, category_id, image_data, ad_id))
    else:
        cur.execute("""
            UPDATE ADS SET TITLE=?, DESCRIPTION=?, PRICE=?, CITY=?, CATEGORY_ID=? WHERE ID=?
        """, (title, description, price, city, category_id, ad_id))
    
    conn.commit()
    cur.close()
    conn.close()
    return True


def delete_ad(ad_id, user_id):
    """Удаляет объявление (только владелец)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT USER_ID FROM ADS WHERE ID = ?", (ad_id,))
    owner = cur.fetchone()
    
    if owner and owner[0] == user_id:
        # Благодаря ON DELETE CASCADE в БД, связанные FAVORITES и MESSAGES удалятся сами
        cur.execute("DELETE FROM ADS WHERE ID = ?", (ad_id,))
        conn.commit()
        success = True
    else:
        success = False
        
    cur.close()
    conn.close()
    return success


# ==========================================
# 6. Чат (Сообщения)
# ==========================================

def send_message(sender_id, receiver_id, ad_id, text):
    """Отправляет сообщение продавцу по объявлению."""
    conn = get_connection()
    cur = conn.cursor()
    new_id = get_next_id(cur, "MESSAGES")
    cur.execute("""
        INSERT INTO MESSAGES (ID, SENDER_ID, RECEIVER_ID, AD_ID, MESSAGE_TEXT)
        VALUES (?, ?, ?, ?, ?)
    """, (new_id, sender_id, receiver_id, ad_id, text))
    conn.commit()
    cur.close()
    conn.close()


def get_chat_history(user1_id, user2_id, ad_id):
    """Возвращает переписку между двумя пользователями по конкретному объявлению."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT SENDER_ID, MESSAGE_TEXT, CREATED_AT
        FROM MESSAGES
        WHERE AD_ID = ? 
          AND ((SENDER_ID = ? AND RECEIVER_ID = ?) OR (SENDER_ID = ? AND RECEIVER_ID = ?))
        ORDER BY CREATED_AT ASC
    """, (ad_id, user1_id, user2_id, user2_id, user1_id))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows