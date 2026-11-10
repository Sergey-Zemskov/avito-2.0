import fdb
import hashlib


# Настройки подключения к базе данных
DB_PATH = "/opt/avito_db/AVITO.DB"
HOST = "localhost"
USER = "sysdba"
PASSWORD = "masterkey"
CHARSET = "UTF8"


def get_connection():
    """Подключение к базе данных."""
    return fdb.connect(
        dsn=f"{HOST}:{DB_PATH}",
        user=USER,
        password=PASSWORD,
        charset=CHARSET
    )


def hash_password(password):
    """Хеширование пароля."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(login, password):
    """Регистрация пользователя."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        password_hash = hash_password(password)

        cursor.execute(
            """
            INSERT INTO users (login, password_hash, role)
            VALUES (?, ?, ?)
            RETURNING id
            """,
            (login, password_hash, "user")
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
    """Проверка логина и пароля."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        password_hash = hash_password(password)

        cursor.execute(
            """
            SELECT id, login, role
            FROM users
            WHERE login = ? AND password_hash = ?
            """,
            (login, password_hash)
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def get_user_by_id(user_id):
    """Получение пользователя по ID."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT id, login, role FROM users WHERE id = ?",
            (user_id,)
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def get_all_categories():
    """Получение всех категорий."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT id, name, description FROM categories ORDER BY name"
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_all_cities():
    """Получение списка городов из объявлений."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT DISTINCT city
            FROM ads
            WHERE city IS NOT NULL
            ORDER BY city
            """
        )

        return [row[0] for row in cursor.fetchall()]

    finally:
        cursor.close()
        connection.close()


def get_catalog(search_query="", category_id=None, city="", sort_by="date"):
    """Получение объявлений с поиском и фильтрами."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        sql = """
            SELECT
                ads.id,
                ads.title,
                ads.price,
                ads.city,
                ads.image_url,
                categories.name,
                users.login
            FROM ads
            JOIN categories ON ads.category_id = categories.id
            JOIN users ON ads.user_id = users.id
            WHERE 1 = 1
        """

        params = []

        if search_query:
            sql += """
                AND (
                    LOWER(ads.title) LIKE ?
                    OR LOWER(ads.description) LIKE ?
                )
            """
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
    """Получение подробной информации об объявлении."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                ads.id,
                ads.title,
                ads.description,
                ads.price,
                ads.city,
                ads.image_url,
                ads.category_id,
                categories.name,
                ads.user_id,
                users.login
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


def create_ad(user_id, category_id, title, description,
              price, city, image_url=None):
    """Создание объявления."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
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

        connection.commit()
        return True

    except fdb.DatabaseError:
        connection.rollback()
        return False

    finally:
        cursor.close()
        connection.close()


def update_ad(ad_id, user_id, category_id, title,
              description, price, city, image_url=None):
    """Изменение объявления."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
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

        connection.commit()
        return cursor.rowcount > 0

    except fdb.DatabaseError:
        connection.rollback()
        return False

    finally:
        cursor.close()
        connection.close()


def delete_ad(ad_id, user_id):
    """Удаление объявления."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM ads WHERE id = ? AND user_id = ?",
            (ad_id, user_id)
        )

        connection.commit()
        return cursor.rowcount > 0

    finally:
        cursor.close()
        connection.close()


def get_user_ads(user_id):
    """Получение объявлений пользователя."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                ads.id,
                ads.title,
                ads.price,
                ads.city,
                categories.name
            FROM ads
            JOIN categories ON ads.category_id = categories.id
            WHERE ads.user_id = ?
            ORDER BY ads.id DESC
            """,
            (user_id,)
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def add_favorite(user_id, ad_id):
    """Добавление объявления в избранное."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO favorites (user_id, ad_id)
            VALUES (?, ?)
            """,
            (user_id, ad_id)
        )

        connection.commit()
        return True

    except fdb.DatabaseError:
        connection.rollback()
        return False

    finally:
        cursor.close()
        connection.close()


def remove_favorite(user_id, ad_id):
    """Удаление объявления из избранного."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM favorites
            WHERE user_id = ? AND ad_id = ?
            """,
            (user_id, ad_id)
        )

        connection.commit()
        return True

    finally:
        cursor.close()
        connection.close()


def is_favorite(user_id, ad_id):
    """Проверка наличия объявления в избранном."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT id
            FROM favorites
            WHERE user_id = ? AND ad_id = ?
            """,
            (user_id, ad_id)
        )

        return cursor.fetchone() is not None

    finally:
        cursor.close()
        connection.close()


def get_user_favorites(user_id):
    """Получение избранных объявлений пользователя."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                ads.id,
                ads.title,
                ads.price,
                ads.city,
                ads.image_url,
                categories.name
            FROM favorites
            JOIN ads ON favorites.ad_id = ads.id
            JOIN categories ON ads.category_id = categories.id
            WHERE favorites.user_id = ?
            ORDER BY favorites.id DESC
            """,
            (user_id,)
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def send_message(sender_id, receiver_id, ad_id, message_text):
    """Отправка сообщения."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO messages (
                sender_id,
                receiver_id,
                ad_id,
                message_text,
                created_at
            )
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
    """Получение переписки двух пользователей."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        sql = """
            SELECT
                messages.id,
                messages.sender_id,
                messages.receiver_id,
                messages.ad_id,
                messages.message_text,
                messages.created_at,
                users.login
            FROM messages
            JOIN users ON messages.sender_id = users.id
            WHERE (
                (messages.sender_id = ? AND messages.receiver_id = ?)
                OR
                (messages.sender_id = ? AND messages.receiver_id = ?)
            )
        """

        params = [user_id, other_id, other_id, user_id]

        if ad_id is not None:
            sql += " AND messages.ad_id = ?"
            params.append(ad_id)

        sql += " ORDER BY messages.created_at"

        cursor.execute(sql, tuple(params))

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_conversations(user_id):
    """Получение списка собеседников пользователя."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN messages.sender_id = ?
                    THEN messages.receiver_id
                    ELSE messages.sender_id
                END AS other_user_id,

                users.login,

                MAX(messages.created_at) AS last_message

            FROM messages

            JOIN users ON users.id =
                CASE
                    WHEN messages.sender_id = ?
                    THEN messages.receiver_id
                    ELSE messages.sender_id
                END

            WHERE messages.sender_id = ?
               OR messages.receiver_id = ?

            GROUP BY
                CASE
                    WHEN messages.sender_id = ?
                    THEN messages.receiver_id
                    ELSE messages.sender_id
                END,
                users.login

            ORDER BY last_message DESC
            """,
            (user_id, user_id, user_id, user_id, user_id)
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()