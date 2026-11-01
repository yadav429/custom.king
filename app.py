
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import math

app = Flask(__name__)

# Security Settings
app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY is not set!")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD is not set!")

# IMPORTANT: Keep the same database path as your old app.
DB = os.environ.get("DB_PATH", "game.db")


# Database Function + Safe Migration
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

    # Add password_hash to existing players table
    columns = [
        row["name"]
        for row in con.execute("PRAGMA table_info(players)").fetchall()
    ]

    if "password_hash" not in columns:
        con.execute(
            "ALTER TABLE players ADD COLUMN password_hash TEXT"
        )

    # Winners table
    con.execute("""
        CREATE TABLE IF NOT EXISTS winners(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_uid TEXT NOT NULL,
            prize REAL NOT NULL,
            match_title TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.commit()
    return con


# Home Page
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
        count=total,
        rooms=rooms
    )


# Player Registration
@app.route("/register", methods=["GET", "POST"])
@app.route("/join", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        uid = request.form.get("uid", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not name or not uid or not phone or not password:
            flash("Please fill all details including password!")
            return redirect("/register")

        if len(password) < 8:
            flash("Password must be at least 8 characters!")
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

            password_hash = generate_password_hash(password)

            con.execute("""
                INSERT INTO players(name, uid, phone, password_hash)
                VALUES(?,?,?,?)
            """, (name, uid, phone, password_hash))

            con.commit()
            con.close()

            flash("Registration Successful! Please Login.")
            return redirect("/player/login")

        except sqlite3.IntegrityError:

            con.close()
            flash("This UID is Already Registered!")
            return redirect("/register")

    return render_template("register.html")


# Player Login
@app.route("/player/login", methods=["GET", "POST"])
def player_login():

    if request.method == "POST":

        uid = request.form.get("uid", "").strip()
        password = request.form.get("password", "")

        con = database()

        player = con.execute(
            "SELECT * FROM players WHERE uid=?",
            (uid,)
        ).fetchone()

        con.close()

        if player and player["password_hash"]:

            if check_password_hash(
                player["password_hash"], password
            ):

                session.clear()
                session["player_uid"] = player["uid"]

                return redirect("/player/dashboard")

        flash("Invalid UID or Password!")

    return render_template("player_login.html")


# Activate Old Player Account
@app.route("/player/activate", methods=["GET", "POST"])
def player_activate():

    if request.method == "POST":

        uid = request.form.get("uid", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not uid or not phone or not password:
            flash("Please fill all details!")
            return redirect("/player/activate")

        if len(password) < 8:
            flash("Password must be at least 8 characters!")
            return redirect("/player/activate")

        con = database()

        player = con.execute(
            "SELECT * FROM players WHERE uid=? AND phone=?",
            (uid, phone)
        ).fetchone()

        if not player:
            con.close()
            flash("UID or Mobile Number is incorrect!")
            return redirect("/player/activate")

        if player["password_hash"]:
            con.close()
            flash("Account already activated. Please Login.")
            return redirect("/player/login")

        password_hash = generate_password_hash(password)

        con.execute(
            "UPDATE players SET password_hash=? WHERE uid=?",
            (password_hash, uid)
        )

        con.commit()
        con.close()

        flash("Account Activated! Please Login.")
        return redirect("/player/login")

    return render_template("player_activate.html")


# Player Dashboard
@app.route("/player/dashboard")
def player_dashboard():

    if not session.get("player_uid"):
        return redirect("/player/login")

    uid = session["player_uid"]

    con = database()

    player = con.execute(
        "SELECT id, name, uid, phone FROM players WHERE uid=?",
        (uid,)
    ).fetchone()

    if not player:
        con.close()
        session.clear()
        return redirect("/player/login")

    rooms = con.execute(
        "SELECT * FROM rooms ORDER BY id DESC"
    ).fetchall()

    winnings = con.execute("""
        SELECT * FROM winners
        WHERE player_uid=?
        ORDER BY id DESC
    """, (uid,)).fetchall()

    total_winning = con.execute(
        "SELECT COALESCE(SUM(prize), 0) FROM winners WHERE player_uid=?",
        (uid,)
    ).fetchone()[0]

    con.close()

    return render_template(
        "player_dashboard.html",
        player=player,
        rooms=rooms,
        winnings=winnings,
        total_winning=total_winning
    )


# Admin Login
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:

            session.clear()
            session["admin"] = True

            return redirect("/dashboard")

        flash("Wrong Admin Password!")

    return render_template("login.html")


# Admin Dashboard
@app.route("/dashboard")
def dashboard():

    if not session.get("admin"):
        return redirect("/admin/login")

    con = database()

    # Do not expose password_hash to templates
    players = con.execute("""
        SELECT id, name, uid, phone
        FROM players
        ORDER BY id DESC
    """).fetchall()

    total = len(players)

    rooms = con.execute(
        "SELECT * FROM rooms ORDER BY id DESC"
    ).fetchall()

    winners = con.execute("""
        SELECT winners.*, players.name AS player_name
        FROM winners
        LEFT JOIN players ON winners.player_uid = players.uid
        ORDER BY winners.id DESC
    """).fetchall()

    con.close()

    return render_template(
        "dashboard.html",
        players=players,
        total=total,
        rooms=rooms,
        winners=winners
    )


# Add Match Room
@app.route("/add-room", methods=["POST"])
def add_room():

    if not session.get("admin"):
        return redirect("/admin/login")

    title = request.form.get("title", "").strip()
    match_time = request.form.get("match_time", "").strip()

    if title:

        con = database()

        con.execute(
            "INSERT INTO rooms(title, match_time) VALUES(?,?)",
            (title, match_time)
        )

        con.commit()
        con.close()

        flash("Room Added Successfully!")

    return redirect("/dashboard")


# Admin: View All Players
@app.route("/playerdata")
def playerdata():

    if not session.get("admin"):
        return redirect("/admin/login")

    con = database()

    players = con.execute("""
        SELECT id, name, uid, phone
        FROM players
        ORDER BY id DESC
    """).fetchall()

    con.close()

    return render_template(
        "playerdata.html",
        players=players
    )


# Admin: Add and View Winners
@app.route("/winningshow", methods=["GET", "POST"])
def winningshow():

    if not session.get("admin"):
        return redirect("/admin/login")

    con = database()

    if request.method == "POST":

        uid = request.form.get("uid", "").strip()
        prize_text = request.form.get("prize", "").strip()
        match_title = request.form.get("match_title", "").strip()

        try:
            prize = float(prize_text)
        except (ValueError, TypeError):
            prize = 0

        if not uid or not match_title or not math.isfinite(prize) or prize <= 0:
            con.close()
            flash("Please enter valid UID, Match and Prize!")
            return redirect("/winningshow")

        player = con.execute(
            "SELECT uid FROM players WHERE uid=?",
            (uid,)
        ).fetchone()

        if not player:
            con.close()
            flash("Player UID not found!")
            return redirect("/winningshow")

        con.execute("""
            INSERT INTO winners(player_uid, prize, match_title)
            VALUES(?,?,?)
        """, (uid, prize, match_title))

        con.commit()
        flash("Winner Added Successfully!")

    winners = con.execute("""
        SELECT winners.*, players.name AS player_name
        FROM winners
        LEFT JOIN players ON winners.player_uid = players.uid
        ORDER BY winners.id DESC
    """).fetchall()

    con.close()

    return render_template(
        "winningshow.html",
        winners=winners
    )


# Player Logout
@app.route("/player/logout")
def player_logout():

    session.clear()
    return redirect("/player/login")


# Admin Logout
@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


# Start App
if __name__ == "__main__":

    con = database()
    con.close()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )

