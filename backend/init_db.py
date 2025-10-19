import os
import sqlite3
from getpass import getpass
from cryptography.fernet import Fernet

BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "sites.db")
os.makedirs(DB_DIR, exist_ok=True)

def load_key():
    env_key = os.environ.get("FERNET_SECRET")
    if env_key:
        return env_key.encode()
    key_path = os.path.join(BASE_DIR, "secret_key")
    if not os.path.exists(key_path):
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        print("Created secret_key at", key_path)
    return open(key_path, "rb").read()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        address TEXT,
        capacity TEXT,
        latitude TEXT,
        longitude TEXT,
        inverter_url TEXT,
        login_id TEXT,
        password TEXT,
        type TEXT,
        image_url TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS engineer_sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engineer_id INTEGER,
        site_id INTEGER
    );
    """)
    conn.commit()
    conn.close()
    print("Initialized DB at", DB_PATH)

def create_admin():
    key = load_key()
    f = Fernet(key)
    username = input("Admin username [admin]: ").strip() or "admin"
    password = getpass("Admin password: ").strip()
    if not password:
        print("Password required. Aborting.")
        return
    enc = f.encrypt(password.encode()).decode()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=?", (username,))
    if cur.fetchone():
        print("User exists, skipping insert.")
    else:
        cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, enc, "admin"))
        conn.commit()
        print("Admin user created:", username)
    conn.close()

if __name__ == "__main__":
    init_db()
    create_admin()