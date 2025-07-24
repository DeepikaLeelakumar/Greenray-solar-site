from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "greeenray@secure"

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
            if session["role"] == "admin":
                return redirect("/admin")
            elif session["role"] == "engineer":
                return redirect("/engineer")
        else:
            error = "Invalid Credentials"

    return render_template("login.html", error=error)

# --- Admin Dashboard ---
@app.route("/admin")
def admin_dashboard():
    if "user" in session and session["role"] == "admin":
        return render_template("admin_panel.html")
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
        login_id = request.form["login_id"]
        password = request.form["password"]
        type = request.form["type"]
        image_url = request.form.get("image_url")  # Optional

        with sqlite3.connect("database/sites.db", timeout=10) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sites 
                (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, address, capacity, latitude, longitude, inverter_url, login_id, password, type, image_url))
            conn.commit()

        return redirect("/admin/sites")

    return render_template("add_site.html")

# --- View Sites ---
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

# --- Edit Site ---
@app.route("/admin/sites/edit/<int:site_id>", methods=["GET", "POST"])
def edit_site(site_id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database/sites.db")
    cur = conn.cursor()

    if request.method == "POST":
        data = (
            request.form["name"],
            request.form["address"],
            request.form["capacity"],
            request.form["latitude"],
            request.form["longitude"],
            request.form["inverter_url"],
            request.form["login_id"],
            request.form["password"],
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
        return render_template("engineer_map.html")
    return redirect("/login")

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
