import fdb
import os
import shutil
import argparse

DB_DIR  = "/opt/avito_db"
DB_NAME = "AVITO.DB"
DB_PATH = os.path.join(DB_DIR, DB_NAME)

HOST     = "localhost"
USER     = "sysdba"
PASSWORD = "masterkey"


def drop_database(remove_dir: bool = False):
    if not os.path.exists(DB_PATH):
        print(f"Файл {DB_PATH} не найден.")
        if remove_dir and os.path.exists(DB_DIR):
            shutil.rmtree(DB_DIR)
            print(f"Папка {DB_DIR} удалена.")
        return

    # 1. Сначала — через Firebird (корректно отключит всех клиентов)
    try:
        conn = fdb.connect(
            database=f"{HOST}:{DB_PATH}",
            user=USER, password=PASSWORD, charset="UTF8",
        )
        conn.drop_database()
        print(f"База удалена через drop_database(): {DB_PATH}")
    except fdb.DatabaseError as e:
        print(f"drop_database() не сработал ({e}), удаляем файл напрямую...")
        try:
            os.remove(DB_PATH)
            print(f"Файл {DB_PATH} удалён.")
        except PermissionError as e2:
            print(f"Нет прав на удаление: {e2}")
            print("Проверьте: groups | grep firebird")
            return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Удаление базы AVITO")
    parser.add_argument("--dir", action="store_true",
                        help="Удалить также папку с базой")
    args = parser.parse_args()
    drop_database(remove_dir=args.dir)