from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
from cryptography.fernet import Fernet


app = Flask(__name__)
app.secret_key = "greeenray@secure"

def load_key():
    if not os.path.exists("secret_key"):
        key = Fernet.generate_key()
        with open("secret_key", "wb") as key_file:
            key_file.write(key)
        print("✅ secret_key file created successfully.")
    return open("secret_key","rb").read()

fernet_key = load_key()
fernet = Fernet(fernet_key)

def safe_decrypt(value):
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception as e:
        print(f"DEBUG: safe_decrypt failed with error: {e}")
        return value


# --- Static and Homepage ---
@app.route("/index.html")
def index_page():
    return render_template("index.html")

@app.route("/")
def home():
    return redirect("/index.html")

# --- Login ---
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database/sites.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = username
            session["role"] = user[3]
            session["id"] = user[0] 
            if session["role"] == "admin":
                # Redirect to the working view_sites page
                return redirect(url_for('view_sites'))
            elif session["role"] == "engineer":
                return redirect("/engineer")
        else:
            error = "Invalid Credentials"

    return render_template("login.html", error=error)

# --- Admin Dashboard ---
# This function is no longer needed, as the login redirects directly to view_sites.
# I'm keeping it as a redirect to handle any other links that might point here.
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

    if request.method == "POST":
        name = request.form["name"]
        address = request.form["address"]
        capacity = request.form["capacity"]
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        inverter_url = request.form["inverter_url"]

        
        # ✅ Encrypt credentials 
        login_id = request.form["login_id"]
        password = request.form["password"]
        enc_login = fernet.encrypt(login_id.encode()).decode()
        enc_pass = fernet.encrypt(password.encode()).decode()

        # 🔒 ADD THIS CHECK HERE ✅ 
        if not enc_login.startswith("gAAAA"):
            return "Encryption failed for login_id ❌"
        if not enc_pass.startswith("gAAAA"):
            return "Encryption failed for password ❌"

        type = request.form["type"]
        image_url = request.form["image_url"]
        
            

        conn = sqlite3.connect("database/sites.db") 
        cur = conn.cursor()
        cur.execute("""
                INSERT INTO sites 
                (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, address, capacity, latitude, longitude, inverter_url, enc_login, enc_pass, type, image_url))
        conn.commit()
        conn.close()

        return redirect("/admin/sites")

    return render_template("add_site.html")


# --- View Sites (This is the correct function) ---
@app.route("/admin/sites")
def view_sites():
    if "user" in session and session["role"] == "admin":
        conn = sqlite3.connect("database/sites.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM sites")
        rows = cur.fetchall()
        conn.close()

        # Decrypt login & password safely
        decrypted_sites = []
        for row in rows:
            decrypted_row = list(row)
            decrypted_row[7] = safe_decrypt(row[7])  # login_id
            decrypted_row[8] = safe_decrypt(row[8])  # password
            decrypted_sites.append(decrypted_row)

        return render_template("admin_sites.html", sites=decrypted_sites)

    return redirect("/login")

# --- Edit Site ---
@app.route("/admin/sites/edit/<int:site_id>", methods=["GET", "POST"])
def edit_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database/sites.db")
    cur = conn.cursor()

    if request.method == "POST":
        # 🔒 Encrypt updated credentials
        login_id = request.form["login_id"]
        password = request.form["password"]
        enc_login = fernet.encrypt(login_id.encode()).decode()
        enc_pass = fernet.encrypt(password.encode()).decode()

        # ✅ Validate encryption
        if not enc_login.startswith("gAAAA"):
            return "Encryption failed for login_id ❌"
        if not enc_pass.startswith("gAAAA"):
            return "Encryption failed for password ❌"
        
        data = (
            request.form["name"],
            request.form["address"],
            request.form["capacity"],
            request.form["latitude"],
            request.form["longitude"],
            request.form["inverter_url"],
            enc_login,
            enc_pass,
            request.form["type"],
            request.form.get("image_url"),
            site_id
        )
        cur.execute("""
            UPDATE sites SET 
            name=?, address=?, capacity=?, latitude=?, longitude=?, 
            inverter_url=?, login_id=?, password=?, type=?, image_url=? 
            WHERE id=?
        """, data)
        conn.commit()
        conn.close()
        return redirect("/admin/sites")

    cur.execute("SELECT * FROM sites WHERE id=?", (site_id,))
    site = cur.fetchone()
    conn.close()
    return render_template("edit_site.html", site=site)
    
# --- Delete Site ---
@app.route("/admin/sites/delete/<int:site_id>")
def delete_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database/sites.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM sites WHERE id=?", (site_id,))
    conn.commit()
    conn.close()
    return redirect("/admin/sites")

# --- Logout ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# --- Engineer Dashboard ---
@app.route("/engineer")
def engineer_dashboard():
    if "user" in session and session["role"] == "engineer":
        print("✅ Accessing engineer dashboard.")

        conn = sqlite3.connect("database/sites.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM sites")
        rows = cur.fetchall()
        conn.close()

        sites = []
        for row in rows:
            site = dict(row)
            print(f"--- Processing Site ID: {site['id']} ---")
            
            # Print the original, encrypted data
            print(f"Encrypted Login ID: {site['login_id']}")
            print(f"Encrypted Password: {site['password']}")
            
            try:
                # Attempt to decrypt and store the result
                decrypted_login_id = safe_decrypt(site["login_id"])
                decrypted_password = safe_decrypt(site["password"])
                
                # Check if decryption was successful
                if decrypted_login_id == site["login_id"]:
                    print("❌ Decryption FAILED for Login ID.")
                else:
                    print("✅ Decryption SUCCESSFUL for Login ID.")
                    site["login_id"] = decrypted_login_id
                    
                if decrypted_password == site["password"]:
                    print("❌ Decryption FAILED for Password.")
                else:
                    print("✅ Decryption SUCCESSFUL for Password.")
                    site["password"] = decrypted_password
                
            except Exception as e:
                print(f"❌ An unexpected error occurred during decryption: {e}")
                site["login_id"] = "Decryption Failed"
                site["password"] = "Decryption Failed"

            if site['image_url']:
                 if site['image_url'].startswith('http'):
        # It's an external image URL (e.g., Imgur, Google Drive)
                   site['image_url'] = site['image_url']
                 else:
                   site['image_url'] = url_for('static', filename=f'assests/{site["image_url"]}')
            else:
                site['image_url'] = None

            sites.append(site)
            print("---------------------------------")

        return render_template("engineer_dashboard.html", sites=sites)
    
    print("❌ Unauthorized access attempt to engineer dashboard.")
    return redirect("/login")

# ... (Also, let's update your safe_decrypt to provide more info if it fails)
def safe_decrypt(value):
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception as e:
        print(f"DEBUG: safe_decrypt failed with error: {e}")
        return value


@app.route("/get_credentials/<int:site_id>")
def get_credentials(site_id):
    conn = sqlite3.connect("database/sites.db")
    cur = conn.cursor()
    cur.execute("SELECT login_id, password FROM sites WHERE id = ?", (site_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        decrypted_username = fernet.decrypt(row[0].encode()).decode()
        decrypted_password = fernet.decrypt(row[1].encode()).decode()
        return jsonify({
            "username": decrypted_username,
            "password": decrypted_password
        })
    return jsonify({"error": "Site not found"}), 404


@app.route("/api/sites")
def get_sites():
    try:
        conn = sqlite3.connect("database/sites.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM sites")
        rows = cur.fetchall()
        conn.close()

        sites = []
        for row in rows:
            
                sites.append({
                    "id": row[0],
                    "name": row[1],
                    "address": row[2],
                    "capacity": row[3],
                    "latitude": row[4],
                    "longitude": row[5],
                    "inverter_url": row[6],
                    "login_id": row[7],
                    "password": row[8],
                    "type": row[9],
                    "image_url": row[10]
                })
            

        return jsonify({"sites": sites})

    except Exception as e:
        print("❌ API Error:", e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500



# --- Run the App ---
if __name__ == "__main__":
    app.run(debug=True)