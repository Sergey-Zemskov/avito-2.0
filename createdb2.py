import fdb
import os
import sys
import shutil
import argparse

# ============================================================
#  ПУТЬ (ТОТ ЖЕ, ЧТО В db_functions.py И create_database.py)
# ============================================================
DB_DIR  = "/opt/avito_db"
DB_NAME = "AVITO.DB"
DB_PATH = os.path.join(DB_DIR, DB_NAME)

HOST     = "localhost"
USER     = "sysdba"
PASSWORD = "masterkey"
# ============================================================


def drop_database(remove_dir: bool = False):
    if not os.path.exists(DB_PATH):
        print(f"Файла {DB_PATH} нет — удалять нечего.")
    else:
        # 1) Пробуем корректный drop через Firebird
        conn = None
        try:
            conn = fdb.connect(
                dsn=f"{HOST}:{DB_PATH}",
                user=USER,
                password=PASSWORD,
                charset="UTF8",
            )
            # drop_database сам закрывает соединение на стороне сервера,
            # поэтому conn.close() после него вызывать НЕЛЬЗЯ.
            conn.drop_database()
            conn = None  # соединение уже недействительно
            print(f"База удалена через Firebird: {DB_PATH}")
        except fdb.DatabaseError as e:
            print(f"Firebird drop не удался: {e}")
        except Exception as e:
            print(f"Ошибка при подключении: {e}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        # 2) Если файл всё ещё существует — удаляем напрямую
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
                print(f"Файл удалён напрямую: {DB_PATH}")
            except PermissionError as e:
                print(f"Нет прав на удаление: {e}")
                print("Выполните:")
                print(f"  sudo -u firebird rm -f {DB_PATH}")
                sys.exit(1)
            except Exception as e:
                print(f"Не удалось удалить файл: {e}")
                sys.exit(1)

    # 3) При желании — снести и сам каталог
    if remove_dir and os.path.exists(DB_DIR):
        try:
            shutil.rmtree(DB_DIR)
            print(f"Каталог удалён: {DB_DIR}")
        except PermissionError:
            print(f"Нет прав на удаление каталога {DB_DIR}.")
            print(f"  sudo rm -rf {DB_DIR}")
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Удаление базы AVITO")
    parser.add_argument("--dir", action="store_true",
                        help="Удалить также каталог /opt/avito_db")
    args = parser.parse_args()
    drop_database(remove_dir=args.dir)