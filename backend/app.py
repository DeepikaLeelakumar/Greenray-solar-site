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
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        with sqlite3.connect("database/sites.db") as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Fetch user by username only
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cur.fetchone()

        if user:
            stored_pw = user["password"]

            # Try decrypting first (for new engineers)
            try:
                decrypted_pw = fernet.decrypt(stored_pw.encode()).decode()
            except:
                decrypted_pw = stored_pw  # fallback to plain text (old users)

            # Check password
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

    # ✅ Load engineers first so variable exists for both GET and POST
    with sqlite3.connect("database/sites.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE role='engineer'")
        engineers = cur.fetchall()

    if request.method == "POST":
        # Collect form data
        name = request.form["name"]
        address = request.form["address"]
        capacity = request.form["capacity"]
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        inverter_url = request.form["inverter_url"]
        type_val = request.form["type"]

        # Encrypt credentials
        enc_login = fernet.encrypt(request.form["login_id"].encode()).decode()
        enc_pass = fernet.encrypt(request.form["password"].encode()).decode()

        # Upload image to Cloudinary
        image_file = request.files.get("image_file")
        image_url = None
        if image_file:
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result["secure_url"]

        # ✅ You can insert the new site into DB here if needed
        with sqlite3.connect("database/sites.db") as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sites 
                (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, image_url) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, address, capacity, latitude, longitude, inverter_url, enc_login, enc_pass, type_val, image_url))
            conn.commit()

        return redirect("/admin/sites")

    # GET request
    return render_template("add_site.html", engineers=engineers)


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


@app.route("/admin/assign", methods=["GET", "POST"])
def assign_site():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect("database/sites.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if request.method == "POST":
            engineer_id = request.form["engineer_id"]
            site_id = request.form["site_id"]
            cur.execute("INSERT INTO engineer_sites (engineer_id, site_id) VALUES (?, ?)", 
                        (engineer_id, site_id))
            conn.commit()
            return redirect("/admin/assign")

        # Load engineers + sites for dropdown
        cur.execute("SELECT id, username FROM users WHERE role='engineer'")
        engineers = cur.fetchall()
        cur.execute("SELECT id, name FROM sites")
        sites = cur.fetchall()

    return render_template("assign_site.html", engineers=engineers, sites=sites)

@app.route("/admin/unassign/<int:site_id>", methods=["POST"])
def unassign_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect("database/sites.db") as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM engineer_sites WHERE site_id = ?", (site_id,))
        conn.commit()

    return redirect("/engineer")  # back to dashboard

@app.route("/admin/sites/edit/<int:site_id>", methods=["GET", "POST"])
def edit_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect("database/sites.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Fetch existing site
        cur.execute("SELECT * FROM sites WHERE id=?", (site_id,))
        row = cur.fetchone()
        if not row:
            return redirect("/admin/sites")  # Site not found

        if request.method == "POST":
            # Handle image upload
            image_file = request.files.get("image_file")
            image_url = row["image_url"]  # default: keep old one
            if image_file and getattr(image_file, "filename", ""):
                upload_result = cloudinary.uploader.upload(image_file)
                image_url = upload_result.get("secure_url")

            # Handle encrypted credentials
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

            # Preserve other fields (use DB value if blank)
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

            # Step 3: Update assigned engineer
            assigned_engineer_id = request.form.get("assigned_engineer")
            # Clear existing assignment
            cur.execute("DELETE FROM engineer_sites WHERE site_id=?", (site_id,))
            if assigned_engineer_id:
                cur.execute(
                    "INSERT INTO engineer_sites (engineer_id, site_id) VALUES (?, ?)",
                    (assigned_engineer_id, site_id)
                )
                conn.commit()

            return redirect("/admin/sites")

        # GET request: prepare site dict
        site = dict(row)
        site["login_id"] = safe_decrypt(site.get("login_id"))
        site["password"] = ""  # don’t prefill password

        # Fetch all engineers for dropdown
        cur.execute("SELECT id, username FROM users WHERE role='engineer'")
        engineers = cur.fetchall()

        # Fetch assigned engineer
        cur.execute("SELECT engineer_id FROM engineer_sites WHERE site_id=?", (site_id,))
        assigned_row = cur.fetchone()
        assigned_engineer_id = assigned_row[0] if assigned_row else None

    return render_template(
        "edit_site.html",
        site=site,
        engineers=engineers,
        assigned_engineer_id=assigned_engineer_id
    )



@app.route("/admin/sites/delete/<int:site_id>")
def delete_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect("database/sites.db") as conn:
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

    # Encrypt password
    enc_password = fernet.encrypt(password.encode()).decode()

    with sqlite3.connect('database/sites.db') as conn:
        cur = conn.cursor()
        # Check if username exists
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            flash(f"⚠ Engineer '{username}' already exists!", "error")
            return redirect(url_for('show_add_engineer_form'))

        # Insert engineer
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, enc_password, "engineer")
        )
        conn.commit()

    flash(f"✅ Engineer '{username}' added successfully!", "success")
    return redirect(url_for('view_engineers'))


@app.route('/admin/engineers')
def view_engineers():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    with sqlite3.connect('database/sites.db') as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE role='engineer'")
        engineers = cur.fetchall()

    # Decrypt passwords for display
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

    with sqlite3.connect('database/sites.db') as conn:
        cur = conn.cursor()
        # Remove assignments first
        cur.execute("DELETE FROM engineer_sites WHERE engineer_id=?", (engineer_id,))
        # Delete engineer
        cur.execute("DELETE FROM users WHERE id=?", (engineer_id,))
        conn.commit()

    flash("✅ Engineer deleted successfully!", "success")
    return redirect(url_for('view_engineers'))





# --- Add Assign Sites to Engineer ---
@app.route('/assign_site', methods=["GET", "POST"])
def show_assign_plants_form():
    conn = sqlite3.connect('database/sites.db')
    cursor = conn.cursor()
    
    # Fetch all engineers
    cursor.execute("SELECT id, username FROM users WHERE role=?", ("engineer",))
    engineers = cursor.fetchall()
    
    # Fetch all sites
    cursor.execute("SELECT id, name FROM sites")
    sites = cursor.fetchall()
    
    conn.close()
    
    return render_template('assign_site.html', engineers=engineers, sites=sites)


@app.route('/assign', methods=['GET', 'POST'])
def assign_plants():
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database/sites.db")
    cur = conn.cursor()

    if request.method == 'POST':
        engineer_id = int(request.form['engineer_id'])
        site_ids = [int(sid) for sid in request.form.getlist('site_id')]

        # Delete old assignments for this engineer
        cur.execute("DELETE FROM engineer_sites WHERE engineer_id=?", (engineer_id,))

        # Insert new assignments
        for sid in site_ids:
            cur.execute(
                "INSERT INTO engineer_sites (engineer_id, site_id) VALUES (?, ?)",
                (engineer_id, sid)
            )
        conn.commit()
        conn.close()

        flash(f"🌱 Successfully assigned {len(site_ids)} site(s) to engineer!", "success")

        # Redirect to admin view for this engineer
        return redirect(url_for('engineer_dashboard_for_admin', engineer_id=engineer_id))

    # GET request: load engineers + sites
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
    
    engineer_id = session["id"]  # Current engineer's ID

    with sqlite3.connect("database/sites.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Only fetch sites assigned to this engineer
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
