
import os
from functools import wraps
from flask import Response

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
)

import db_functions as db


app = Flask(__name__)

secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    raise RuntimeError(
        "Не задан SECRET_KEY. Установите переменную окружения SECRET_KEY."
    )

app.config["SECRET_KEY"] = secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ============================================================
# ПОЛЬЗОВАТЕЛИ И СЕССИИ
# ============================================================

def current_user_id():
    user_id = session.get("user_id")
    return int(user_id) if user_id is not None else None


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user_id() is None:
            flash("Для выполнения действия необходимо войти.", "error")
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_user():
    user_id = current_user_id()
    user = db.get_user_by_id(user_id) if user_id is not None else None

    return {
        "current_user": user,
        "current_user_id": user_id,
        "current_login": user[1] if user else None,
    }


# ============================================================
# ГЛАВНАЯ СТРАНИЦА И КАТАЛОГ
# ============================================================

@app.route("/")
def index():
    search_query = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", "").strip()
    city = request.args.get("city", "").strip()
    sort_by = request.args.get("sort", "date")

    if sort_by not in ("date", "price_asc", "price_desc"):
        sort_by = "date"

    try:
        category_id = int(category_id) if category_id else None
    except ValueError:
        category_id = None

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
        selected_category=category_id,
        selected_city=city,
        sort_by=sort_by,
    )


# ============================================================
# РЕГИСТРАЦИЯ
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        if len(login) < 3 or len(login) > 50:
            flash("Логин должен содержать от 3 до 50 символов.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Пароль должен содержать не менее 6 символов.", "error")
            return render_template("register.html")

        user_id = db.register_user(login, password)

        if user_id is None:
            flash("Не удалось зарегистрировать пользователя. Возможно, логин занят.", "error")
            return render_template("register.html")

        session.clear()
        session["user_id"] = int(user_id)

        flash("Регистрация успешно завершена.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


# ============================================================
# АВТОРИЗАЦИЯ
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        row = db.login_user(login_value, password)

        if not row:
            flash("Неверный логин или пароль.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = int(row[0])

        flash("Вы успешно вошли в систему.", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


# ============================================================
# ВЫХОД
# ============================================================

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("index"))


# ============================================================
# ИЗОБРАЖЕНИЯ
# ============================================================

@app.route("/image/<int:ad_id>")
def image(ad_id):
    ad = db.get_ad_details(ad_id)

    if not ad or not ad[5]:
        abort(404)

    return redirect(ad[5])


# ============================================================
# ПРОСМОТР ОБЪЯВЛЕНИЯ
# ============================================================

@app.route("/ad/<int:ad_id>")
def ad_detail(ad_id):
    ad = db.get_ad_details(ad_id)

    if not ad:
        abort(404)

    user_id = current_user_id()
    is_favorite = (
        db.is_favorite(user_id, ad_id)
        if user_id is not None
        else False
    )

    return render_template(
        "ad_detail.html",
        ad=ad,
        is_favorite=is_favorite,
    )


# ============================================================
# СОЗДАНИЕ ОБЪЯВЛЕНИЯ
# ============================================================

@app.route("/ad/create", methods=["GET", "POST"])
@login_required
def ad_create():
    categories = db.get_all_categories()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        city = request.form.get("city", "").strip()
        image_url = request.form.get("image_url", "").strip() or None

        try:
            price = float(request.form.get("price", "").replace(",", "."))
            category_id = int(request.form.get("category_id", ""))
        except (ValueError, TypeError):
            flash("Проверьте цену и категорию.", "error")
            return render_template("ad_form.html", categories=categories, ad=None)

        if not title or not city:
            flash("Название и город обязательны.", "error")
            return render_template("ad_form.html", categories=categories, ad=None)

        if price < 0:
            flash("Цена не может быть отрицательной.", "error")
            return render_template("ad_form.html", categories=categories, ad=None)

        if not any(c[0] == category_id for c in categories):
            flash("Выбрана несуществующая категория.", "error")
            return render_template("ad_form.html", categories=categories, ad=None)

        new_id = db.create_ad(
            user_id=current_user_id(),
            category_id=category_id,
            title=title,
            description=description,
            price=price,
            city=city,
            image_url=image_url,
        )

        if new_id is None:
            flash("Не удалось создать объявление.", "error")
            return render_template("ad_form.html", categories=categories, ad=None)

        flash("Объявление успешно создано.", "success")
        return redirect(url_for("ad_detail", ad_id=new_id))

    return render_template(
        "ad_form.html",
        categories=categories,
        ad=None,
    )


# ============================================================
# РЕДАКТИРОВАНИЕ ОБЪЯВЛЕНИЯ
# ============================================================

@app.route("/ad/<int:ad_id>/edit", methods=["GET", "POST"])
@login_required
def ad_edit(ad_id):
    ad = db.get_ad_details(ad_id)

    if not ad:
        abort(404)

    # Индекс 8 — идентификатор владельца объявления.
    if int(ad[8]) != current_user_id():
        abort(403)

    categories = db.get_all_categories()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        city = request.form.get("city", "").strip()
        image_url = request.form.get("image_url", "").strip() or ad[5]

        try:
            price = float(request.form.get("price", "").replace(",", "."))
            category_id = int(request.form.get("category_id", ""))
        except (ValueError, TypeError):
            flash("Проверьте цену и категорию.", "error")
            return render_template("ad_form.html", categories=categories, ad=ad)

        if not title or not city or price < 0:
            flash("Проверьте введённые данные.", "error")
            return render_template("ad_form.html", categories=categories, ad=ad)

        if not any(c[0] == category_id for c in categories):
            flash("Выбрана несуществующая категория.", "error")
            return render_template("ad_form.html", categories=categories, ad=ad)

        success = db.update_ad(
            ad_id=ad_id,
            user_id=current_user_id(),
            category_id=category_id,
            title=title,
            description=description,
            price=price,
            city=city,
            image_url=image_url,
        )

        if not success:
            flash("Не удалось сохранить изменения.", "error")
            return render_template("ad_form.html", categories=categories, ad=ad)

        flash("Объявление обновлено.", "success")
        return redirect(url_for("ad_detail", ad_id=ad_id))

    return render_template(
        "ad_form.html",
        categories=categories,
        ad=ad,
    )


# ============================================================
# УДАЛЕНИЕ ОБЪЯВЛЕНИЯ
# ============================================================

@app.route("/ad/<int:ad_id>/delete", methods=["POST"])
@login_required
def ad_delete(ad_id):
    success = db.delete_ad(ad_id, current_user_id())

    if not success:
        abort(403)

    flash("Объявление удалено.", "success")
    return redirect(url_for("profile"))


# ============================================================
# ИЗБРАННОЕ
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
    if not db.get_ad_details(ad_id):
        abort(404)

    if db.is_favorite(current_user_id(), ad_id):
        db.remove_favorite(current_user_id(), ad_id)
        flash("Объявление удалено из избранного.", "success")
    else:
        db.add_favorite(current_user_id(), ad_id)
        flash("Объявление добавлено в избранное.", "success")

    return redirect(request.referrer or url_for("index"))


# ============================================================
# ПРОФИЛЬ
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
# СПИСОК ПЕРЕПИСОК
# ============================================================

@app.route("/messages")
@login_required
def messages_list():
    return render_template(
        "messages.html",
        conversations=db.get_conversations(current_user_id()),
    )


# ============================================================
# ЧАТ
# ============================================================

@app.route("/messages/<int:other_id>", methods=["GET", "POST"])
@login_required
def chat(other_id):
    user_id = current_user_id()

    if other_id == user_id:
        abort(400)

    other = db.get_user_by_id(other_id)

    if not other:
        abort(404)

    ad_id = request.args.get("ad_id", type=int)

    if request.method == "POST":
        message_text = request.form.get("text", "").strip()

        if not message_text:
            flash("Нельзя отправить пустое сообщение.", "error")
        elif len(message_text) > 2000:
            flash("Сообщение слишком длинное.", "error")
        else:
            success = db.send_message(
                sender_id=user_id,
                receiver_id=other_id,
                ad_id=ad_id,
                text=message_text,
            )

            if not success:
                flash("Не удалось отправить сообщение.", "error")

        return redirect(
            url_for("chat", other_id=other_id, ad_id=ad_id)
            if ad_id else url_for("chat", other_id=other_id)
        )

    messages = db.get_dialog(user_id, other_id, ad_id)

    return render_template(
        "chat.html",
        other=other,
        messages=messages,
        history=messages,
        ad_id=ad_id,
    )


# ============================================================
# ОБРАБОТЧИКИ ОШИБОК
# ============================================================

@app.errorhandler(403)
def error_403(error):
    return render_template(
        "error.html",
        code=403,
        message="Доступ запрещён.",
    ), 403


@app.errorhandler(404)
def error_404(error):
    return render_template(
        "error.html",
        code=404,
        message="Запрашиваемая страница не найдена.",
    ), 404


@app.errorhandler(500)
def error_500(error):
    return render_template(
        "error.html",
        code=500,
        message="Внутренняя ошибка сервера.",
    ), 500


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=False,
    )
