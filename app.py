from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from db_functions import *

app = Flask(__name__)
app.secret_key = "secret_key_for_student"

@app.context_processor
def inject_user():
    return dict(current_user_id=session.get("user_id"), current_login=session.get("login"))

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category")
    city = request.args.get("city", "").strip()
    sort = request.args.get("sort", "date")
    ads = get_catalog(q, int(cat) if cat else None, city or None, sort)
    categories = get_all_categories()
    return render_template("index.html", ads=ads, categories=categories, q=q, selected_cat=cat, city=city, sort=sort)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = login_user(request.form.get("login"), request.form.get("password"))
        if user:
            session["user_id"] = user[0]
            session["login"] = user[1]
            return redirect(url_for("index"))
        flash("Неверный логин или пароль.")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if register_user(request.form.get("login"), request.form.get("password")):
            flash("Успешная регистрация! Теперь войдите.")
            return redirect(url_for("login"))
        flash("Логин уже занят.")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/ad/<int:ad_id>")
def ad_detail(ad_id):
    ad = get_ad_details(ad_id)
    if not ad:
        return "Объявление не найдено", 404
    return render_template("ad_detail.html", ad=ad)

@app.route("/image/<int:ad_id>")
def image(ad_id):
    data = get_ad_image(ad_id)
    if not data:
        return "", 404
    return Response(bytes(data), mimetype="image/jpeg")

@app.route("/add_ad", methods=["GET", "POST"])
def add_ad():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if request.method == "POST":
        image_bytes = request.files["image"].read() if request.files.get("image") else None
        create_ad(session["user_id"], int(request.form["category_id"]), request.form["title"],
                  request.form["description"], float(request.form["price"]), request.form["city"], image_bytes)
        return redirect(url_for("my_ads"))
    return render_template("ad_form.html", categories=get_all_categories(), ad=None)

@app.route("/edit_ad/<int:ad_id>", methods=["GET", "POST"])
def edit_ad(ad_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    ad = get_ad_details(ad_id)
    if not ad or ad[7] != session["user_id"]:
        return "Доступ запрещен", 403
    if request.method == "POST":
        image_bytes = request.files["image"].read() if request.files.get("image") else None
        update_ad(ad_id, session["user_id"], int(request.form["category_id"]), request.form["title"],
                  request.form["description"], float(request.form["price"]), request.form["city"], image_bytes)
        return redirect(url_for("my_ads"))
    return render_template("ad_form.html", categories=get_all_categories(), ad=ad)

@app.route("/delete_ad/<int:ad_id>", methods=["POST"])
def delete_ad_route(ad_id):
    if session.get("user_id"):
        delete_ad(ad_id, session["user_id"])
    return redirect(url_for("my_ads"))

@app.route("/my_ads")
def my_ads():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("my_ads.html", ads=get_user_ads(session["user_id"]))

@app.route("/favorites")
def favorites():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("favorites.html", ads=get_favorites(session["user_id"]))

@app.route("/favorites/add/<int:ad_id>", methods=["POST"])
def fav_add(ad_id):
    if session.get("user_id"):
        add_to_favorites(session["user_id"], ad_id)
    return redirect(request.referrer or url_for("index"))

@app.route("/favorites/remove/<int:ad_id>", methods=["POST"])
def fav_remove(ad_id):
    if session.get("user_id"):
        remove_from_favorites(session["user_id"], ad_id)
    return redirect(url_for("favorites"))

@app.route("/messages")
def messages():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("messages.html", chats=get_messages_list(session["user_id"]))

@app.route("/chat/<int:ad_id>/<int:other_id>", methods=["GET", "POST"])
def chat(ad_id, other_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if request.method == "POST":
        text = request.form.get("text", "")
        if text.strip():
            send_message(session["user_id"], other_id, ad_id, text)
        return redirect(url_for("chat", ad_id=ad_id, other_id=other_id))
    return render_template("chat.html", history=get_chat_history(session["user_id"], other_id, ad_id), 
                           other=get_user_by_id(other_id), ad=get_ad_details(ad_id))

if __name__ == "__main__":
    app.run(debug=True)