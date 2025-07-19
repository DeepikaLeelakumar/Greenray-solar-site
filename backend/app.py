from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "greeenray@secure"

# 1. Home redirects to login
@app.route("/")
def home():
    return redirect("/login")

# 2. Login logic for both Admin & Engineer
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
            session["role"] = user[3]  # role column assumed at index 3
            if session["role"] == "admin":
                return redirect("/admin")
            elif session["role"] == "engineer":
                return redirect("/engineer")
        else:
            error = "Invalid Credentials"

    return render_template("login.html", error=error)

# 3. Admin Dashboard
@app.route("/admin")
def admin_dashboard():
    if "user" in session and session["role"] == "admin":
        return render_template("admin_panel.html")
    return redirect("/login")

# 4. Add New Site
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
        login_id = request.form["login_id"]
        password = request.form["password"]
        type = request.form["type"]

        try:
            with sqlite3.connect("database/sites.db", timeout=10) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO sites 
                    (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type))
                conn.commit()
        except sqlite3.OperationalError as e:
            print("🔴 SQLite error:", e)
            return "Database is currently busy. Please try again later.", 500

        return redirect("/admin/sites")

    return render_template("add_site.html")

# 5. View All Sites (Admin)
@app.route("/admin/sites")
def view_sites():
    if "user" in session and session["role"] == "admin":
        conn = sqlite3.connect("database/sites.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM sites")
        rows = cur.fetchall()
        conn.close()
        return render_template("admin_sites.html", sites=rows)
    return redirect("/login")

# 6. Edit Site
@app.route("/admin/sites/edit/<int:site_id>", methods=["GET", "POST"])
def edit_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database/sites.db")
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        address = request.form["address"]
        capacity = request.form["capacity"]
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        inverter_url = request.form["inverter_url"]
        login_id = request.form["login_id"]
        password = request.form["password"]
        type = request.form["type"]

        cur.execute("""
            UPDATE sites SET 
            name=?, address=?, capacity=?, latitude=?, longitude=?, 
            inverter_url=?, login_id=?, password=?, type=? 
            WHERE id=?
        """, (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, site_id))
        conn.commit()
        conn.close()
        return redirect("/admin/sites")

    # For GET: Load existing data
    cur.execute("SELECT * FROM sites WHERE id=?", (site_id,))
    site = cur.fetchone()
    conn.close()
    return render_template("edit_site.html", site=site)

# 7. Delete Site
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

# 8. Engineer Dashboard
@app.route("/engineer")
def engineer_dashboard():
    if "user" in session and session["role"] == "engineer":
        return render_template("engineer_map.html")
    return redirect("/login")

# 9. Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# Run the Flask app
if __name__ == "__main__":
    print("✅ Flask app is running at http://127.0.0.1:5000")
    app.run(debug=True)
