
import fdb
import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# ПОДКЛЮЧЕНИЕ К РЕД БАЗЕ ДАННЫХ
# ============================================================

DB_PATH = "/opt/avito_db/AVITO.DB"

HOST = "localhost"
USER = "sysdba"
PASSWORD = "masterkey"
CHARSET = "UTF8"


def get_connection():
    """Создаёт подключение к базе данных."""
    return fdb.connect(
        dsn=f"{HOST}:{DB_PATH}",
        user=USER,
        password=PASSWORD,
        charset=CHARSET
    )


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _hash(password):
    """SHA256 для совместимости со старыми записями."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password, stored_hash):
    """
    Проверяет пароль.
    Поддерживает старые SHA256-хеши и новые Werkzeug-хеши.
    """
    if not password or not stored_hash:
        return False

    # Старый формат SHA256
    if len(stored_hash) == 64:
        old_hash = _hash(password)
        return hmac.compare_digest(old_hash, stored_hash)

    # Новый формат Werkzeug
    try:
        return check_password_hash(stored_hash, password)
    except (ValueError, TypeError):
        return False


def _valid_id(value):
    """Проверяет идентификатор."""
    try:
        value = int(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _valid_price(value):
    """Проверяет и преобразует цену."""
    try:
        price = Decimal(str(value).replace(",", "."))

        if not price.is_finite():
            return None

        if price < 0 or price > Decimal("9999999999.99"):
            return None

        return price.quantize(Decimal("0.01"))

    except (InvalidOperation, TypeError, ValueError):
        return None


def _close(cur, conn):
    """Безопасно закрывает курсор и соединение."""
    if cur:
        try:
            cur.close()
        except Exception:
            pass

    if conn:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def register_user(login, password):
    """Регистрирует нового пользователя."""
    if not login or not password:
        return None

    login = login.strip()

    if len(login) < 3 or len(login) > 50:
        return None

    if len(password) < 4:
        return None

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        password_hash = generate_password_hash(password)

        cur.execute(
            """
            INSERT INTO users (login, password_hash, role)
            VALUES (?, ?, 'user')
            RETURNING id
            """,
            (login, password_hash)
        )

        row = cur.fetchone()
        user_id = row[0] if row else None

        conn.commit()
        return user_id

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print("register_user:", error)
        return None

    finally:
        _close(cur, conn)


def login_user(login, password):
    """Авторизует пользователя."""
    if not login or not password:
        return None

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, login, password_hash, role
            FROM users
            WHERE login = ?
            """,
            (login.strip(),)
        )

        row = cur.fetchone()

        if not row:
            return None

        user_id, user_login, stored_hash, role = row

        if not _verify_password(password, stored_hash):
            return None

        # При успешном входе обновляем старый SHA256-хеш
        if len(stored_hash) == 64:
            new_hash = generate_password_hash(password)

            cur.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (new_hash, user_id)
            )

            conn.commit()

        return user_id, user_login, role

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print("login_user:", error)
        return None

    finally:
        _close(cur, conn)


def get_user_by_id(user_id):
    """Возвращает пользователя по ID."""
    user_id = _valid_id(user_id)

    if not user_id:
        return None

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, login, role
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        )

        return cur.fetchone()

    finally:
        _close(cur, conn)


# ============================================================
# КАТЕГОРИИ И ГОРОДА
# ============================================================

def get_all_categories():
    """Возвращает список категорий."""
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, name
            FROM categories
            ORDER BY name
            """
        )

        return cur.fetchall()

    finally:
        _close(cur, conn)


def get_all_cities():
    """Возвращает список городов, в которых есть объявления."""
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT DISTINCT city
            FROM ads
            WHERE city IS NOT NULL
            ORDER BY city
            """
        )

        return [row[0] for row in cur.fetchall()]

    finally:
        _close(cur, conn)


# ============================================================
# ОБЪЯВЛЕНИЯ
# ============================================================

def get_catalog(
    search_query="",
    category_id=None,
    city="",
    sort_by="date",
    limit=200
):
    """
    Возвращает каталог объявлений.

    Формат строки:
    0 - ID объявления
    1 - название
    2 - цена
    3 - город
    4 - ссылка на изображение
    5 - категория
    6 - логин продавца
    """
    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        sql = """
            SELECT
                a.id,
                a.title,
                a.price,
                a.city,
                a.image_url,
                c.name,
                u.login
            FROM ads a
            JOIN categories c ON a.category_id = c.id
            JOIN users u ON a.user_id = u.id
            WHERE 1 = 1
        """

        params = []

        if search_query:
            search = f"%{search_query.strip().lower()}%"

            sql += """
                AND (
                    LOWER(a.title) LIKE ?
                    OR LOWER(a.description) LIKE ?
                )
            """

            params.extend([search, search])

        if category_id:
            category_id = _valid_id(category_id)

            if category_id:
                sql += " AND a.category_id = ?"
                params.append(category_id)

        if city:
            sql += " AND a.city = ?"
            params.append(city)

        if sort_by == "price_asc":
            sql += " ORDER BY a.price ASC"
        elif sort_by == "price_desc":
            sql += " ORDER BY a.price DESC"
        else:
            sql += " ORDER BY a.id DESC"

        # Лимит проверяется и вставляется как целое число.
        # Это исключает подстановку SQL-кода через параметр limit.
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 200

        limit = max(1, min(limit, 500))

        sql += f" ROWS {limit}"

        cur.execute(sql, params)

        return cur.fetchall()

    finally:
        _close(cur, conn)


def get_ad_details(ad_id):
    """
    Возвращает подробную информацию об объявлении.

    Формат строки:
    0 - ID объявления
    1 - название
    2 - описание
    3 - цена
    4 - город
    5 - ссылка на изображение
    6 - ID категории
    7 - название категории
    8 - ID продавца
    9 - логин продавца
    """
    ad_id = _valid_id(ad_id)

    if not ad_id:
        return None

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                a.id,
                a.title,
                a.description,
                a.price,
                a.city,
                a.image_url,
                c.id,
                c.name,
                u.id,
                u.login
            FROM ads a
            JOIN categories c ON a.category_id = c.id
            JOIN users u ON a.user_id = u.id
            WHERE a.id = ?
            """,
            (ad_id,)
        )

        return cur.fetchone()

    finally:
        _close(cur, conn)


def get_ad_image(ad_id):
    """
    Временная заглушка для изображения.

    Сейчас таблица ads использует image_url.
    BLOB-хранение фотографий пока не реализовано.
    """
    ad = get_ad_details(ad_id)

    if not ad:
        return None

    return ad[5]


def create_ad(
    user_id,
    category_id,
    title,
    description,
    price,
    city,
    image_url=None
):
    """Создаёт объявление."""
    user_id = _valid_id(user_id)
    category_id = _valid_id(category_id)
    price = _valid_price(price)

    if not user_id or not category_id or price is None:
        return None

    if not title or not description or not city:
        return None

    title = title.strip()
    description = description.strip()
    city = city.strip()

    if not title or len(title) > 150:
        return None

    if len(description) > 5000 or len(city) > 100:
        return None

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO ads (
                user_id,
                category_id,
                title,
                description,
                price,
                city,
                image_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                user_id,
                category_id,
                title,
                description,
                price,
                city,
                image_url
            )
        )

        row = cur.fetchone()
        ad_id = row[0] if row else None

        conn.commit()
        return ad_id

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print("create_ad:", error)
        return None

    finally:
        _close(cur, conn)


def update_ad(
    ad_id,
    user_id,
    category_id,
    title,
    description,
    price,
    city,
    image_url=None
):
    """Изменяет объявление. Изменять его может только владелец."""
    ad_id = _valid_id(ad_id)
    user_id = _valid_id(user_id)
    category_id = _valid_id(category_id)
    price = _valid_price(price)

    if not ad_id or not user_id or not category_id:
        return False

    if price is None or not title or not description or not city:
        return False

    title = title.strip()
    description = description.strip()
    city = city.strip()

    if not title or len(title) > 150:
        return False

    if len(description) > 5000 or len(city) > 100:
        return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE ads
            SET
                category_id = ?,
                title = ?,
                description = ?,
                price = ?,
                city = ?,
                image_url = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                category_id,
                title,
                description,
                price,
                city,
                image_url,
                ad_id,
                user_id
            )
        )

        updated = cur.rowcount > 0

        conn.commit()
        return updated

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print("update_ad:", error)
        return False

    finally:
        _close(cur, conn)


def delete_ad(ad_id, user_id):
    """Удаляет объявление только его владельцем."""
    ad_id = _valid_id(ad_id)
    user_id = _valid_id(user_id)

    if not ad_id or not user_id:
        return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM ads
            WHERE id = ? AND user_id = ?
            """,
            (ad_id, user_id)
        )

        deleted = cur.rowcount > 0

        conn.commit()
        return deleted

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print("delete_ad:", error)
        return False

    finally:
        _close(cur, conn)


def get_user_ads(user_id):
    """Возвращает объявления конкретного пользователя."""
    user_id = _valid_id(user_id)

    if not user_id:
        return []

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                a.id,
                a.title,
                a.price,
                a.city,
                c.name
            FROM ads a
            JOIN categories c ON a.category_id = c.id
            WHERE a.user_id = ?
            ORDER BY a.id DESC
            """,
            (user_id,)
        )

        return cur.fetchall()

    finally:
        _close(cur, conn)


# ============================================================
# ИЗБРАННОЕ
# ============================================================

def add_favorite(user_id, ad_id):
    """Добавляет объявление в избранное."""
    user_id = _valid_id(user_id)
    ad_id = _valid_id(ad_id)

    if not user_id or not ad_id:
        return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Не добавляем повторно уже существующую запись.
        cur.execute(
            """
            SELECT 1
            FROM favorites
            WHERE user_id = ? AND ad_id = ?
            """,
            (user_id, ad_id)
        )

        if cur.fetchone():
            return True

        cur.execute(
            """
            INSERT INTO favorites (user_id, ad_id)
            VALUES (?, ?)
            """,
            (user_id, ad_id)
        )

        conn.commit()
        return True

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print("add_favorite:", error)
        return False

    finally:
        _close(cur, conn)


def remove_favorite(user_id, ad_id):
    """Удаляет объявление из избранного."""
    user_id = _valid_id(user_id)
    ad_id = _valid_id(ad_id)

    if not user_id or not ad_id:
        return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM favorites
            WHERE user_id = ? AND ad_id = ?
            """,
            (user_id, ad_id)
        )

        removed = cur.rowcount > 0

        conn.commit()
        return removed

    finally:
        _close(cur, conn)


def is_favorite(user_id, ad_id):
    """Проверяет наличие объявления в избранном."""
    user_id = _valid_id(user_id)
    ad_id = _valid_id(ad_id)

    if not user_id or not ad_id:
        return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM favorites
            WHERE user_id = ? AND ad_id = ?
            """,
            (user_id, ad_id)
        )

        return cur.fetchone() is not None

    finally:
        _close(cur, conn)


def get_user_favorites(user_id):
    """
    Возвращает избранные объявления.

    Формат строки:
    0 - ID объявления
    1 - название
    2 - цена
    3 - город
    4 - ссылка на изображение
    5 - категория
    """
    user_id = _valid_id(user_id)

    if not user_id:
        return []

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                a.id,
                a.title,
                a.price,
                a.city,
                a.image_url,
                c.name
            FROM favorites f
            JOIN ads a ON f.ad_id = a.id
            JOIN categories c ON a.category_id = c.id
            WHERE f.user_id = ?
            ORDER BY f.id DESC
            """,
            (user_id,)
        )

        return cur.fetchall()

    finally:
        _close(cur, conn)


# ============================================================
# СООБЩЕНИЯ И ЧАТ
# ============================================================

def send_message(sender_id, receiver_id, ad_id, text):
    """Отправляет сообщение между двумя пользователями."""
    sender_id = _valid_id(sender_id)
    receiver_id = _valid_id(receiver_id)

    if not sender_id or not receiver_id:
        return False

    if sender_id == receiver_id:
        return False

    if not text or not text.strip():
        return False

    text = text.strip()

    if len(text) > 5000:
        return False

    if ad_id is not None:
        ad_id = _valid_id(ad_id)

        if not ad_id:
            return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Проверяем существование получателя.
        cur.execute(
            "SELECT id FROM users WHERE id = ?",
            (receiver_id,)
        )

        if not cur.fetchone():
            return False

        # Проверяем существование отправителя.
        cur.execute(
            "SELECT id FROM users WHERE id = ?",
            (sender_id,)
        )

        if not cur.fetchone():
            return False

        # Если сообщение относится к объявлению,
        # отправитель и получатель должны быть его участниками:
        # продавцом или покупателем.
        if ad_id is not None:
            cur.execute(
                """
                SELECT user_id
                FROM ads
                WHERE id = ?
                """,
                (ad_id,)
            )

            ad = cur.fetchone()

            if not ad:
                return False

            seller_id = ad[0]

            if sender_id != seller_id and receiver_id != seller_id:
                return False

        cur.execute(
            """
            INSERT INTO messages (
                sender_id,
                receiver_id,
                ad_id,
                message_text
            )
            VALUES (?, ?, ?, ?)
            """,
            (sender_id, receiver_id, ad_id, text)
        )

        conn.commit()
        return True

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print("send_message:", error)
        return False

    finally:
        _close(cur, conn)


def get_dialog(user_id, other_id, ad_id=None):
    """
    Возвращает переписку между двумя пользователями.

    Формат строки:
    0 - ID сообщения
    1 - ID отправителя
    2 - ID получателя
    3 - ID объявления
    4 - текст сообщения
    5 - дата отправки
    6 - логин отправителя
    """
    user_id = _valid_id(user_id)
    other_id = _valid_id(other_id)

    if not user_id or not other_id:
        return []

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        sql = """
            SELECT
                m.id,
                m.sender_id,
                m.receiver_id,
                m.ad_id,
                m.message_text,
                m.created_at,
                u.login
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE (
                (m.sender_id = ? AND m.receiver_id = ?)
                OR
                (m.sender_id = ? AND m.receiver_id = ?)
            )
        """

        params = [
            user_id,
            other_id,
            other_id,
            user_id
        ]

        if ad_id is not None:
            ad_id = _valid_id(ad_id)

            if not ad_id:
                return []

            sql += " AND m.ad_id = ?"
            params.append(ad_id)

        sql += " ORDER BY m.created_at ASC"

        cur.execute(sql, params)

        return cur.fetchall()

    finally:
        _close(cur, conn)


def get_conversations(user_id):
    """
    Возвращает список собеседников пользователя.

    Формат строки:
    0 - ID собеседника
    1 - логин собеседника
    2 - время последнего сообщения
    """
    user_id = _valid_id(user_id)

    if not user_id:
        return []

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                u.id,
                u.login,
                MAX(m.created_at)
            FROM messages m
            JOIN users u
                ON u.id = CASE
                    WHEN m.sender_id = ?
                    THEN m.receiver_id
                    ELSE m.sender_id
                END
            WHERE
                m.sender_id = ?
                OR m.receiver_id = ?
            GROUP BY u.id, u.login
            ORDER BY 3 DESC
            """,
            (user_id, user_id, user_id)
        )

        return cur.fetchall()

    finally:
        _close(cur, conn)
