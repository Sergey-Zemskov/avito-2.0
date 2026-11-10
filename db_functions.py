
"""
db_functions.py

Слой доступа к базе данных портала частных объявлений.

СУБД: Firebird
Драйвер: fdb
Хэширование паролей: Werkzeug
Фотографии: временная заглушка через IMAGE_URL.

Совместим с существующей схемой:
    USERS
    CATEGORIES
    ADS
    FAVORITES
    MESSAGES
"""

import os
import hashlib
import hmac
from decimal import Decimal, InvalidOperation

import fdb
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


# ============================================================
# НАСТРОЙКИ ПОДКЛЮЧЕНИЯ
# ============================================================

DB_PATH = os.getenv("DB_PATH", "/opt/avito_db/AVITO.DB")
HOST = os.getenv("DB_HOST", "localhost")
USER = os.getenv("DB_USER", "sysdba")
PASSWORD = os.getenv("DB_PASSWORD", "masterkey")
CHARSET = os.getenv("DB_CHARSET", "UTF8")


def get_connection():
    """
    Создаёт соединение с Firebird.

    Настройки подключения можно переопределить
    через переменные окружения.
    """
    return fdb.connect(
        dsn=f"{HOST}:{DB_PATH}",
        user=USER,
        password=PASSWORD,
        charset=CHARSET,
    )


def _valid_id(value):
    """Проверяет корректность идентификатора."""
    try:
        value = int(value)
        return value if value > 0 else None
    except (ValueError, TypeError):
        return None


def _valid_price(value):
    """Проверяет и нормализует цену."""
    try:
        price = Decimal(str(value).replace(",", "."))
        if not price.is_finite() or price < 0:
            return None
        if price > Decimal("9999999999.99"):
            return None
        return price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _legacy_hash(password):
    """
    Старый формат паролей.

    Используется только для проверки существующих аккаунтов
    и последующего автоматического обновления хэша.
    """
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def _verify_password(password, stored_hash):
    """
    Проверяет новый и старый формат хэша.

    Старый SHA-256 распознаётся для совместимости
    с ранее созданными пользователями.
    """
    if not password or not stored_hash:
        return False, False

    # Новый формат Werkzeug.
    if stored_hash.startswith(("scrypt:", "pbkdf2:")):
        try:
            return check_password_hash(stored_hash, password), False
        except (ValueError, TypeError):
            return False, False

    # Старый SHA-256.
    legacy = _legacy_hash(password)

    if hmac.compare_digest(str(stored_hash), legacy):
        return True, True

    return False, False


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def register_user(login: str, password: str):
    """
    Регистрация пользователя.

    Возвращает:
        ID пользователя при успехе;
        None при ошибке.
    """
    login = (login or "").strip()

    if not 3 <= len(login) <= 50:
        return None

    if not password or len(password) < 6:
        return None

    if len(password) > 256:
        return None

    password_hash = generate_password_hash(password)

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users (login, password_hash, role)
            VALUES (?, ?, 'user')
            RETURNING id
            """,
            (login, password_hash),
        )

        row = cur.fetchone()
        user_id = row[0] if row else None

        conn.commit()
        return user_id

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"register_user: {error}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def login_user(login: str, password: str):
    """
    Авторизация пользователя.

    Поддерживает:
        - новые хэши Werkzeug;
        - старые SHA-256 хэши.

    При успешной авторизации со старым SHA-256
    автоматически обновляет пароль до Werkzeug.

    Возвращает кортеж:
        (id, login, role)

    При ошибке возвращает None.
    """
    login = (login or "").strip()

    if not login or not password:
        return None

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, login, role, password_hash
            FROM users
            WHERE login = ?
            """,
            (login,),
        )

        row = cur.fetchone()

        if not row:
            return None

        user_id, user_login, role, stored_hash = row

        valid, needs_upgrade = _verify_password(
            password,
            stored_hash,
        )

        if not valid:
            return None

        if needs_upgrade:
            new_hash = generate_password_hash(password)

            cur.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (new_hash, user_id),
            )

            conn.commit()

        return user_id, user_login, role

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"login_user: {error}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_user_by_id(user_id):
    """Получает пользователя по ID."""
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
            (user_id,),
        )

        return cur.fetchone()

    except fdb.DatabaseError as error:
        print(f"get_user_by_id: {error}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


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

    except fdb.DatabaseError as error:
        print(f"get_all_categories: {error}")
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_all_cities():
    """Возвращает список городов, присутствующих в объявлениях."""
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

    except fdb.DatabaseError as error:
        print(f"get_all_cities: {error}")
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# ОБЪЯВЛЕНИЯ
# ============================================================

def get_catalog(
    search_query="",
    category_id=None,
    city="",
    sort_by="date",
    limit=200,
):
    """
    Получает каталог объявлений.

    Формат строки:
        0 - ID объявления
        1 - название
        2 - цена
        3 - город
        4 - IMAGE_URL
        5 - название категории
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
            JOIN categories c ON c.id = a.category_id
            JOIN users u ON u.id = a.user_id
            WHERE 1 = 1
        """

        params = []

        search_query = (search_query or "").strip()
        city = (city or "").strip()

        if search_query:
            sql += """
                AND (
                    LOWER(a.title) LIKE ?
                    OR LOWER(a.description) LIKE ?
                )
            """

            pattern = f"%{search_query.lower()}%"
            params.extend([pattern, pattern])

        category_id = _valid_id(category_id)

        if category_id:
            sql += " AND a.category_id = ?"
            params.append(category_id)

        if city:
            sql += " AND LOWER(a.city) = ?"
            params.append(city.lower())

        if sort_by == "price_asc":
            sql += " ORDER BY a.price ASC, a.id DESC"

        elif sort_by == "price_desc":
            sql += " ORDER BY a.price DESC, a.id DESC"

        else:
            sql += " ORDER BY a.id DESC"

        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 200

        limit = max(1, min(limit, 500))

        # limit преобразован в целое число и ограничен диапазоном.
        # Поэтому здесь допустима подстановка числа в SQL.
        sql += f" ROWS {limit}"

        cur.execute(sql, params)

        return cur.fetchall()

    except fdb.DatabaseError as error:
        print(f"get_catalog: {error}")
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_ad_details(ad_id):
    """
    Получает полную информацию об объявлении.

    Формат результата:
        0 - ID объявления
        1 - название
        2 - описание
        3 - цена
        4 - город
        5 - IMAGE_URL
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
            JOIN categories c ON c.id = a.category_id
            JOIN users u ON u.id = a.user_id
            WHERE a.id = ?
            """,
            (ad_id,),
        )

        return cur.fetchone()

    except fdb.DatabaseError as error:
        print(f"get_ad_details: {error}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def create_ad(
    user_id,
    category_id,
    title,
    description,
    price,
    city,
    image_url=None,
):
    """Создаёт объявление и возвращает его ID."""
    user_id = _valid_id(user_id)
    category_id = _valid_id(category_id)
    title = (title or "").strip()
    description = (description or "").strip()
    city = (city or "").strip()
    price = _valid_price(price)

    if not user_id or not category_id:
        return None

    if not title or len(title) > 255:
        return None

    if len(description) > 2000:
        return None

    if not city or len(city) > 100:
        return None

    if price is None:
        return None

    if image_url and len(image_url) > 500:
        return None

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Проверяем существование пользователя и категории.
        cur.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,),
        )

        if not cur.fetchone():
            return None

        cur.execute(
            "SELECT id FROM categories WHERE id = ?",
            (category_id,),
        )

        if not cur.fetchone():
            return None

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
                image_url,
            ),
        )

        row = cur.fetchone()
        new_id = row[0] if row else None

        conn.commit()
        return new_id

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"create_ad: {error}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def update_ad(
    ad_id,
    user_id,
    category_id,
    title,
    description,
    price,
    city,
    image_url=None,
):
    """
    Обновляет объявление.

    Обновление выполняется только для объявления
    с указанным владельцем.
    """
    ad_id = _valid_id(ad_id)
    user_id = _valid_id(user_id)
    category_id = _valid_id(category_id)

    title = (title or "").strip()
    description = (description or "").strip()
    city = (city or "").strip()
    price = _valid_price(price)

    if not ad_id or not user_id or not category_id:
        return False

    if not title or len(title) > 255:
        return False

    if len(description) > 2000:
        return False

    if not city or len(city) > 100:
        return False

    if price is None:
        return False

    if image_url and len(image_url) > 500:
        return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT id FROM categories WHERE id = ?",
            (category_id,),
        )

        if not cur.fetchone():
            return False

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
                user_id,
            ),
        )

        updated = cur.rowcount > 0

        conn.commit()
        return updated

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"update_ad: {error}")
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


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
            (ad_id, user_id),
        )

        deleted = cur.rowcount > 0

        conn.commit()
        return deleted

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"delete_ad: {error}")
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


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
            JOIN categories c ON c.id = a.category_id
            WHERE a.user_id = ?
            ORDER BY a.id DESC
            """,
            (user_id,),
        )

        return cur.fetchall()

    except fdb.DatabaseError as error:
        print(f"get_user_ads: {error}")
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# ФОТОГРАФИИ — ВРЕМЕННАЯ ЗАГЛУШКА
# ============================================================

def get_ad_image(ad_id):
    """
    Временная заглушка для получения фотографии.

    Сейчас в БД хранится IMAGE_URL, а не BLOB.
    Функция возвращает ссылку, если она есть.

    Если фотографии нет, возвращается None.

    В будущем здесь можно реализовать получение
    двоичных данных изображения из BLOB.
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
            SELECT image_url
            FROM ads
            WHERE id = ?
            """,
            (ad_id,),
        )

        row = cur.fetchone()

        return row[0] if row else None

    except fdb.DatabaseError as error:
        print(f"get_ad_image: {error}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# ИЗБРАННОЕ
# ============================================================

def add_favorite(user_id, ad_id):
    """
    Добавляет объявление в избранное.

    Повторное добавление не создаёт дубликат.
    """
    user_id = _valid_id(user_id)
    ad_id = _valid_id(ad_id)

    if not user_id or not ad_id:
        return False

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Проверяем наличие объявления.
        cur.execute(
            "SELECT id FROM ads WHERE id = ?",
            (ad_id,),
        )

        if not cur.fetchone():
            return False

        cur.execute(
            """
            SELECT id
            FROM favorites
            WHERE user_id = ? AND ad_id = ?
            """,
            (user_id, ad_id),
        )

        if cur.fetchone():
            return True

        cur.execute(
            """
            INSERT INTO favorites (user_id, ad_id)
            VALUES (?, ?)
            """,
            (user_id, ad_id),
        )

        conn.commit()
        return True

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"add_favorite: {error}")
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


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
            (user_id, ad_id),
        )

        deleted = cur.rowcount > 0

        conn.commit()
        return deleted

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"remove_favorite: {error}")
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def is_favorite(user_id, ad_id):
    """Проверяет, находится ли объявление в избранном."""
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
            (user_id, ad_id),
        )

        return cur.fetchone() is not None

    except fdb.DatabaseError as error:
        print(f"is_favorite: {error}")
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_user_favorites(user_id):
    """
    Возвращает избранные объявления.

    Формат:
        0 - ID объявления
        1 - название
        2 - цена
        3 - город
        4 - IMAGE_URL
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
            JOIN ads a ON a.id = f.ad_id
            JOIN categories c ON c.id = a.category_id
            WHERE f.user_id = ?
            ORDER BY f.id DESC
            """,
            (user_id,),
        )

        return cur.fetchall()

    except fdb.DatabaseError as error:
        print(f"get_user_favorites: {error}")
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# СООБЩЕНИЯ И ЧАТ
# ============================================================

def send_message(sender_id, receiver_id, ad_id, text):
    """
    Отправляет сообщение.

    Проверки:
        - отправитель существует;
        - получатель существует;
        - пользователь не пишет самому себе;
        - сообщение не пустое;
        - длина сообщения не превышает 2000 символов;
        - объявление существует;
        - продавец объявления является одним из участников чата.

    Последняя проверка позволяет продавцу отвечать покупателю.
    """
    sender_id = _valid_id(sender_id)
    receiver_id = _valid_id(receiver_id)

    if not sender_id or not receiver_id:
        return False

    if sender_id == receiver_id:
        return False

    text = (text or "").strip()

    if not text or len(text) > 2000:
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

        # Проверка существования обоих участников.
        cur.execute(
            "SELECT id FROM users WHERE id = ?",
            (sender_id,),
        )

        if not cur.fetchone():
            return False

        cur.execute(
            "SELECT id FROM users WHERE id = ?",
            (receiver_id,),
        )

        if not cur.fetchone():
            return False

        if ad_id is not None:
            cur.execute(
                """
                SELECT user_id
                FROM ads
                WHERE id = ?
                """,
                (ad_id,),
            )

            ad = cur.fetchone()

            if not ad:
                return False

            seller_id = int(ad[0])

            # Один из участников диалога должен быть продавцом.
            if seller_id not in (sender_id, receiver_id):
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
            (
                sender_id,
                receiver_id,
                ad_id,
                text,
            ),
        )

        conn.commit()
        return True

    except fdb.DatabaseError as error:
        if conn:
            conn.rollback()

        print(f"send_message: {error}")
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_dialog(user_id, other_id, ad_id=None):
    """
    Получает переписку между двумя пользователями.

    Формат сообщения:
        0 - ID сообщения
        1 - ID отправителя
        2 - ID получателя
        3 - ID объявления
        4 - текст
        5 - дата
        6 - логин отправителя
    """
    user_id = _valid_id(user_id)
    other_id = _valid_id(other_id)

    if not user_id or not other_id or user_id == other_id:
        return []

    if ad_id is not None:
        ad_id = _valid_id(ad_id)

        if not ad_id:
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
            JOIN users u ON u.id = m.sender_id
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
            user_id,
        ]

        if ad_id is not None:
            sql += " AND m.ad_id = ?"
            params.append(ad_id)

        sql += " ORDER BY m.created_at ASC, m.id ASC"

        cur.execute(sql, params)

        return cur.fetchall()

    except fdb.DatabaseError as error:
        print(f"get_dialog: {error}")
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_conversations(user_id):
    """
    Возвращает список пользователей, с которыми
    текущий пользователь переписывался.

    Формат:
        0 - ID собеседника
        1 - логин собеседника
        2 - дата последнего сообщения
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
                MAX(m.created_at) AS last_message
            FROM messages m
            JOIN users u
                ON u.id = CASE
                    WHEN m.sender_id = ?
                    THEN m.receiver_id
                    ELSE m.sender_id
                END
            WHERE m.sender_id = ? OR m.receiver_id = ?
            GROUP BY u.id, u.login
            ORDER BY last_message DESC
            """,
            (
                user_id,
                user_id,
                user_id,
            ),
        )

        return cur.fetchall()

    except fdb.DatabaseError as error:
        print(f"get_conversations: {error}")
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
