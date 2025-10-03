# ...existing code...
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import os
from cryptography.fernet import Fernet
import cloudinary
import cloudinary.uploader
import cloudinary.api
import random, string



def generate_password(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# ===== CHANGED: base paths + env-based secrets =====
BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "sites.db")
os.makedirs(DB_DIR, exist_ok=True)

# Cloudinary config (load from environment variables)
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "greeenray@secure"

# ------------------ ENCRYPTION ------------------

def load_key():
    """Load Fernet key from env or file (creates file if missing)."""
    # 1) environment variable (recommended on server)
    env_key = os.environ.get("FERNET_SECRET")
    if env_key:
        # assume base64 urlsafe string
        return env_key.encode()

    # 2) file next to this script
    key_path = os.path.join(BASE_DIR, "secret_key")
    if not os.path.exists(key_path):
        key = Fernet.generate_key()
        with open(key_path, "wb") as key_file:
            key_file.write(key)
        print("✅ secret_key file created at", key_path)
    return open(key_path, "rb").read()

fernet_key = load_key()
fernet = Fernet(fernet_key)

def safe_decrypt(value):
    """Safely decrypt values and return original on failure."""
    if not value:
        return value
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception as e:
        print(f"❌ Decrypt failed: {e}")
        return value  # fallback (show encrypted or plain string)

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
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cur.fetchone()

        if user:
            stored_pw = user["password"]
            # Try decrypting first
            try:
                decrypted_pw = fernet.decrypt(stored_pw.encode()).decode()
            except Exception:
                decrypted_pw = stored_pw  # fallback

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

    # Load engineers first so variable exists for both GET and POST
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

        enc_login = fernet.encrypt(request.form["login_id"].encode()).decode()
        enc_pass = fernet.encrypt(request.form["password"].encode()).decode()

        image_file = request.files.get("image_file")
        image_url = None
        if image_file and getattr(image_file, "filename", ""):
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result.get("secure_url")

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sites 
                (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, image_url) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, address, capacity, latitude, longitude, inverter_url, enc_login, enc_pass, type_val, image_url))
            conn.commit()

        return redirect("/admin/sites")

    return render_template("add_site.html", engineers=engineers)

@app.route("/admin/sites")
def view_sites():
    if "user" in session and session["role"] == "admin":
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
            s["image_url"] = s.get("image_url") if (s.get("image_url") and s.get("image_url").startswith("http")) else None
            sites.append(s)

        return render_template("admin_sites.html", sites=sites)

    return redirect("/login")

@app.route("/admin/assign", methods=["GET", "POST"])
def assign_site():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if request.method == "POST":
            engineer_id = request.form["engineer_id"]
            site_id = request.form["site_id"]
            cur.execute("INSERT INTO engineer_sites (engineer_id, site_id) VALUES (?, ?)", (engineer_id, site_id))
            conn.commit()
            return redirect("/admin/assign")

        cur.execute("SELECT id, username FROM users WHERE role='engineer'")
        engineers = cur.fetchall()
        cur.execute("SELECT id, name FROM sites")
        sites = cur.fetchall()

    return render_template("assign_site.html", engineers=engineers, sites=sites)

@app.route("/admin/unassign/<int:site_id>", methods=["POST"])
def unassign_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM engineer_sites WHERE site_id = ?", (site_id,))
        conn.commit()

    return redirect("/engineer")

@app.route("/admin/sites/edit/<int:site_id>", methods=["GET", "POST"])
def edit_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM sites WHERE id=?", (site_id,))
        row = cur.fetchone()
        if not row:
            return redirect("/admin/sites")

        if request.method == "POST":
            image_file = request.files.get("image_file")
            image_url = row["image_url"]
            if image_file and getattr(image_file, "filename", ""):
                upload_result = cloudinary.uploader.upload(image_file)
                image_url = upload_result.get("secure_url")

            new_login_raw = request.form.get("login_id", "").strip()
            new_pass_raw = request.form.get("password", "").strip()

            if new_login_raw:
                enc_login = fernet.encrypt(new_login_raw.encode()).decode()
            else:
                enc_login = row["login_id"]

            if new_pass_raw:
                enc_pass = fernet.encrypt(new_pass_raw.encode()).decode()
            else:
                enc_pass = row["password"]

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

            assigned_engineer_id = request.form.get("assigned_engineer")
            cur.execute("DELETE FROM engineer_sites WHERE site_id=?", (site_id,))
            if assigned_engineer_id:
                cur.execute("INSERT INTO engineer_sites (engineer_id, site_id) VALUES (?, ?)", (assigned_engineer_id, site_id))
                conn.commit()

            return redirect("/admin/sites")

        site = dict(row)
        site["login_id"] = safe_decrypt(site.get("login_id"))
        site["password"] = ""  # don't prefill password

        cur.execute("SELECT id, username FROM users WHERE role='engineer'")
        engineers = cur.fetchall()

        cur.execute("SELECT engineer_id FROM engineer_sites WHERE site_id=?", (site_id,))
        assigned_row = cur.fetchone()
        assigned_engineer_id = assigned_row[0] if assigned_row else None

    return render_template("edit_site.html", site=site, engineers=engineers, assigned_engineer_id=assigned_engineer_id)

@app.route("/admin/sites/delete/<int:site_id>")
def delete_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sites WHERE id=?", (site_id,))
        conn.commit()

    return redirect("/admin/sites")

@app.route('/admin/add_engineer')
def show_add_engineer_form():
    return render_template('admin_add_engineer.html')

@app.route('/admin/add_engineer', methods=['POST'])
def add_engineer_post():
    username = request.form['username']
    password = request.form['password']

    enc_password = fernet.encrypt(password.encode()).decode()

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            flash(f"⚠ Engineer '{username}' already exists!", "error")
            return redirect(url_for('show_add_engineer_form'))

        cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, enc_password, "engineer"))
        conn.commit()

    flash(f"✅ Engineer '{username}' added successfully!", "success")
    return redirect(url_for('view_engineers'))

@app.route('/admin/engineers')
def view_engineers():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE role='engineer'")
        engineers = cur.fetchall()

    engineers_list = []
    for eng in engineers:
        decrypted_pw = safe_decrypt(eng['password'])
        engineers_list.append({
            "id": eng["id"],
            "username": eng["username"],
            "password": decrypted_pw
        })

    return render_template('admin_engineers.html', engineers=engineers_list)

@app.route('/admin/delete_engineer/<int:engineer_id>')
def delete_engineer(engineer_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM engineer_sites WHERE engineer_id=?", (engineer_id,))
        cur.execute("DELETE FROM users WHERE id=?", (engineer_id,))
        conn.commit()

    flash("✅ Engineer deleted successfully!", "success")
    return redirect(url_for('view_engineers'))

# --- Assign sites to engineer (form)
@app.route('/assign_site', methods=["GET", "POST"])
def show_assign_plants_form():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE role=?", ("engineer",))
        engineers = cur.fetchall()
        cur.execute("SELECT id, name FROM sites")
        sites = cur.fetchall()

    return render_template('assign_site.html', engineers=engineers, sites=sites)

@app.route('/assign', methods=['GET', 'POST'])
def assign_plants():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if request.method == 'POST':
        engineer_id = int(request.form['engineer_id'])
        site_ids = [int(sid) for sid in request.form.getlist('site_id')]

        if not site_ids:
            flash("⚠ Please select at least one site!", "error")
            return redirect(url_for('assign_plants'))

        # Remove previous assignments
        cur.execute("DELETE FROM engineer_sites WHERE engineer_id=?", (engineer_id,))
        for sid in site_ids:
            cur.execute("INSERT INTO engineer_sites (engineer_id, site_id) VALUES (?, ?)", (engineer_id, sid))
        conn.commit()
        conn.close()

        flash(f"🌱 Successfully assigned {len(site_ids)} site(s) to engineer!", "success")
        return redirect(url_for('assign_plants'))

    # GET: show form
    cur.execute("SELECT id, username FROM users WHERE role='engineer'")
    engineers = cur.fetchall()
    cur.execute("SELECT id, name FROM sites")
    sites = cur.fetchall()
    conn.close()
    return render_template("assign_site.html", engineers=engineers, sites=sites)

# ------------------ ENGINEER ------------------
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

# ------------------ API ------------------
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

# ------------------ RUN ------------------
if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
# ...existing code...