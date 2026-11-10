from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort,
)
import os
from functools import wraps

import db_functions as db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")


# ============================================================
#  ХЕЛПЕРЫ СЕССИИ
# ============================================================
def current_user_id():
    return session.get("user_id")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user_id():
            flash("Требуется вход в аккаунт", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def inject_user():
    """Добавляет current_user во все шаблоны."""
    uid = current_user_id()
    return {
        "current_user": db.get_user_by_id(uid) if uid else None,
    }


app.context_processor(lambda: inject_user())


# ============================================================
#  КАТАЛОГ
# ============================================================
@app.route("/")
def index():
    search_query = request.args.get("q", "").strip()
    category_id  = request.args.get("category_id") or None
    city         = request.args.get("city", "").strip()
    sort_by      = request.args.get("sort", "date")

    ads = db.get_catalog(
        search_query=search_query,
        category_id=category_id,
        city=city,
        sort_by=sort_by,
    )
    return render_template(
        "index.html",
        ads=ads,
        categories=db.get_all_categories(),
        cities=db.get_all_cities(),
        search_query=search_query,
        selected_category=int(category_id) if category_id else None,
        selected_city=city,
        sort_by=sort_by,
    )


# ============================================================
#  РЕГИСТРАЦИЯ / ВХОД / ВЫХОД
# ============================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login    = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        if not login or not password:
            flash("Заполните все поля", "error")
            return render_template("register.html")

        user_id = db.register_user(login, password)
        if user_id is None:
            flash("Логин уже занят", "error")
            return render_template("register.html")

        session["user_id"] = user_id
        session["login"]   = login
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login    = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        row = db.login_user(login, password)
        if not row:
            flash("Неверный логин или пароль", "error")
            return render_template("login.html")

        session["user_id"], session["login"], _role = row
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ============================================================
#  ОБЪЯВЛЕНИЯ
# ============================================================
@app.route("/ad/<int:ad_id>")
def ad_detail(ad_id):
    ad = db.get_ad_details(ad_id)
    if not ad:
        abort(404)
    fav = bool(current_user_id()) and db.is_favorite(current_user_id(), ad_id)
    return render_template("ad_detail.html", ad=ad, is_favorite=fav)


@app.route("/ad/create", methods=["GET", "POST"])
@login_required
def ad_create():
    if request.method == "POST":
        try:
            price = float(request.form.get("price", "0").replace(",", "."))
        except ValueError:
            flash("Некорректная цена", "error")
            return render_template("ad_form.html",
                                   categories=db.get_all_categories(),
                                   ad=None)

        image_url = request.form.get("image_url", "").strip() or None

        new_id = db.create_ad(
            user_id=current_user_id(),
            category_id=int(request.form["category_id"]),
            title=request.form["title"].strip(),
            description=request.form.get("description", "").strip(),
            price=price,
            city=request.form["city"].strip(),
            image_url=image_url,
        )
        if new_id is None:
            flash("Не удалось создать объявление", "error")
            return render_template("ad_form.html",
                                   categories=db.get_all_categories(),
                                   ad=None)
        return redirect(url_for("ad_detail", ad_id=new_id))

    return render_template("ad_form.html",
                           categories=db.get_all_categories(),
                           ad=None)


@app.route("/ad/<int:ad_id>/edit", methods=["GET", "POST"])
@login_required
def ad_edit(ad_id):
    ad = db.get_ad_details(ad_id)
    if not ad:
        abort(404)
    if ad[8] != current_user_id():
        abort(403)

    if request.method == "POST":
        try:
            price = float(request.form.get("price", "0").replace(",", "."))
        except ValueError:
            flash("Некорректная цена", "error")
            return render_template("ad_form.html",
                                   categories=db.get_all_categories(),
                                   ad=ad)

        ok = db.update_ad(
            ad_id=ad_id,
            user_id=current_user_id(),
            category_id=int(request.form["category_id"]),
            title=request.form["title"].strip(),
            description=request.form.get("description", "").strip(),
            price=price,
            city=request.form["city"].strip(),
            image_url=request.form.get("image_url", "").strip() or None,
        )
        if not ok:
            flash("Не удалось сохранить", "error")
        return redirect(url_for("ad_detail", ad_id=ad_id))

    return render_template("ad_form.html",
                           categories=db.get_all_categories(),
                           ad=ad)


@app.route("/ad/<int:ad_id>/delete", methods=["POST"])
@login_required
def ad_delete(ad_id):
    db.delete_ad(ad_id, current_user_id())
    return redirect(url_for("profile"))


# ============================================================
#  ИЗБРАННОЕ
# ============================================================
@app.route("/favorites")
@login_required
def favorites():
    return render_template(
        "favorites.html",
        ads=db.get_user_favorites(current_user_id()),
    )


@app.route("/favorite/<int:ad_id>/toggle", methods=["POST"])
@login_required
def favorite_toggle(ad_id):
    if db.is_favorite(current_user_id(), ad_id):
        db.remove_favorite(current_user_id(), ad_id)
    else:
        db.add_favorite(current_user_id(), ad_id)
    return redirect(request.referrer or url_for("index"))


# ============================================================
#  ПРОФИЛЬ
# ============================================================
@app.route("/profile")
@login_required
def profile():
    return render_template(
        "profile.html",
        user=db.get_user_by_id(current_user_id()),
        ads=db.get_user_ads(current_user_id()),
    )


# ============================================================
#  ЧАТ
# ============================================================
@app.route("/messages")
@login_required
def messages_list():
    return render_template(
        "messages.html",
        conversations=db.get_conversations(current_user_id()),
    )


@app.route("/messages/<int:other_id>", methods=["GET", "POST"])
@login_required
def chat(other_id):
    if other_id == current_user_id():
        abort(400)

    ad_id = request.args.get("ad_id", type=int)

    if request.method == "POST":
        text = request.form.get("text", "").strip()
        if text:
            db.send_message(current_user_id(), other_id, ad_id, text)
        return redirect(url_for("chat", other_id=other_id,
                                ad_id=ad_id) if ad_id else
                        url_for("chat", other_id=other_id))

    return render_template(
        "chat.html",
        other=db.get_user_by_id(other_id),
        messages=db.get_dialog(current_user_id(), other_id, ad_id),
        ad_id=ad_id,
    )


# ============================================================
#  ОШИБКИ
# ============================================================
@app.errorhandler(403)
def err_403(_e):
    return render_template("error.html",
                           code=403,
                           message="Доступ запрещён"), 403


@app.errorhandler(404)
def err_404(_e):
    return render_template("error.html",
                           code=404,
                           message="Страница не найдена"), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)