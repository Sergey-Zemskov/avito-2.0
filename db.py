# -*- coding: utf-8 -*-
"""
Слой доступа к базе данных Firebird (RedDatabase).

Модуль решает три задачи:
  1) держит пул соединений, чтобы не открывать новое подключение на каждый запрос;
  2) предоставляет удобные обёртки над курсором (query_all / query_one / execute);
  3) аккуратно работает с транзакциями: commit при изменении данных,
     rollback при любой ошибке.

Использование:

    from db import query_all, query_one, execute

    rows = query_all("select id, title from ads where city = ?", ["Москва"])
    new_id = execute("insert into ads (title) values (?) returning id",
                     ["Заголовок"], returning=True)
"""

import queue
import threading
import time

import fdb

import config

# Пул свободных соединений. Соединения Firebird не потокобезопасны,
# поэтому каждое соединение в каждый момент времени используется одним потоком.
_pool = queue.Queue(maxsize=config.DB_POOL_SIZE)
_pool_lock = threading.Lock()
_created = 0

# Ошибки, после которых соединение считается испорченным и закрывается
_FATAL = (fdb.OperationalError, fdb.InterfaceError, fdb.InternalError)


class DatabaseError(Exception):
    """Ошибка уровня базы данных, пригодная для показа пользователю."""


def _open_connection():
    """Открывает новое соединение с базой данных."""
    return fdb.connect(
        host=config.DB_HOST,
        database=config.DB_PATH,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset=config.DB_CHARSET,
    )


def _acquire():
    """Берёт соединение из пула или создаёт новое."""
    global _created
    try:
        conn = _pool.get_nowait()
    except queue.Empty:
        with _pool_lock:
            if _created < config.DB_POOL_SIZE:
                _created += 1
                return _open_connection()
        # Пул исчерпан — ждём освобождения соединения
        conn = _pool.get(timeout=15)

    # Проверяем, что соединение живо (сервер мог перезапуститься)
    try:
        probe = conn.cursor()
        probe.execute("select 1 from rdb$database")
        probe.fetchall()
        probe.close()
        return conn
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return _open_connection()


def _release(conn, broken=False):
    """Возвращает соединение в пул либо закрывает его."""
    global _created
    if conn is None:
        return
    if broken:
        try:
            conn.close()
        except Exception:
            pass
        with _pool_lock:
            _created = max(0, _created - 1)
        return
    try:
        _pool.put_nowait(conn)
    except queue.Full:
        try:
            conn.close()
        except Exception:
            pass
        with _pool_lock:
            _created = max(0, _created - 1)


def _rows_to_dicts(cursor, rows):
    """Преобразует кортежи в словари с именами столбцов в нижнем регистре."""
    if cursor.description is None:
        return []
    names = [d[0].lower() for d in cursor.description]
    return [dict(zip(names, row)) for row in rows]


def _run(sql, params=None, only_one=False):
    """
    Внутренняя функция выполнения запроса.

    Возвращает список словарей (может быть пустым для INSERT/UPDATE/DELETE).
    """
    conn = _acquire()
    broken = False
    try:
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            rows = []
            if cursor.description is not None:
                fetched = cursor.fetchall()
                if only_one:
                    fetched = fetched[:1]
                rows = _rows_to_dicts(cursor, fetched)
            conn.commit()
            return rows
        except Exception:
            conn.rollback()
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass
    except fdb.Error as exc:
        broken = isinstance(exc, _FATAL)
        raise DatabaseError(_humanize(exc))
    except DatabaseError:
        raise
    except Exception as exc:                       # сетевые и прочие сбои
        broken = True
        raise DatabaseError(str(exc))
    finally:
        _release(conn, broken=broken)


def query_all(sql, params=None):
    """Выполняет SELECT и возвращает список словарей."""
    return _run(sql, params)


def query_one(sql, params=None):
    """Выполняет SELECT и возвращает первую строку в виде словаря или None."""
    rows = _run(sql, params, only_one=True)
    return rows[0] if rows else None


def query_value(sql, params=None, default=None):
    """Возвращает единственное значение первого столбца первой строки."""
    row = query_one(sql, params)
    if not row:
        return default
    return list(row.values())[0]


def execute(sql, params=None, returning=False):
    """
    Выполняет INSERT/UPDATE/DELETE и фиксирует транзакцию.

    Если returning=True, возвращает значение из конструкции RETURNING
    (например, сгенерированный первичный ключ).
    """
    rows = _run(sql, params, only_one=True)
    if returning:
        if not rows:
            return None
        return list(rows[0].values())[0]
    return None


def ddl(statement):
    """Выполняет одну DDL-команду (CREATE / ALTER / DROP) и фиксирует её."""
    return _run(statement)


def _humanize(exc):
    """Превращает техническое сообщение Firebird в понятную фразу."""
    text = str(exc)
    mapping = (
        ("violation of PRIMARY or UNIQUE KEY constraint",
         "Запись с таким значением уже существует."),
        ("violation of FOREIGN KEY constraint",
         "Нарушена ссылочная целостность: запись используется в другой таблице."),
        ("violation of CHECK constraint",
         "Значение не проходит проверку ограничения целостности."),
        ("arithmetic exception, numeric overflow, or string truncation",
         "Слишком длинное значение или переполнение числового поля."),
        ("attempted update on read-only transaction",
         "Транзакция доступна только для чтения."),
    )
    for key, human in mapping:
        if key in text:
            return human
    return text


# --- Служебные функции ------------------------------------------------------

def ping(retries=5, delay=1.0):
    """Проверяет доступность БД. Возвращает (True, None) либо (False, текст ошибки)."""
    last = None
    for _ in range(retries):
        try:
            query_value("select 1 from rdb$database")
            return True, None
        except DatabaseError as exc:
            last = str(exc)
            time.sleep(delay)
    return False, last


def close_pool():
    """Закрывает все соединения пула (используется при остановке приложения)."""
    while True:
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            break
        try:
            conn.close()
        except Exception:
            pass
