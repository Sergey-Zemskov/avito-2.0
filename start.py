# -*- coding: utf-8 -*-
"""
Запуск сайта объявлений "Авито" одной командой.

Этот файл запускают скрипты start.bat (Windows) и start.sh (Linux).
Он сам делает всю подготовку:
    1) проверяет, установлены ли нужные библиотеки, и при необходимости ставит их;
    2) проверяет, работает ли сервер Firebird;
    3) создаёт базу данных и наполняет её демонстрационными данными;
    4) открывает браузер и запускает сайт.

Отдельно запускать этот файл не нужно - просто используйте start.bat
или start.sh.
"""

import os
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser

# Чтобы русский текст правильно выводился в консоль Windows
if os.name == "nt":
    os.system("chcp 65001 >nul")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

URL = "http://127.0.0.1:5000"
PACKAGES = ("flask", "fdb")


def say(text=""):
    print(text)


def check_python():
    """Проверяет версию Python."""
    if sys.version_info < (3, 6):
        say("Нужен Python 3.6 или новее, а у вас %s." % sys.version.split()[0])
        return False
    return True


def packages_ok():
    """Установлены ли нужные библиотеки."""
    for name in PACKAGES:
        try:
            __import__(name)
        except ImportError:
            return False
    return True


def install_packages():
    """Ставит библиотеки. Если не получилось - создаёт виртуальное окружение."""
    say("Устанавливаю нужные библиотеки, подождите...")
    subprocess.call([sys.executable, "-m", "pip", "install", "--quiet",
                     "--disable-pip-version-check", "-r", "requirements.txt"])
    if packages_ok():
        return True

    say("Ставлю библиотеки в отдельную папку .venv ...")
    venv_dir = os.path.join(BASE_DIR, ".venv")
    subprocess.call([sys.executable, "-m", "venv", venv_dir])

    if os.name == "nt":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    if not os.path.isfile(venv_python):
        return False

    subprocess.call([venv_python, "-m", "pip", "install", "--quiet",
                     "-r", "requirements.txt"])

    # Перезапускаемся уже внутри виртуального окружения
    os.execv(venv_python, [venv_python, os.path.abspath(__file__)])
    return False


def firebird_running():
    """Отвечает ли сервер Firebird на порту 3050."""
    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect(("127.0.0.1", 3050))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def try_install_firebird():
    """На Linux предлагает установить Firebird через dnf."""
    if os.name == "nt":
        return
    if shutil.which("dnf") is None:
        return
    try:
        answer = input("Установить и запустить Firebird сейчас? (y/n): ")
    except EOFError:
        return
    if answer.strip().lower() not in ("y", "yes", "д", "да"):
        return

    say()
    say("Устанавливаю Firebird...")
    for packages in (["firebird", "firebird-utils"], ["firebird-superserver"],
                     ["firebird"]):
        if subprocess.call(["sudo", "dnf", "install", "-y"] + packages) == 0:
            break

    for service in ("firebird", "firebird-superserver", "firebird-classic"):
        if subprocess.call(["sudo", "systemctl", "enable", "--now", service]) == 0:
            break
    say("Проверяю ещё раз...")
    import time
    time.sleep(3)


def open_browser():
    """Открывает сайт в браузере по умолчанию."""
    try:
        if webbrowser.open(URL):
            return
    except Exception:
        pass
    if os.name == "nt":
        try:
            os.startfile(URL)
        except Exception:
            pass


def main():
    say("=" * 60)
    say("   Сайт объявлений «Авито» - курсовая работа")
    say("=" * 60)
    say()

    if not check_python():
        return 1

    if not packages_ok():
        install_packages()
    if not packages_ok():
        say()
        say("Не удалось установить библиотеки.")
        say("Попробуйте выполнить вручную:")
        say("    %s -m pip install -r requirements.txt" % sys.executable)
        return 1
    say("Библиотеки на месте.")

    if not firebird_running():
        say()
        say("Сервер Firebird не отвечает (порт 3050 закрыт).")
        import config
        say(config.firebird_help())
        try_install_firebird()
        if not firebird_running():
            say()
            say("Без сервера Firebird сайт работать не сможет.")
            return 1

    say("Сервер Firebird отвечает.")
    say()

    if subprocess.call([sys.executable, "setup_all.py", "--demo"]) != 0:
        say()
        say("Сайт не запущен: сначала нужно наладить базу данных.")
        return 1

    say()
    say("Открываю браузер: %s" % URL)
    say("Чтобы остановить сайт, нажмите Ctrl+C.")
    say()

    timer = threading.Timer(3, open_browser)
    timer.daemon = True
    timer.start()

    import runpy
    runpy.run_path("app.py", run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
