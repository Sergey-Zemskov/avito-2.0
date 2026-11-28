from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.utils import secure_filename
import db_functions as db

app = Flask(__name__)
app.secret_key = "avito-secret-key"  # Для постоянного использования замени на случайный ключ.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # Максимум 5 МБ на запрос.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Сначала необходимо войти в аккаунт.")
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


def read_uploaded_image():
    """Возвращает (байты, MIME) или (None, None), если файл не выбран."""
    file = request.files.get("image")
    if not file or not file.filename:
        return None, None
    if file.mimetype not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Можно загружать только JPG, PNG, GIF или WEBP.")
    data = file.read()
    if not data:
        raise ValueError("Выбран пустой файл.")
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("Размер фотографии не должен превышать 5 МБ.")
    # Проверяем сигнатуры, чтобы не принимать файл только по расширению.
    valid = (
        data.startswith(b"\xff\xd8\xff") or
        data.startswith(b"\x89PNG\r\n\x1a\n") or
        data.startswith((b"GIF87a", b"GIF89a")) or
        (len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )
    if not valid:
        raise ValueError("Файл не похож на изображение поддерживаемого формата.")
    return data, file.mimetype


@app.context_processor
def add_user():
    return {
        "current_user_id": session.get("user_id"),
        "current_login": session.get("login"),
        "current_user": db.get_user_by_id(session["user_id"]) if "user_id" in session else None
    }


@app.route("/")
def index():
    search_query = request.args.get("q", "")
    selected_category = request.args.get("category_id", "")
    selected_city = request.args.get("city", "")
    sort_by = request.args.get("sort", "date")
    try:
        category_id = int(selected_category) if selected_category else None
    except ValueError:
        category_id = None
    ads = db.get_catalog(search_query, category_id, selected_city, sort_by)
    return render_template(
        "index.html", ads=ads, categories=db.get_all_categories(), cities=db.get_all_cities(),
        search_query=search_query, selected_category=selected_category,
        selected_city=selected_city, sort_by=sort_by
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        password = request.form.get("password", "")
        if not login or not password:
            flash("Заполните все поля.")
        elif len(password) < 4:
            flash("Пароль должен содержать не менее 4 символов.")
        else:
            user_id = db.register_user(login, password)
            if user_id:
                flash("Регистрация прошла успешно. Теперь войдите.")
                return redirect(url_for("login"))
            flash("Пользователь с таким логином уже существует.")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = db.login_user(request.form.get("login", "").strip(), request.form.get("password", ""))
        if user:
            session["user_id"], session["login"], session["role"] = user[0], user[1], user[2]
            flash("Вы успешно вошли в аккаунт.")
            return redirect(url_for("index"))
        flash("Неверный логин или пароль.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из аккаунта.")
    return redirect(url_for("index"))


@app.route("/ad/<int:ad_id>")
def ad_detail(ad_id):
    ad = db.get_ad_details(ad_id)
    if not ad:
        return "Объявление не найдено", 404
    favorite = bool("user_id" in session and db.is_favorite(session["user_id"], ad_id))
    return render_template("ad_detail.html", ad=ad, favorite=favorite)


@app.route("/ad/create", methods=["GET", "POST"])
@login_required
def ad_create():
    categories = db.get_all_categories()
    if request.method == "POST":
        try:
            category_id = int(request.form.get("category_id", ""))
            price = float(request.form.get("price", ""))
            if price < 0:
                raise ValueError
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            city = request.form.get("city", "").strip()
            if not title or not description or not city:
                raise ValueError
            image_data, image_type = read_uploaded_image()
        except ValueError as error:
            flash(str(error) or "Проверьте категорию, цену и обязательные поля.")
            return render_template("ad_form.html", ad=None, categories=categories)
        result = db.create_ad(session["user_id"], category_id, title, description,
                              price, city, image_data, image_type)
        if result:
            flash("Объявление успешно создано.")
            return redirect(url_for("profile"))
        flash("Не удалось создать объявление. Подробная ошибка выведена в терминал.")
    return render_template("ad_form.html", ad=None, categories=categories)


@app.route("/ad/edit/<int:ad_id>", methods=["GET", "POST"])
@login_required
def ad_edit(ad_id):
    ad = db.get_ad_details(ad_id)
    if not ad:
        return "Объявление не найдено", 404
    if ad[8] != session["user_id"]:
        return "Нет доступа к этому объявлению", 403
    categories = db.get_all_categories()
    if request.method == "POST":
        try:
            category_id = int(request.form.get("category_id", ""))
            price = float(request.form.get("price", ""))
            if price < 0:
                raise ValueError
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            city = request.form.get("city", "").strip()
            if not title or not description or not city:
                raise ValueError
            image_data, image_type = read_uploaded_image()
        except ValueError as error:
            flash(str(error) or "Проверьте категорию, цену и обязательные поля.")
            return render_template("ad_form.html", ad=ad, categories=categories)
        result = db.update_ad(ad_id, session["user_id"], category_id, title,
                              description, price, city, image_data, image_type,
                              replace_image=image_data is not None)
        if result:
            flash("Объявление изменено.")
            return redirect(url_for("ad_detail", ad_id=ad_id))
        flash("Не удалось изменить объявление.")
    return render_template("ad_form.html", ad=ad, categories=categories)


@app.route("/ad/delete/<int:ad_id>", methods=["POST"])
@login_required
def ad_delete(ad_id):
    if db.delete_ad(ad_id, session["user_id"]):
        flash("Объявление удалено.")
    else:
        flash("Не удалось удалить объявление.")
    return redirect(url_for("profile"))


@app.route("/favorites")
@login_required
def favorites():
    return render_template("favorites.html", ads=db.get_user_favorites(session["user_id"]))


@app.route("/favorite/<int:ad_id>", methods=["POST"])
@login_required
def favorite_toggle(ad_id):
    if not db.get_ad_details(ad_id):
        return "Объявление не найдено", 404
    if db.is_favorite(session["user_id"], ad_id):
        db.remove_favorite(session["user_id"], ad_id)
        flash("Объявление удалено из избранного.")
    else:
        db.add_favorite(session["user_id"], ad_id)
        flash("Объявление добавлено в избранное.")
    return redirect(request.form.get("next") or request.referrer or url_for("favorites"))


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=db.get_user_by_id(session["user_id"]),
                           ads=db.get_user_ads(session["user_id"]))


@app.route("/messages")
@login_required
def messages():
    return render_template("messages.html", conversations=db.get_conversations(session["user_id"]))


@app.route("/chat/<int:other_id>", methods=["GET", "POST"])
@login_required
def chat(other_id):
    user = db.get_user_by_id(other_id)
    if not user:
        return "Пользователь не найден", 404
    if other_id == session["user_id"]:
        return "Нельзя открыть переписку с самим собой", 400
    raw_ad_id = request.values.get("ad_id")
    try:
        ad_id = int(raw_ad_id) if raw_ad_id else None
    except ValueError:
        ad_id = None
    if ad_id is not None and not db.get_ad_details(ad_id):
        ad_id = None
    if request.method == "POST":
        message_text = request.form.get("message", "").strip()
        if message_text:
            if not db.send_message(session["user_id"], other_id, ad_id, message_text):
                flash("Не удалось отправить сообщение.")
        else:
            flash("Введите текст сообщения.")
        return redirect(url_for("chat", other_id=other_id, ad_id=ad_id))
    return render_template("chat.html", other=user,
                           messages=db.get_dialog(session["user_id"], other_id, ad_id), ad_id=ad_id)


@app.route("/image/<int:ad_id>")
def image(ad_id):
    image_data, image_type = db.get_ad_image(ad_id)
    if not image_data:
        return "Изображение не найдено", 404
    return Response(image_data, mimetype=image_type)


@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", code=404, message="Страница не найдена."), 404


@app.errorhandler(413)
def file_too_large(error):
    return render_template("error.html", code=413, message="Фотография слишком большая. Максимум 5 МБ."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
