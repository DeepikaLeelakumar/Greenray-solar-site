from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
from cryptography.fernet import Fernet
import cloudinary
import cloudinary.uploader
import cloudinary.api

# ------------------ CONFIG ------------------

# Cloudinary config
cloudinary.config(
    cloud_name="dptibaupg",
    api_key="247993645571145",
    api_secret="xmlSvgLNc9TpaR_dk7KttQPBL68"
)

app = Flask(__name__)
app.secret_key = "greeenray@secure"

# ------------------ ENCRYPTION ------------------

def load_key():
    """Load Fernet key from file or generate a new one."""
    if not os.path.exists("secret_key"):
        key = Fernet.generate_key()
        with open("secret_key", "wb") as key_file:
            key_file.write(key)
        print("✅ secret_key file created successfully.")
    return open("secret_key", "rb").read()

fernet_key = load_key()
fernet = Fernet(fernet_key)

def safe_decrypt(value):
    """Safely decrypt values and log failures."""
    if not value:
        return value
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception as e:
        print(f"❌ Decrypt failed: {e}")
        return value  # fallback (encrypted string shown)

# ------------------ ROUTES ------------------

# --- Static and Homepage ---
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
        username = request.form["username"]
        password = request.form["password"]

        with sqlite3.connect("database/sites.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            user = cur.fetchone()

        if user:
            session["user"] = username
            session["role"] = user[3]
            session["id"] = user[0]

            if session["role"] == "admin":
                return redirect(url_for('view_sites'))
            elif session["role"] == "engineer":
                return redirect("/engineer")
        else:
            error = "Invalid Credentials ❌"

    return render_template("login.html", error=error)

# --- Logout ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ------------------ ADMIN ------------------

@app.route("/admin")
def admin_dashboard():
    if "user" in session and session["role"] == "admin":
        return redirect(url_for('view_sites'))
    return redirect("/login")
@app.route("/add-site", methods=["GET", "POST"])
def add_site():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    if request.method == "POST":
        # Collect form data
        name = request.form["name"]
        address = request.form["address"]
        capacity = request.form["capacity"]
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        inverter_url = request.form["inverter_url"]
        type = request.form["type"]

        # Encrypt credentials
        enc_login = fernet.encrypt(request.form["login_id"].encode()).decode()
        enc_pass = fernet.encrypt(request.form["password"].encode()).decode()

        # Upload image to Cloudinary
        image_file = request.files.get("image_file")
        image_url = None
        if image_file:
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result["secure_url"]

        with sqlite3.connect("database/sites.db") as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sites
                (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, address, capacity, latitude, longitude, inverter_url,
                  enc_login, enc_pass, type, image_url))
            conn.commit()

        return redirect("/admin/sites")

    return render_template("add_site.html")

@app.route("/admin/sites")
def view_sites():
    if "user" in session and session["role"] == "admin":
        with sqlite3.connect("database/sites.db") as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sites")
            rows = cur.fetchall()

        sites = []
        for row in rows:
            s = dict(row)
            s["login_id"] = safe_decrypt(s.get("login_id"))
            s["password"] = safe_decrypt(s.get("password"))
            # keep image_url as-is or None
            s["image_url"] = s.get("image_url") if (s.get("image_url") and s.get("image_url").startswith("http")) else None
            sites.append(s)

        return render_template("admin_sites.html", sites=sites)

    return redirect("/login")


@app.route("/admin/sites/edit/<int:site_id>", methods=["GET", "POST"])
def edit_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect("database/sites.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Fetch existing row
        cur.execute("SELECT * FROM sites WHERE id=?", (site_id,))
        row = cur.fetchone()
        if not row:
            return redirect("/admin/sites")  # or flash("Site not found")

        if request.method == "POST":
            # ✅ Handle image upload
            image_file = request.files.get("image_file")
            image_url = row["image_url"]  # default: keep old one
            if image_file and getattr(image_file, "filename", ""):
                upload_result = cloudinary.uploader.upload(image_file)
                image_url = upload_result.get("secure_url")

            # ✅ Handle encrypted credentials
            new_login_raw = request.form.get("login_id", "").strip()
            new_pass_raw = request.form.get("password", "").strip()

            if new_login_raw:
                enc_login = fernet.encrypt(new_login_raw.encode()).decode()
            else:
                enc_login = row["login_id"]  # keep old

            if new_pass_raw:
                enc_pass = fernet.encrypt(new_pass_raw.encode()).decode()
            else:
                enc_pass = row["password"]  # keep old

            # ✅ Preserve other fields (if blank, use DB value)
            def get_or_keep(field):
                val = request.form.get(field, "").strip()
                return val if val else row[field]

            name = get_or_keep("name")
            address = get_or_keep("address")
            capacity = get_or_keep("capacity")
            latitude = get_or_keep("latitude")
            longitude = get_or_keep("longitude")
            inverter_url = get_or_keep("inverter_url")
            type_val = get_or_keep("type")

            data = (
                name, address, capacity, latitude, longitude,
                inverter_url, enc_login, enc_pass, type_val, image_url, site_id
            )

            cur.execute("""
                UPDATE sites SET
                name=?, address=?, capacity=?, latitude=?, longitude=?,
                inverter_url=?, login_id=?, password=?, type=?, image_url=?
                WHERE id=?
            """, data)
            conn.commit()
            return redirect("/admin/sites")

        # ✅ GET request: prepare site dict with decrypted values
        site = dict(row)
        site["login_id"] = safe_decrypt(site.get("login_id"))
        site["password"] = ""  # ⚠ don’t prefill password for security

    return render_template("edit_site.html", site=site)


@app.route("/admin/sites/delete/<int:site_id>")
def delete_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect("database/sites.db") as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sites WHERE id=?", (site_id,))
        conn.commit()

    return redirect("/admin/sites")

# ------------------ ENGINEER ------------------

@app.route("/engineer")
def engineer_dashboard():
    if "user" not in session or session["role"] != "engineer":
        print("❌ Unauthorized access attempt to engineer dashboard.")
        return redirect("/login")

    with sqlite3.connect("database/sites.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM sites")
        rows = cur.fetchall()

    sites = []
    for row in rows:
        site = dict(row)

        # Decrypt credentials
        site["login_id"] = safe_decrypt(site["login_id"])
        site["password"] = safe_decrypt(site["password"])

        # Ensure Cloudinary/public image URL
        site["image_url"] = site["image_url"] if (site["image_url"] and site["image_url"].startswith("http")) else None

        sites.append(site)

    return render_template("engineer_dashboard.html", sites=sites)

@app.route("/get_credentials/<int:site_id>")
def get_credentials(site_id):
    with sqlite3.connect("database/sites.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT login_id, password FROM sites WHERE id=?", (site_id,))
        row = cur.fetchone()

    if row:
        return jsonify({
            "username": safe_decrypt(row[0]),
            "password": safe_decrypt(row[1])
        })
    return jsonify({"error": "Site not found"}), 404

# ------------------ API ------------------

@app.route("/api/sites")
def get_sites():
    try:
        with sqlite3.connect("database/sites.db") as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sites")
            rows = cur.fetchall()

        sites = [dict(row) for row in rows]
        return jsonify({"sites": sites})

    except Exception as e:
        print("❌ API Error:", e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# ------------------ RUN ------------------
if __name__ == "__main__":
    app.run(debug=True)
