"""Добавляет BLOB-поля фотографий в существующую базу, не удаляя данные."""
import fdb
from db_functions import DB_PATH, HOST, USER, PASSWORD, CHARSET


def column_exists(cursor, column_name):
    cursor.execute(
        """SELECT 1 FROM RDB$RELATION_FIELDS
           WHERE RDB$RELATION_NAME = 'ADS' AND RDB$FIELD_NAME = ?""",
        (column_name.upper(),)
    )
    return cursor.fetchone() is not None


def migrate():
    connection = fdb.connect(
        dsn=f"{HOST}:{DB_PATH}", user=USER, password=PASSWORD, charset=CHARSET
    )
    cursor = connection.cursor()
    try:
        if not column_exists(cursor, "IMAGE"):
            cursor.execute("ALTER TABLE ads ADD image BLOB SUB_TYPE BINARY")
            print("Добавлено поле ADS.IMAGE типа BLOB.")
        else:
            print("Поле ADS.IMAGE уже существует.")

        if not column_exists(cursor, "IMAGE_TYPE"):
            cursor.execute("ALTER TABLE ads ADD image_type VARCHAR(100)")
            print("Добавлено поле ADS.IMAGE_TYPE.")
        else:
            print("Поле ADS.IMAGE_TYPE уже существует.")

        connection.commit()
        print("Миграция завершена. Старые данные и IMAGE_URL сохранены.")
        print("Старые URL автоматически не превращаются в BLOB-файлы.")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    migrate()
