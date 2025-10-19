from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import os
from cryptography.fernet import Fernet
import cloudinary
import cloudinary.uploader
import cloudinary.api
import random, string

# -------------------------
# Password generator
# -------------------------
def generate_password(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# -------------------------
# 1️⃣ SECRET_KEY (Flask sessions)
# -------------------------
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise Exception("⚠ SECRET_KEY not set! Add it in Railway Shared Variables.")

# -------------------------
# 2️⃣ FERNET_KEY (encrypt/decrypt credentials)
# -------------------------
FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    raise Exception("⚠ FERNET_KEY not set! Add it in Railway Shared Variables.")

fernet = Fernet(FERNET_KEY.encode())

# -------------------------
# 3️⃣ Flask App
# -------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY

# -------------------------
# 4️⃣ Fernet helpers
# -------------------------
def encrypt_password(password: str) -> str:
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()

def safe_decrypt(value):
    """Safely decrypt a value; returns original if decryption fails."""
    if not value:
        return ""
    try:
        return fernet.decrypt(value.encode()).decode()
    except:
        return value

# -------------------------
# 5️⃣ Cloudinary config
# -------------------------
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL")
if not CLOUDINARY_URL:
    raise Exception("⚠ CLOUDINARY_URL not set! Add it to Railway Shared Variables.")
cloudinary.config(cloudinary_url=CLOUDINARY_URL)

# -------------------------
# 6️⃣ Database path
# -------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "sites.db")

# -------------------------
# Routes
# -------------------------

# --- Homepage ---
@app.route("/")
def home():
    return redirect("/index.html")

@app.route("/index.html")
def index_page():
    return render_template("index.html")

# --- Login ---
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cur.fetchone()

        if user:
            stored_pw = user["password"]
            try:
                decrypted_pw = fernet.decrypt(stored_pw.encode()).decode()
            except:
                decrypted_pw = stored_pw

            if password == decrypted_pw:
                session["user"] = username
                session["role"] = user["role"]
                session["id"] = user["id"]

                if user["role"] == "admin":
                    return redirect(url_for("view_sites"))
                elif user["role"] == "engineer":
                    return redirect("/engineer")
            else:
                error = "Invalid Credentials ❌"
        else:
            error = "Invalid Credentials ❌"

    return render_template("login.html", error=error)

# --- Logout ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# --- Admin Dashboard ---
@app.route("/admin")
def admin_dashboard():
    if "user" in session and session["role"] == "admin":
        return redirect(url_for('view_sites'))
    return redirect("/login")

# --- Add Site ---
@app.route("/add-site", methods=["GET", "POST"])
def add_site():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE role='engineer'")
        engineers = cur.fetchall()

    if request.method == "POST":
        name = request.form["name"]
        address = request.form["address"]
        capacity = request.form["capacity"]
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        inverter_url = request.form["inverter_url"]
        type_val = request.form["type"]

        enc_login = encrypt_password(request.form["login_id"])
        enc_pass = encrypt_password(request.form["password"])

        image_file = request.files.get("image_file")
        image_url = None
        if image_file and getattr(image_file, "filename", ""):
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result["secure_url"]

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sites 
                (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, image_url) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, address, capacity, latitude, longitude, inverter_url, enc_login, enc_pass, type_val, image_url))
            conn.commit()

        return redirect("/admin/sites")

    return render_template("add_site.html", engineers=engineers)

# --- View Sites ---
@app.route("/admin/sites")
def view_sites():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM sites")
        rows = cur.fetchall()

    sites = []
    for row in rows:
        s = dict(row)
        s["login_id"] = safe_decrypt(s.get("login_id"))
        s["password"] = safe_decrypt(s.get("password"))
        s["image_url"] = s.get("image_url") if s.get("image_url") and s.get("image_url").startswith("http") else None
        sites.append(s)

    return render_template("admin_sites.html", sites=sites)

# --- Engineer Dashboard ---
@app.route("/engineer")
def engineer_dashboard():
    if "user" not in session or session["role"] != "engineer":
        return redirect("/login")

    engineer_id = session["id"]
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT s.*
            FROM sites s
            JOIN engineer_sites es ON s.id = es.site_id
            WHERE es.engineer_id = ?
        """, (engineer_id,))
        rows = cur.fetchall()

    sites = []
    for row in rows:
        site = dict(row)
        site["login_id"] = safe_decrypt(site.get("login_id"))
        site["password"] = safe_decrypt(site.get("password"))
        site["image_url"] = site.get("image_url") if site.get("image_url") and site.get("image_url").startswith("http") else None
        sites.append(site)

    return render_template("engineer_dashboard.html", sites=sites, role="engineer")

# --- API ---
@app.route("/api/sites")
def get_sites():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sites")
            rows = cur.fetchall()
        sites = [dict(row) for row in rows]
        return jsonify({"sites": sites})
    except Exception as e:
        print("❌ API Error:", e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# --- Run ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)