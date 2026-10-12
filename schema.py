# -*- coding: utf-8 -*-
"""
Приведение схемы базы данных к «полному» виду (курсовая работа).

Скрипт идемпотентный: его можно запускать сколько угодно раз. Он
  1) добавляет недостающие столбцы;
  2) создаёт последовательности (генераторы) и триггеры автонумерации;
  3) создаёт индексы для ускорения поиска;
  4) накладывает ограничения целостности CHECK;
  5) создаёт представления (views) для отчётов и выборок;
  6) создаёт хранимые процедуры.

Запуск:  python schema.py
"""

import db
import config

# ---------------------------------------------------------------------------
# Вспомогательные проверки по системным таблицам Firebird
# ---------------------------------------------------------------------------

def _one(sql, params=None):
    return db.query_value(sql, params)


def table_exists(name):
    return bool(_one(
        "select count(*) from rdb$relations where rdb$relation_name = ?",
        [name.upper()]))


def view_exists(name):
    return bool(_one(
        "select count(*) from rdb$relations "
        "where rdb$relation_name = ? and rdb$view_blr is not null",
        [name.upper()]))


def column_exists(table, column):
    return bool(_one(
        "select count(*) from rdb$relation_fields "
        "where rdb$relation_name = ? and rdb$field_name = ?",
        [table.upper(), column.upper()]))


def sequence_exists(name):
    return bool(_one(
        "select count(*) from rdb$generators where rdb$generator_name = ?",
        [name.upper()]))


def trigger_exists(name):
    return bool(_one(
        "select count(*) from rdb$triggers where rdb$trigger_name = ?",
        [name.upper()]))


def index_exists(name):
    return bool(_one(
        "select count(*) from rdb$indices where rdb$index_name = ?",
        [name.upper()]))


def constraint_exists(name):
    return bool(_one(
        "select count(*) from rdb$relation_constraints "
        "where rdb$constraint_name = ?",
        [name.upper()]))


# ---------------------------------------------------------------------------
# Каталог изменений
# ---------------------------------------------------------------------------

# Новые столбцы: (таблица, столбец, описание)
COLUMNS = [
    ("users", "full_name",  "VARCHAR(150)"),
    ("users", "phone",      "VARCHAR(30)"),
    ("users", "email",      "VARCHAR(150)"),
    ("users", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("users", "is_blocked", "SMALLINT DEFAULT 0 NOT NULL"),

    ("categories", "icon", "VARCHAR(50)"),

    ("ads", "created_at",  "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("ads", "updated_at",  "TIMESTAMP"),
    ("ads", "status",      "VARCHAR(20) DEFAULT 'active' NOT NULL"),
    ("ads", "views_count", "INTEGER DEFAULT 0 NOT NULL"),

    ("favorites", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),

    ("messages", "is_read", "SMALLINT DEFAULT 0 NOT NULL"),
]

# Последовательности: (имя, таблица)
SEQUENCES = [
    ("seq_users_id", "users"),
    ("seq_categories_id", "categories"),
    ("seq_ads_id", "ads"),
    ("seq_favorites_id", "favorites"),
    ("seq_messages_id", "messages"),
]

# Триггеры автонумерации
AUTO_ID_TRIGGERS = [
    ("tr_users_bi", "users", "seq_users_id"),
    ("tr_categories_bi", "categories", "seq_categories_id"),
    ("tr_ads_bi", "ads", "seq_ads_id"),
    ("tr_favorites_bi", "favorites", "seq_favorites_id"),
    ("tr_messages_bi", "messages", "seq_messages_id"),
]

# Индексы: (имя, таблица, столбцы)
INDEXES = [
    ("idx_ads_category", "ads", "category_id"),
    ("idx_ads_user", "ads", "user_id"),
    ("idx_ads_city", "ads", "city"),
    ("idx_ads_status", "ads", "status"),
    ("idx_ads_price", "ads", "price"),
    ("idx_ads_created", "ads", "created_at"),
    ("idx_favorites_user", "favorites", "user_id"),
    ("idx_favorites_ad", "favorites", "ad_id"),
    ("idx_messages_sender", "messages", "sender_id"),
    ("idx_messages_receiver", "messages", "receiver_id"),
    ("idx_messages_created", "messages", "created_at"),
    ("idx_users_role", "users", "role"),
]

# Ограничения целостности: (имя, таблица, условие, пояснение)
CHECKS = [
    ("chk_users_role", "users", "role in ('user', 'admin')",
     "Роль пользователя может быть только «user» или «admin»"),
    ("chk_ads_price", "ads", "price >= 0",
     "Цена объявления не может быть отрицательной"),
    ("chk_ads_status", "ads",
     "status in ('active', 'sold', 'archived', 'blocked')",
     "Недопустимый статус объявления"),
    ("chk_ads_views", "ads", "views_count >= 0",
     "Счётчик просмотров не может быть отрицательным"),
    ("chk_messages_self", "messages", "sender_id <> receiver_id",
     "Пользователь не может отправить сообщение самому себе"),
]

# Представления: (имя, тело представления после имени)
VIEWS = [
    ("v_ads_full", """(
            ad_id, title, price, city, description, image_url, status,
            views_count, created_at, category_id, category_name,
            seller_id, seller_login, seller_name, seller_phone, favorites_count
        ) AS
        SELECT a.id, a.title, a.price, a.city, a.description, a.image_url,
               a.status, a.views_count, a.created_at,
               c.id, c.name,
               u.id, u.login, u.full_name, u.phone,
               (SELECT COUNT(*) FROM favorites f WHERE f.ad_id = a.id)
        FROM ads a
        JOIN categories c ON c.id = a.category_id
        JOIN users u ON u.id = a.user_id"""),
    ("v_category_stats", """(
            category_id, category_name, ads_count,
            min_price, max_price, avg_price, total_views
        ) AS
        SELECT c.id, c.name,
               (SELECT COUNT(*) FROM ads a WHERE a.category_id = c.id),
               (SELECT MIN(a.price) FROM ads a WHERE a.category_id = c.id),
               (SELECT MAX(a.price) FROM ads a WHERE a.category_id = c.id),
               (SELECT AVG(a.price) FROM ads a WHERE a.category_id = c.id),
               (SELECT COALESCE(SUM(a.views_count), 0) FROM ads a
                 WHERE a.category_id = c.id)
        FROM categories c"""),
    ("v_user_activity", """(
            user_id, login, full_name, role,
            ads_count, favorites_count, sent_messages, unread_messages
        ) AS
        SELECT u.id, u.login, u.full_name, u.role,
               (SELECT COUNT(*) FROM ads a WHERE a.user_id = u.id),
               (SELECT COUNT(*) FROM favorites f WHERE f.user_id = u.id),
               (SELECT COUNT(*) FROM messages m WHERE m.sender_id = u.id),
               (SELECT COUNT(*) FROM messages m
                 WHERE m.receiver_id = u.id AND m.is_read = 0)
        FROM users u"""),
]

# Хранимые процедуры: (имя, тело процедуры после имени)
PROCEDURES = [
    ("sp_search_ads", """(
            p_keyword  VARCHAR(100),
            p_category INTEGER,
            p_city     VARCHAR(100),
            p_min      NUMERIC(12, 2),
            p_max      NUMERIC(12, 2)
        )
        RETURNS (
            ad_id INTEGER, title VARCHAR(255), price NUMERIC(12, 2),
            city VARCHAR(100), category_name VARCHAR(100),
            created_at TIMESTAMP, image_url VARCHAR(500), seller_login VARCHAR(50)
        )
        AS
        BEGIN
            FOR SELECT a.id, a.title, a.price, a.city, c.name,
                       a.created_at, a.image_url, u.login
                FROM ads a
                JOIN categories c ON c.id = a.category_id
                JOIN users u ON u.id = a.user_id
                WHERE a.status = 'active'
                  AND (:p_keyword IS NULL
                       OR UPPER(a.title) LIKE UPPER('%' || :p_keyword || '%')
                       OR UPPER(a.description) LIKE UPPER('%' || :p_keyword || '%'))
                  AND (:p_category IS NULL OR a.category_id = :p_category)
                  AND (:p_city IS NULL OR UPPER(a.city) = UPPER(:p_city))
                  AND (:p_min IS NULL OR a.price >= :p_min)
                  AND (:p_max IS NULL OR a.price <= :p_max)
                ORDER BY a.created_at DESC
                INTO :ad_id, :title, :price, :city, :category_name,
                     :created_at, :image_url, :seller_login
            DO
                SUSPEND;
        END"""),
    ("sp_user_statistics", """(p_user_id INTEGER)
        RETURNS (
            ads_total INTEGER, ads_active INTEGER, ads_sold INTEGER,
            total_views INTEGER, favorites_made INTEGER, messages_received INTEGER
        )
        AS
        BEGIN
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN status = 'sold'   THEN 1 ELSE 0 END), 0),
                   COALESCE(SUM(views_count), 0)
              FROM ads WHERE user_id = :p_user_id
              INTO :ads_total, :ads_active, :ads_sold, :total_views;

            SELECT COUNT(*) FROM favorites WHERE user_id = :p_user_id
              INTO :favorites_made;

            SELECT COUNT(*) FROM messages WHERE receiver_id = :p_user_id
              INTO :messages_received;

            SUSPEND;
        END"""),
]

# Триггеры сопровождения
EXTRA_TRIGGERS = [
    ("tr_ads_bu", """
        CREATE TRIGGER tr_ads_bu FOR ads
        ACTIVE BEFORE UPDATE POSITION 1
        AS
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
        END
    """),
    ("tr_messages_bi_touch", """
        CREATE TRIGGER tr_messages_bi_touch FOR messages
        ACTIVE BEFORE INSERT POSITION 1
        AS
        BEGIN
            IF (NEW.created_at IS NULL) THEN
            BEGIN
                NEW.created_at = CURRENT_TIMESTAMP;
            END
        END
    """),
]


# ---------------------------------------------------------------------------
# Описание типов данных (для страницы «Структура базы данных»)
# ---------------------------------------------------------------------------

FIELD_TYPES = {
    7: "SMALLINT", 8: "INTEGER", 10: "FLOAT", 12: "DATE", 13: "TIME",
    14: "CHAR", 16: "BIGINT", 27: "DOUBLE PRECISION", 35: "TIMESTAMP",
    37: "VARCHAR", 261: "BLOB",
}


def describe_type(row):
    """Собирает читаемое имя типа данных по системному описанию столбца."""
    field_type = row.get("ftype")
    subtype = row.get("subtype")
    name = FIELD_TYPES.get(field_type, "ТИП_%s" % field_type)
    if field_type in (14, 37):
        return "%s(%s)" % (name, row.get("char_len") or row.get("flen"))
    if field_type == 16 and subtype in (1, 2):
        return "NUMERIC(%s,%s)" % (row.get("prec"), abs(row.get("fscale") or 0))
    return name


def table_columns(table_name):
    """Возвращает описание столбцов таблицы или представления."""
    rows = db.query_all(
        "SELECT f.rdb$field_name AS name, f.rdb$null_flag AS not_null, "
        "       t.rdb$field_type AS ftype, t.rdb$field_sub_type AS subtype, "
        "       t.rdb$character_length AS char_len, t.rdb$field_length AS flen, "
        "       t.rdb$field_precision AS prec, t.rdb$field_scale AS fscale "
        "FROM rdb$relation_fields f "
        "JOIN rdb$fields t ON t.rdb$field_name = f.rdb$field_source "
        "WHERE f.rdb$relation_name = ? "
        "ORDER BY f.rdb$field_position", [table_name.upper()])
    for row in rows:
        row["name"] = (row["name"] or "").strip()
        row["type"] = describe_type(row)
        row["not_null"] = bool(row["not_null"])
    return rows


# ---------------------------------------------------------------------------
# Основная процедура обновления схемы
# ---------------------------------------------------------------------------

def upgrade(verbose=True):
    """Приводит схему к целевому виду. Возвращает список выполненных действий."""
    log = []

    def say(text):
        log.append(text)
        if verbose:
            print("  " + text)

    if verbose:
        print("Обновление структуры базы данных...")

    # 1. Столбцы ------------------------------------------------------------
    for table, column, definition in COLUMNS:
        if not table_exists(table):
            say("! таблица %s отсутствует — пропуск" % table)
            continue
        if column_exists(table, column):
            continue
        db.ddl("ALTER TABLE %s ADD %s %s" % (table, column, definition))
        say("+ столбец %s.%s" % (table, column))

    # 2. Последовательности ------------------------------------------------
    for seq, table in SEQUENCES:
        if not sequence_exists(seq):
            db.ddl("CREATE SEQUENCE %s" % seq)
            say("+ последовательность %s" % seq)
        # Синхронизируем значение со максимальным существующим ключом
        max_id = db.query_value("SELECT MAX(id) FROM %s" % table, default=None)
        db.ddl("SET GENERATOR %s TO %d" % (seq, int(max_id or 0)))

    # 3. Триггеры автонумерации -------------------------------------------
    for name, table, seq in AUTO_ID_TRIGGERS:
        if not table_exists(table):
            continue
        db.ddl("""
            RECREATE TRIGGER %s FOR %s
            ACTIVE BEFORE INSERT POSITION 0
            AS
            BEGIN
                IF (NEW.id IS NULL) THEN
                BEGIN
                    NEW.id = GEN_ID(%s, 1);
                END
            END
        """ % (name, table, seq))
        say("~ триггер %s" % name)

    # 4. Триггеры сопровождения -------------------------------------------
    for name, ddl_text in EXTRA_TRIGGERS:
        db.ddl(ddl_text.replace("CREATE TRIGGER", "RECREATE TRIGGER", 1))
        say("~ триггер %s" % name)

    # 5. Индексы -----------------------------------------------------------
    for name, table, columns in INDEXES:
        if not table_exists(table):
            continue
        if index_exists(name):
            continue
        db.ddl("CREATE INDEX %s ON %s (%s)" % (name, table, columns))
        say("+ индекс %s" % name)

    # 6. Ограничения CHECK -------------------------------------------------
    for name, table, condition, _comment in CHECKS:
        if not table_exists(table):
            continue
        if constraint_exists(name):
            continue
        db.ddl("ALTER TABLE %s ADD CONSTRAINT %s CHECK (%s)"
               % (table, name, condition))
        say("+ ограничение %s" % name)

    # 7. Представления -----------------------------------------------------
    for name, body in VIEWS:
        db.ddl("RECREATE VIEW %s %s" % (name, body))
        say("~ представление %s" % name)

    # 8. Хранимые процедуры ------------------------------------------------
    for name, body in PROCEDURES:
        db.ddl("RECREATE PROCEDURE %s %s" % (name, body))
        say("~ процедура %s" % name)

    # 9. Заполнение новых столбцов значениями по умолчанию -----------------
    db.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP "
               "WHERE created_at IS NULL")
    db.execute("UPDATE users SET is_blocked = 0 WHERE is_blocked IS NULL")
    db.execute("UPDATE ads SET created_at = CURRENT_TIMESTAMP "
               "WHERE created_at IS NULL")
    db.execute("UPDATE ads SET status = 'active' WHERE status IS NULL")
    db.execute("UPDATE ads SET views_count = 0 WHERE views_count IS NULL")
    db.execute("UPDATE messages SET is_read = 0 WHERE is_read IS NULL")
    db.execute("UPDATE favorites SET created_at = CURRENT_TIMESTAMP "
               "WHERE created_at IS NULL")
    db.execute("UPDATE categories SET icon = '📦' WHERE icon IS NULL")

    if verbose:
        print("Готово. Изменений: %d" % len(log))
    return log


def reset_sequences():
    """Синхронизирует последовательности с фактическими максимальными ключами."""
    for seq, table in SEQUENCES:
        max_id = db.query_value("SELECT MAX(id) FROM %s" % table, default=None)
        db.ddl("SET GENERATOR %s TO %d" % (seq, int(max_id or 0)))


def schema_report():
    """Возвращает словарь с описанием текущей структуры (для отчёта и админки)."""
    tables = [r["rdb$relation_name"].strip()
              for r in db.query_all(
                  "select rdb$relation_name from rdb$relations "
                  "where rdb$system_flag = 0 and rdb$view_blr is null "
                  "order by rdb$relation_name")]
    views = [r["rdb$relation_name"].strip()
             for r in db.query_all(
                 "select rdb$relation_name from rdb$relations "
                 "where rdb$system_flag = 0 and rdb$view_blr is not null "
                 "order by rdb$relation_name")]
    procs = [r["rdb$procedure_name"].strip()
             for r in db.query_all(
                 "select rdb$procedure_name from rdb$procedures "
                 "where rdb$system_flag = 0 order by 1")]
    triggers = [r["rdb$trigger_name"].strip()
                for r in db.query_all(
                    "select rdb$trigger_name from rdb$triggers "
                    "where rdb$system_flag = 0 order by 1")]
    return {"tables": tables, "views": views,
            "procedures": procs, "triggers": triggers}


if __name__ == "__main__":
    ok, err = db.ping(retries=1)
    if not ok:
        print("Не удалось подключиться к базе данных %s" % config.DATABASE_DSN)
        print(err)
        raise SystemExit(1)
    upgrade()
    print()
    print("Структура базы данных:")
    for kind, items in schema_report().items():
        print("  %-12s: %s" % (kind, ", ".join(items)))
