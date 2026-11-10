from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response
)

from functools import wraps
import db_functions as db


app = Flask(__name__)

# Ключ для работы с сессиями
app.secret_key = "avito-secret-key"


def login_required(function):
    """Проверка авторизации пользователя."""

    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Сначала необходимо войти в аккаунт.")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


@app.context_processor
def add_user():
    """Передача данных пользователя во все шаблоны."""

    return {
        "current_user_id": session.get("user_id"),
        "current_login": session.get("login"),
        "current_user": db.get_user_by_id(session["user_id"])
        if "user_id" in session else None
    }


@app.route("/")
def index():
    """Главная страница с каталогом объявлений."""

    search_query = request.args.get("q", "")
    selected_category = request.args.get("category_id", "")
    selected_city = request.args.get("city", "")
    sort_by = request.args.get("sort", "date")

    category_id = None

    if selected_category:
        try:
            category_id = int(selected_category)
        except ValueError:
            category_id = None

    ads = db.get_catalog(
        search_query=search_query,
        category_id=category_id,
        city=selected_city,
        sort_by=sort_by
    )

    categories = db.get_all_categories()
    cities = db.get_all_cities()

    return render_template(
        "index.html",
        ads=ads,
        categories=categories,
        cities=cities,
        search_query=search_query,
        selected_category=selected_category,
        selected_city=selected_city,
        sort_by=sort_by
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация пользователя."""

    if request.method == "POST":
        login = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        if not login or not password:
            flash("Заполните все поля.")
            return redirect(url_for("register"))

        if len(password) < 4:
            flash("Пароль должен содержать не менее 4 символов.")
            return redirect(url_for("register"))

        user_id = db.register_user(login, password)

        if user_id:
            flash("Регистрация прошла успешно. Теперь войдите.")
            return redirect(url_for("login"))

        flash("Пользователь с таким логином уже существует.")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Авторизация пользователя."""

    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        user = db.login_user(login_value, password)

        if user:
            session["user_id"] = user[0]
            session["login"] = user[1]
            session["role"] = user[2]

            flash("Вы успешно вошли в аккаунт.")
            return redirect(url_for("index"))

        flash("Неверный логин или пароль.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Выход из аккаунта."""

    session.clear()
    flash("Вы вышли из аккаунта.")

    return redirect(url_for("index"))


@app.route("/ad/<int:ad_id>")
def ad_detail(ad_id):
    """Страница отдельного объявления."""

    ad = db.get_ad_details(ad_id)

    if not ad:
        return "Объявление не найдено", 404

    favorite = False

    if "user_id" in session:
        favorite = db.is_favorite(session["user_id"], ad_id)

    return render_template(
        "ad_detail.html",
        ad=ad,
        favorite=favorite
    )


@app.route("/ad/create", methods=["GET", "POST"])
@login_required
def ad_create():
    """Создание нового объявления."""

    categories = db.get_all_categories()

    if request.method == "POST":
        category_id = request.form.get("category_id")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "")
        city = request.form.get("city", "").strip()
        image_url = request.form.get("image_url", "").strip()

        try:
            category_id = int(category_id)
            price = float(price)

            if price < 0:
                raise ValueError

        except (ValueError, TypeError):
            flash("Проверьте категорию и цену.")
            return redirect(url_for("ad_create"))

        if not title or not description or not city:
            flash("Заполните все обязательные поля.")
            return redirect(url_for("ad_create"))

        result = db.create_ad(
            user_id=session["user_id"],
            category_id=category_id,
            title=title,
            description=description,
            price=price,
            city=city,
            image_url=image_url if image_url else None
        )

        if result:
            flash("Объявление успешно создано.")
            return redirect(url_for("index"))

        flash("Не удалось создать объявление.")

    return render_template(
        "ad_create.html",
        categories=categories
    )


@app.route("/ad/edit/<int:ad_id>", methods=["GET", "POST"])
@login_required
def ad_edit(ad_id):
    """Редактирование объявления."""

    ad = db.get_ad_details(ad_id)

    if not ad:
        return "Объявление не найдено", 404

    # Проверяем, что объявление принадлежит текущему пользователю
    if ad[8] != session["user_id"]:
        return "Нет доступа к этому объявлению", 403

    categories = db.get_all_categories()

    if request.method == "POST":
        category_id = request.form.get("category_id")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "")
        city = request.form.get("city", "").strip()
        image_url = request.form.get("image_url", "").strip()

        try:
            category_id = int(category_id)
            price = float(price)

            if price < 0:
                raise ValueError

        except (ValueError, TypeError):
            flash("Проверьте категорию и цену.")
            return redirect(url_for("ad_edit", ad_id=ad_id))

        if not title or not description or not city:
            flash("Заполните все обязательные поля.")
            return redirect(url_for("ad_edit", ad_id=ad_id))

        result = db.update_ad(
            ad_id=ad_id,
            user_id=session["user_id"],
            category_id=category_id,
            title=title,
            description=description,
            price=price,
            city=city,
            image_url=image_url if image_url else None
        )

        if result:
            flash("Объявление изменено.")
            return redirect(url_for("ad_detail", ad_id=ad_id))

        flash("Не удалось изменить объявление.")

    return render_template(
        "ad_edit.html",
        ad=ad,
        categories=categories
    )


@app.route("/ad/delete/<int:ad_id>", methods=["GET", "POST"])
@login_required
def ad_delete(ad_id):
    """Удаление объявления."""

    result = db.delete_ad(ad_id, session["user_id"])

    if result:
        flash("Объявление удалено.")
    else:
        flash("Не удалось удалить объявление.")

    return redirect(url_for("profile"))


@app.route("/favorites")
@login_required
def favorites():
    """Страница избранных объявлений."""

    ads = db.get_user_favorites(session["user_id"])

    return render_template(
        "favorites.html",
        ads=ads
    )


@app.route("/favorite/<int:ad_id>")
@login_required
def favorite_toggle(ad_id):
    """Добавление или удаление объявления из избранного."""

    if db.is_favorite(session["user_id"], ad_id):
        db.remove_favorite(session["user_id"], ad_id)
    else:
        db.add_favorite(session["user_id"], ad_id)

    return redirect(request.referrer or url_for("index"))


@app.route("/profile")
@login_required
def profile():
    """Личный кабинет пользователя."""

    user = db.get_user_by_id(session["user_id"])
    ads = db.get_user_ads(session["user_id"])

    return render_template(
        "profile.html",
        user=user,
        ads=ads
    )


@app.route("/messages")
@login_required
def messages():
    """Список переписок пользователя."""

    conversations = db.get_conversations(session["user_id"])

    return render_template(
        "messages.html",
        conversations=conversations
    )


@app.route("/chat/<int:other_id>", methods=["GET", "POST"])
@login_required
def chat(other_id):
    """Переписка с другим пользователем."""

    user = db.get_user_by_id(other_id)

    if not user:
        return "Пользователь не найден", 404

    if other_id == session["user_id"]:
        return "Нельзя открыть переписку с самим собой", 400

    ad_id = request.args.get("ad_id")

    if ad_id:
        try:
            ad_id = int(ad_id)
        except ValueError:
            ad_id = None

    if request.method == "POST":
        message_text = request.form.get("message", "").strip()

        if message_text:
            db.send_message(
                sender_id=session["user_id"],
                receiver_id=other_id,
                ad_id=ad_id,
                message_text=message_text
            )

        return redirect(
            url_for("chat", other_id=other_id, ad_id=ad_id)
        )

    messages_list = db.get_dialog(
        user_id=session["user_id"],
        other_id=other_id,
        ad_id=ad_id
    )

    return render_template(
        "chat.html",
        other=user,
        messages=messages_list,
        ad_id=ad_id
    )


@app.route("/image/<int:ad_id>")
def image(ad_id):
    """Отображение изображения объявления."""

    ad = db.get_ad_details(ad_id)

    if not ad:
        return "Изображение не найдено", 404

    image_url = ad[5]

    if image_url and image_url.startswith(("http://", "https://")):
        return redirect(image_url)

    # Если изображение не указано, показываем заглушку
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="400" height="250">
        <rect width="100%" height="100%" fill="#eeeeee"/>
        <text x="50%" y="50%"
              text-anchor="middle"
              dominant-baseline="middle"
              fill="#777777"
              font-size="20">
            Нет изображения
        </text>
    </svg>
    """

    return Response(svg, mimetype="image/svg+xml")


@app.errorhandler(404)
def page_not_found(error):
    """Страница ошибки 404."""

    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )