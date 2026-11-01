from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "customkingff-secret-change-this")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "kingff123")
DB = "game.db"


def database():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    con.execute("""
        CREATE TABLE IF NOT EXISTS players(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            uid TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS rooms(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            match_time TEXT
        )
    """)

    con.commit()
    return con


@app.route("/")
def home():
    con = database()

    total = con.execute(
        "SELECT COUNT(*) FROM players"
    ).fetchone()[0]

    rooms = con.execute(
        "SELECT * FROM rooms ORDER BY id DESC"
    ).fetchall()

    con.close()

    return render_template(
        "index.html",
        total=total,
        rooms=rooms
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        uid = request.form.get("uid", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name or not uid or not phone:
            flash("Please fill all details!")
            return redirect("/register")

        con = database()

        count = con.execute(
            "SELECT COUNT(*) FROM players"
        ).fetchone()[0]

        if count >= 50:
            con.close()
            flash("Registration Full! 50 Players Already Joined.")
            return redirect("/register")

        try:
            con.execute(
                "INSERT INTO players(name,uid,phone) VALUES(?,?,?)",
                (name, uid, phone)
            )

            con.commit()
            flash("Registration Successful!")

        except sqlite3.IntegrityError:
            flash("This UID is Already Registered!")

        con.close()

        return redirect("/")

    return render_template("register.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")

        flash("Wrong Admin Password!")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if not session.get("admin"):
        return redirect("/admin/login")

    con = database()

    players = con.execute(
        "SELECT * FROM players ORDER BY id DESC"
    ).fetchall()

    total = len(players)

    rooms = con.execute(
        "SELECT * FROM rooms ORDER BY id DESC"
    ).fetchall()

    con.close()

    return render_template(
        "dashboard.html",
        players=players,
        total=total,
        rooms=rooms
    )


@app.route("/add-room", methods=["POST"])
def add_room():

    if not session.get("admin"):
        return redirect("/admin/login")

    title = request.form.get("title", "").strip()
    match_time = request.form.get("match_time", "").strip()

    if title:
        con = database()

        con.execute(
            "INSERT INTO rooms(title,match_time) VALUES(?,?)",
            (title, match_time)
        )

        con.commit()
        con.close()

    return redirect("/dashboard")


@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


if __name__ == "__main__":
    database().close()
    app.run(host="0.0.0.0", port=5000, debug=True)
