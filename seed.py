# -*- coding: utf-8 -*-
"""
Заполнение базы данных демонстрационными данными.

Запуск:
    python seed.py            добавить данные, если база пустая
    python seed.py --reset    удалить все данные и заполнить заново
"""

import os
import random
import sys
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

import config
import db

random.seed(2026)

CITIES = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск",
          "Екатеринбург", "Нижний Новгород", "Самара", "Краснодар"]

# логин, пароль, роль
USERS = [
    ("admin", "admin", "admin"),
    ("ivan", "12345", "user"),
    ("anna", "12345", "user"),
    ("petr", "12345", "user"),
]

CATEGORIES = [
    ("Транспорт", "Автомобили, мотоциклы, запчасти"),
    ("Недвижимость", "Квартиры, дома, комнаты, гаражи"),
    ("Электроника", "Телефоны, ноутбуки, телевизоры, аудио"),
    ("Бытовая техника", "Холодильники, стиральные машины, пылесосы"),
    ("Одежда и обувь", "Мужская, женская и детская одежда"),
    ("Мебель", "Шкафы, диваны, столы, стулья"),
    ("Работа", "Вакансии и резюме"),
    ("Услуги", "Ремонт, обучение, красота, транспорт"),
    ("Детское", "Игрушки, коляски, детская одежда"),
    ("Спорт и отдых", "Тренажёры, велосипеды, туризм"),
]

# категория, название, цена, город, описание
ADS = [
    ("Транспорт", "Lada Vesta 2019, 1.6 МТ", 875000, "Москва",
     "Автомобиль в отличном состоянии, один владелец по ПТС. Пробег 64 000 км."),
    ("Транспорт", "Kia Rio 2017, 1.6 АТ", 1090000, "Санкт-Петербург",
     "Комплектация Prestige, кожаный салон, камера заднего вида."),
    ("Транспорт", "Комплект зимних шин R16", 24000, "Казань",
     "Шины Nokian Hakkapeliitta, остаток протектора 8 мм."),
    ("Недвижимость", "2-комнатная квартира, 62 кв.м", 8900000, "Новосибирск",
     "Свободная планировка, панорамные окна, рядом метро и парк."),
    ("Недвижимость", "Сдам студию 28 кв.м", 32000, "Екатеринбург",
     "Свежий ремонт, встроенная кухня, стиральная машина, интернет."),
    ("Недвижимость", "Гараж 24 кв.м в кооперативе", 450000, "Самара",
     "Капитальный гараж, сухой погреб, электричество, охрана."),
    ("Электроника", "Ноутбук ASUS VivoBook 15, i5, 16 ГБ", 62000, "Москва",
     "Процессор Intel Core i5, SSD 512 ГБ, экран 15.6 дюйма FullHD."),
    ("Электроника", "iPhone 13 128 ГБ, Midnight", 54000, "Санкт-Петербург",
     "Состояние идеальное, ёмкость аккумулятора 91 процент."),
    ("Электроника", "Телевизор LG 55 дюймов 4K", 47000, "Казань",
     "4K UHD, webOS, пульт-указка. Битых пикселей нет."),
    ("Электроника", "Наушники Sony WH-1000XM4", 21000, "Нижний Новгород",
     "Активное шумоподавление, оригинальный чехол и кабель."),
    ("Бытовая техника", "Стиральная машина Bosch Serie 6", 34000, "Москва",
     "Загрузка 8 кг, 1400 оборотов, инверторный двигатель."),
    ("Бытовая техника", "Холодильник Liebherr, 340 л", 56000, "Краснодар",
     "Две камеры, система NoFrost, класс энергопотребления A++."),
    ("Бытовая техника", "Робот-пылесос Xiaomi Mi Robot", 18500, "Казань",
     "Влажная и сухая уборка, управление со смартфона."),
    ("Одежда и обувь", "Пуховик мужской, размер 50", 8900, "Новосибирск",
     "Натуральный пух, до минус 30 градусов, носился один сезон."),
    ("Одежда и обувь", "Кроссовки Nike Air Max 90, 42 размер", 7400, "Москва",
     "Оригинал, состояние новых, коробка в комплекте."),
    ("Мебель", "Угловой диван-кровать, 260x160 см", 39000, "Екатеринбург",
     "Ткань антивандальная, механизм еврокнижка, ящик для белья."),
    ("Мебель", "Кухонный гарнитур 3,2 м", 72000, "Самара",
     "Фасады МДФ, столешница из искусственного камня, фурнитура Blum."),
    ("Мебель", "Стол письменный из дуба, 140x70 см", 15500, "Москва",
     "Массив дуба, покрытие лаком, два выдвижных ящика."),
    ("Работа", "Требуется курьер на личном автомобиле", 70000, "Москва",
     "Доставка документов по городу, гибкий график, оплата два раза в месяц."),
    ("Работа", "Вакансия: frontend-разработчик (React)", 180000, "Санкт-Петербург",
     "Удалённая работа, гибкое начало дня, ДМС после испытательного срока."),
    ("Услуги", "Ремонт квартир под ключ", 250000, "Казань",
     "Демонтаж, электрика, сантехника, отделка. Гарантия на работы 2 года."),
    ("Услуги", "Репетитор по математике, 9-11 класс", 1200, "Нижний Новгород",
     "Подготовка к ОГЭ и ЕГЭ, средний балл учеников 82."),
    ("Услуги", "Грузоперевозки: газель, 3 тонны", 3500, "Екатеринбург",
     "Работаем по городу и области, есть грузчики, оплата почасовая."),
    ("Детское", "Коляска-трансформер 2 в 1", 17500, "Краснодар",
     "Прогулочный блок и люлька, дождевик, сумка для мамы."),
    ("Детское", "Конструктор LEGO Duplo, 120 деталей", 4200, "Москва",
     "Полный комплект, все детали на месте, инструкция сохранена."),
    ("Спорт и отдых", "Велотренажёр магнитный", 13500, "Самара",
     "Регулировка нагрузки, пульсометр, дисплей. Складывается."),
    ("Спорт и отдых", "Горный велосипед Merida, 27,5 дюйма", 43000, "Новосибирск",
     "21 скорость, гидравлические тормоза, обслужен в веломастерской."),
    ("Спорт и отдых", "Палатка 4-местная", 9800, "Казань",
     "Дуговой каркас, два входа, тамбур, вес 5,4 кг."),
]

MESSAGES = [
    (0, 1, "Здравствуйте! Ноутбук ещё продаётся?"),
    (1, 0, "Добрый день! Да, в продаже."),
    (0, 1, "А торг возможен?"),
    (1, 0, "Небольшой, в пределах пяти тысяч."),
    (2, 0, "Добрый день! Автомобиль не битый?"),
    (0, 2, "Здравствуйте! Не битый, есть отчёт."),
]


def make_image(path, title):
    """Рисует простую картинку с названием товара (нужна библиотека Pillow)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    image = Image.new("RGB", (640, 480), (230, 230, 230))
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, 630, 470], outline=(0, 0, 0), width=2)

    font = None
    for name in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        if os.path.isfile(name):
            font = ImageFont.truetype(name, 28)
            break

    if font is not None:
        words = title.split()
        lines = []
        line = ""
        for word in words:
            probe = (line + " " + word).strip()
            if draw.textlength(probe, font=font) > 580:
                lines.append(line)
                line = word
            else:
                line = probe
        if line:
            lines.append(line)

        y = 200
        for text in lines[:5]:
            draw.text((40, y), text, font=font, fill=(0, 0, 0))
            y = y + 38

    image.save(path, "JPEG")
    return True


def add_users():
    """Создаёт пользователей. Возвращает словарь логин -> id."""
    result = {}
    for login, password, role in USERS:
        user = db.query_one("select id from users where login = ?", [login])
        if user is None:
            user_id = db.execute(
                "insert into users (login, password_hash, role) "
                "values (?, ?, ?) returning id",
                [login, generate_password_hash(password), role],
                returning=True)
            print("  добавлен пользователь", login)
        else:
            user_id = user["id"]
        result[login] = user_id
    return result


def add_categories():
    """Создаёт категории. Возвращает словарь название -> id."""
    result = {}
    for name, description in CATEGORIES:
        row = db.query_one("select id from categories where name = ?", [name])
        if row is None:
            category_id = db.execute(
                "insert into categories (name, description) "
                "values (?, ?) returning id", [name, description],
                returning=True)
            print("  добавлена категория", name)
        else:
            category_id = row["id"]
        result[name] = category_id
    return result


def add_ads(users, categories):
    """Добавляет объявления, если таблица ads пустая."""
    count = db.query_value("select count(*) from ads", default=0)
    if count > 0:
        print("  объявления уже есть (%d штук), пропускаем" % count)
        return

    folder = os.path.join(config.UPLOAD_DIR, "demo")
    if not os.path.isdir(folder):
        os.makedirs(folder)

    logins = ["ivan", "anna", "petr"]
    now = datetime.now()

    for number, (category, title, price, city, description) in enumerate(ADS, 1):
        file_name = "demo_%02d.jpg" % number
        full_name = os.path.join(folder, file_name)
        if not os.path.isfile(full_name):
            make_image(full_name, title)

        db.execute(
            "insert into ads (user_id, category_id, title, description, "
            "                 price, city, image_url, created_at) "
            "values (?, ?, ?, ?, ?, ?, ?, ?)",
            [users[random.choice(logins)], categories[category], title,
             description, price, city, "uploads/demo/" + file_name,
             now - timedelta(days=random.randint(0, 30))])

    print("  добавлено объявлений: %d" % len(ADS))


def add_favorites(users):
    count = db.query_value("select count(*) from favorites", default=0)
    if count > 0:
        print("  избранное уже заполнено")
        return

    ad_ids = [row["id"] for row in db.query_all("select id from ads")]
    if not ad_ids:
        return

    total = 0
    for login in ("ivan", "anna", "petr"):
        for ad_id in random.sample(ad_ids, min(5, len(ad_ids))):
            try:
                db.execute("insert into favorites (user_id, ad_id) "
                           "values (?, ?)", [users[login], ad_id])
                total = total + 1
            except db.DatabaseError:
                pass
    print("  добавлено записей в избранное: %d" % total)


def add_messages(users):
    count = db.query_value("select count(*) from messages", default=0)
    if count > 0:
        print("  сообщения уже есть")
        return

    order = [users["ivan"], users["anna"], users["petr"]]
    sent = 0
    for sender_index, receiver_index, text in MESSAGES:
        sender = order[sender_index]
        receiver = order[receiver_index]
        db.execute(
            "insert into messages (sender_id, receiver_id, message_text) "
            "values (?, ?, ?)", [sender, receiver, text])
        sent = sent + 1
    print("  добавлено сообщений: %d" % sent)


def reset_data():
    """Удаляет все данные из таблиц."""
    print("Удаление старых данных...")
    for table in ("messages", "favorites", "ads", "categories", "users"):
        db.execute("delete from " + table)
    print("  таблицы очищены")


def main():
    if "--reset" in sys.argv:
        answer = input("Все данные будут удалены. Продолжить? (y/N): ")
        if answer.strip().lower() not in ("y", "yes", "д", "да"):
            print("Отменено.")
            return
        reset_data()

    ok, error = db.ping(retries=1)
    if not ok:
        print("Нет связи с базой данных:", error)
        return

    print("Заполнение базы демонстрационными данными...")
    users = add_users()
    categories = add_categories()
    add_ads(users, categories)
    add_favorites(users)
    add_messages(users)

    print()
    print("Готово. Логины для входа:")
    for login, password, role in USERS:
        print("  %-6s / %-8s (%s)" % (login, password, role))


if __name__ == "__main__":
    main()
