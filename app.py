# -*- coding: utf-8 -*-
"""
Сайт объявлений "Авито" - курсовая работа по базам данных.

База данных: Firebird (таблицы users, categories, ads, favorites, messages).
Сайт написан на Flask.

Запуск:  python app.py
Открыть: http://127.0.0.1:5000
"""

import os
import uuid

from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def current_user():
    """Возвращает данные вошедшего пользователя или None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.query_one("select id, login, role from users where id = ?",
                        [user_id])


def all_categories():
    """Список категорий для выпадающего списка."""
    return db.query_all("select id, name from categories order by name")


@app.context_processor
def add_user():
    """Чтобы переменная user была доступна во всех шаблонах."""
    return {"user": current_user()}


@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", text="Страница не найдена"), 404


# ---------------------------------------------------------------------------
# Главная страница со списком объявлений
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", type=int)

    sql = ("select a.id, a.title, a.price, a.city, a.image_url, "
           "       c.name as category_name, u.login as seller "
           "from ads a "
           "join categories c on c.id = a.category_id "
           "join users u on u.id = a.user_id")

    usloviya = []
    parametry = []
    if q:
        usloviya.append("upper(a.title) like upper(?)")
        parametry.append("%" + q + "%")
    if category:
        usloviya.append("a.category_id = ?")
        parametry.append(category)
    if usloviya:
        sql = sql + " where " + " and ".join(usloviya)
    sql = sql + " order by a.id desc"

    ads = db.query_all(sql, parametry)
    return render_template("index.html", ads=ads, categories=all_categories(),
                           q=q, category=category)


# ---------------------------------------------------------------------------
# Просмотр одного объявления
# ---------------------------------------------------------------------------

@app.route("/ad/<int:ad_id>")
def ad_view(ad_id):
    ad = db.query_one(
        "select a.id, a.title, a.description, a.price, a.city, a.image_url, "
        "       a.user_id, a.category_id, c.name as category_name, "
        "       u.login as seller "
        "from ads a "
        "join categories c on c.id = a.category_id "
        "join users u on u.id = a.user_id "
        "where a.id = ?", [ad_id])

    if ad is None:
        return render_template("error.html",
                               text="Объявление не найдено"), 404

    v_izbrannom = False
    if session.get("user_id"):
        v_izbrannom = db.query_value(
            "select count(*) from favorites where user_id = ? and ad_id = ?",
            [session["user_id"], ad_id], 0) > 0

    return render_template("ad.html", ad=ad, favorite=v_izbrannom)


# ---------------------------------------------------------------------------
# Добавление объявления
# ---------------------------------------------------------------------------

@app.route("/add", methods=["GET", "POST"])
def ad_add():
    if not session.get("user_id"):
        flash("Сначала войдите на сайт")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        city = request.form.get("city", "").strip()
        category_id = request.form.get("category_id", type=int)

        # цена должна быть числом
        try:
            price = float(price.replace(",", "."))
        except ValueError:
            price = None

        # загрузка фотографии
        image_url = ""
        file = request.files.get("photo")
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in config.ALLOWED_EXTENSIONS:
                config.make_upload_dir()
                name = uuid.uuid4().hex + ext
                file.save(os.path.join(config.UPLOAD_DIR, name))
                image_url = "uploads/" + name
            else:
                flash("Такой формат фотографии не поддерживается")

        if not title or price is None or not city or not category_id:
            flash("Заполните все обязательные поля")
            return redirect(url_for("ad_add"))

        db.execute(
            "insert into ads (user_id, category_id, title, description, "
            "                 price, city, image_url) "
            "values (?, ?, ?, ?, ?, ?, ?)",
            [session["user_id"], category_id, title, description,
             price, city, image_url])

        flash("Объявление добавлено")
        return redirect(url_for("index"))

    return render_template("form.html", ad=None,
                           categories=all_categories())


# ---------------------------------------------------------------------------
# Редактирование объявления
# ---------------------------------------------------------------------------

@app.route("/edit/<int:ad_id>", methods=["GET", "POST"])
def ad_edit(ad_id):
    if not session.get("user_id"):
        flash("Сначала войдите на сайт")
        return redirect(url_for("login"))

    ad = db.query_one("select * from ads where id = ?", [ad_id])
    if ad is None:
        return render_template("error.html",
                               text="Объявление не найдено"), 404
    if ad["user_id"] != session["user_id"]:
        return render_template("error.html",
                               text="Это не ваше объявление"), 403

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        city = request.form.get("city", "").strip()
        category_id = request.form.get("category_id", type=int)

        try:
            price = float(price.replace(",", "."))
        except ValueError:
            price = None

        image_url = ad["image_url"]
        file = request.files.get("photo")
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in config.ALLOWED_EXTENSIONS:
                config.make_upload_dir()
                name = uuid.uuid4().hex + ext
                file.save(os.path.join(config.UPLOAD_DIR, name))
                image_url = "uploads/" + name
            else:
                flash("Такой формат фотографии не поддерживается")

        if not title or price is None or not city or not category_id:
            flash("Заполните все обязательные поля")
            return redirect(url_for("ad_edit", ad_id=ad_id))

        db.execute(
            "update ads set category_id = ?, title = ?, description = ?, "
            "       price = ?, city = ?, image_url = ? "
            "where id = ?",
            [category_id, title, description, price, city, image_url, ad_id])

        flash("Изменения сохранены")
        return redirect(url_for("ad_view", ad_id=ad_id))

    return render_template("form.html", ad=ad, categories=all_categories())


# ---------------------------------------------------------------------------
# Удаление объявления
# ---------------------------------------------------------------------------

@app.route("/delete/<int:ad_id>")
def ad_delete(ad_id):
    if not session.get("user_id"):
        flash("Сначала войдите на сайт")
        return redirect(url_for("login"))

    ad = db.query_one("select user_id from ads where id = ?", [ad_id])
    if ad is None:
        return render_template("error.html",
                               text="Объявление не найдено"), 404
    if ad["user_id"] != session["user_id"]:
        return render_template("error.html",
                               text="Это не ваше объявление"), 403

    db.execute("delete from ads where id = ?", [ad_id])
    flash("Объявление удалено")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Избранное
# ---------------------------------------------------------------------------

@app.route("/favorites")
def favorites():
    if not session.get("user_id"):
        flash("Сначала войдите на сайт")
        return redirect(url_for("login"))

    ads = db.query_all(
        "select a.id, a.title, a.price, a.city "
        "from favorites f "
        "join ads a on a.id = f.ad_id "
        "where f.user_id = ? "
        "order by a.id desc", [session["user_id"]])

    return render_template("favorites.html", ads=ads)


@app.route("/favorite/<int:ad_id>")
def favorite(ad_id):
    if not session.get("user_id"):
        flash("Сначала войдите на сайт")
        return redirect(url_for("login"))

    est = db.query_value(
        "select count(*) from favorites where user_id = ? and ad_id = ?",
        [session["user_id"], ad_id], 0)

    if est > 0:
        db.execute("delete from favorites where user_id = ? and ad_id = ?",
                   [session["user_id"], ad_id])
        flash("Удалено из избранного")
    else:
        db.execute("insert into favorites (user_id, ad_id) values (?, ?)",
                   [session["user_id"], ad_id])
        flash("Добавлено в избранное")

    return redirect(url_for("ad_view", ad_id=ad_id))


# ---------------------------------------------------------------------------
# Сообщения
# ---------------------------------------------------------------------------

@app.route("/messages")
def messages():
    if not session.get("user_id"):
        flash("Сначала войдите на сайт")
        return redirect(url_for("login"))

    # все пользователи, с которыми уже есть переписка
    users = db.query_all(
        "select id, login from users where id in ("
        "    select sender_id from messages where receiver_id = ? "
        "    union "
        "    select receiver_id from messages where sender_id = ?) "
        "order by login", [session["user_id"], session["user_id"]])

    return render_template("messages.html", users=users)


@app.route("/messages/<int:user_id>", methods=["GET", "POST"])
def dialog(user_id):
    if not session.get("user_id"):
        flash("Сначала войдите на сайт")
        return redirect(url_for("login"))

    other = db.query_one("select id, login from users where id = ?", [user_id])
    if other is None:
        return render_template("error.html",
                               text="Пользователь не найден"), 404
    if user_id == session["user_id"]:
        return render_template("error.html",
                               text="Нельзя писать самому себе"), 403

    if request.method == "POST":
        text = request.form.get("text", "").strip()
        ad_id = request.form.get("ad_id", type=int)
        if text:
            db.execute(
                "insert into messages (sender_id, receiver_id, ad_id, "
                "                      message_text) values (?, ?, ?, ?)",
                [session["user_id"], user_id, ad_id, text])
        return redirect(url_for("dialog", user_id=user_id))

    msgs = db.query_all(
        "select m.id, m.sender_id, m.message_text, m.created_at, u.login "
        "from messages m "
        "join users u on u.id = m.sender_id "
        "where (m.sender_id = ? and m.receiver_id = ?) "
        "   or (m.sender_id = ? and m.receiver_id = ?) "
        "order by m.id", [session["user_id"], user_id,
                          user_id, session["user_id"]])

    return render_template("dialog.html", other=other, msgs=msgs)


# ---------------------------------------------------------------------------
# Регистрация, вход и выход
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if len(login) < 3:
            flash("Логин должен быть не короче 3 символов")
        elif len(password) < 5:
            flash("Пароль должен быть не короче 5 символов")
        elif password != password2:
            flash("Пароли не совпадают")
        elif db.query_one("select id from users where login = ?", [login]):
            flash("Такой логин уже занят")
        else:
            db.execute(
                "insert into users (login, password_hash, role) "
                "values (?, ?, 'user')",
                [login, generate_password_hash(password)])
            flash("Регистрация прошла успешно. Теперь войдите на сайт")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        user = db.query_one(
            "select id, login, password_hash from users where login = ?",
            [login])

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Вы вошли на сайт")
            return redirect(url_for("index"))

        flash("Неверный логин или пароль")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли с сайта")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ok, error = db.ping(retries=1)
    if not ok:
        print()
        print("НЕТ СВЯЗИ С БАЗОЙ ДАННЫХ")
        print("  Файл базы: %s" % config.DB_PATH)
        print("  Ошибка   : %s" % error)
        print()
        print(config.firebird_help())
        raise SystemExit(1)

    print()
    print("=" * 60)
    print("  Сайт объявлений «Авито»")
    print("  Откройте в браузере: http://%s:%d" % (config.WEB_HOST,
                                                  config.WEB_PORT))
    print("  Вход: admin / admin")
    print("  Остановить сервер: Ctrl+C")
    print("=" * 60)
    print()
    app.run(host=config.WEB_HOST, port=config.WEB_PORT,
            debug=config.DEBUG, use_reloader=False)
