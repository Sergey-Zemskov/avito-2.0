from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
# Импортируем ваши функции из db_functions.py
from db_functions import (
    register_user, login_user, get_catalog, get_all_categories,
    get_ad_details, get_ad_image, add_to_favorites, remove_from_favorites, get_favorites,
    create_ad, update_ad, delete_ad, get_user_ads, send_message, get_chat_history, get_messages_list, get_user_by_id
)

app = Flask(__name__)
app.secret_key = "student_secret_123" # Нужно для работы сессий (входа)

# --- ГЛАВНАЯ СТРАНИЦА ---
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category") or None
    city = request.args.get("city", "").strip() or None
    sort = request.args.get("sort", "date")

    ads = get_catalog(q, int(cat) if cat else None, city, sort)
    categories = get_all_categories()
    
    return render_template("index.html", ads=ads, categories=categories, 
                           current_user_id=session.get("user_id"), current_login=session.get("login"))

# --- РЕГИСТРАЦИЯ И ВХОД ---
@app.route("/register", methods=["POST"])
def register():
    login = request.form["login"].strip()
    password = request.form["password"]
    if register_user(login, password):
        flash("Регистрация успешна! Войдите.")
        return redirect(url_for("index"))
    flash("Логин уже занят.")
    return redirect(url_for("index"))

@app.route("/login", methods=["POST"])
def login():
    user = login_user(request.form["login"].strip(), request.form["password"])
    if user:
        session["user_id"] = user[0]
        session["login"] = user[1]
    else:
        flash("Неверный логин или пароль.")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# --- КАРТОЧКА ОБЪЯВЛЕНИЯ И ФОТО ---
@app.route("/ad/<int:ad_id>")
def ad_detail(ad_id):
    ad = get_ad_details(ad_id)
    if not ad:
        return "Объявление не найдено", 404
    return render_template("index.html", ad=ad, current_user_id=session.get("user_id"))

@app.route("/image/<int:ad_id>")
def image(ad_id):
    data = get_ad_image(ad_id)
    if not data:
        return "", 404
    return Response(bytes(data), mimetype="image/jpeg")

# --- ДОБАВЛЕНИЕ ОБЪЯВЛЕНИЯ ---
@app.route("/add_ad", methods=["POST"])
def add_ad():
    if not session.get("user_id"):
        return redirect(url_for("index"))
    
    image_bytes = None
    f = request.files.get("image")
    if f and f.filename:
        image_bytes = f.read() 

    create_ad(
        user_id=session["user_id"],
        category_id=int(request.form["category_id"]),
        title=request.form["title"],
        description=request.form.get("description", ""),
        price=float(request.form["price"]),
        city=request.form["city"],
        image_data=image_bytes
    )
    return redirect(url_for("index"))

# --- ИЗБРАННОЕ ---
@app.route("/favorites/add/<int:ad_id>", methods=["POST"])
def fav_add(ad_id):
    if session.get("user_id"):
        add_to_favorites(session["user_id"], ad_id)
    return redirect(request.referrer or url_for("index"))

# --- СООБЩЕНИЯ ---
@app.route("/send_message", methods=["POST"])
def send_msg():
    if not session.get("user_id"):
        return redirect(url_for("index"))
    
    receiver_id = int(request.form["receiver_id"])
    ad_id = int(request.form["ad_id"])
    text = request.form["text"]
    
    if text.strip():
        send_message(session["user_id"], receiver_id, ad_id, text)
    
    return redirect(request.referrer or url_for("index"))

if __name__ == "__main__":
    # Запуск сервера
    app.run(debug=True, host="127.0.0.1", port=5000)