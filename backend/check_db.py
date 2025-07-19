import sqlite3
import os

# ✅ Create 'database' folder if it doesn't exist
os.makedirs("database", exist_ok=True)

# ✅ Create or connect to sites.db
conn = sqlite3.connect("database/sites.db")
cur = conn.cursor()

# ✅ Create 'sites' table
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
    password TEXT
)
""")

conn.commit()
conn.close()

print("✅ Database and table created successfully!")
