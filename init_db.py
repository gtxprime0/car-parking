import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join('data', 'user.db')

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Delete the old DB file to ensure a clean slate
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# USERS TABLE (no changes)
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    pincode TEXT NOT NULL,
    address TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0
)
''')

# PARKINGS TABLE (Removed slot counts)
cursor.execute('''
CREATE TABLE IF NOT EXISTS parkings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    pincode TEXT NOT NULL,
    total_slots INTEGER NOT NULL,
    price_per_hour REAL DEFAULT 10
)
''')

# NEW SPOTS TABLE
cursor.execute('''
CREATE TABLE IF NOT EXISTS spots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parking_id INTEGER NOT NULL,
    spot_uid TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    UNIQUE(parking_id, spot_uid),
    FOREIGN KEY(parking_id) REFERENCES parkings(id) ON DELETE CASCADE
)
''')

# BOOKINGS TABLE (references spots table now)
cursor.execute('''
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    parking_id INTEGER NOT NULL,
    spot_id INTEGER NOT NULL,
    vehicle_number TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    duration REAL DEFAULT 0,
    cost REAL DEFAULT 0,
    status TEXT DEFAULT 'booked',
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(parking_id) REFERENCES parkings(id),
    FOREIGN KEY(spot_id) REFERENCES spots(id)
)
''')

# --- Seed Data ---

# Add test user
hashed_user_pw = generate_password_hash('Test@1234')
cursor.execute("INSERT OR IGNORE INTO users (email, password, full_name, pincode, address, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
    ('test@test.com', hashed_user_pw, 'Test User', '110011', 'Test Address', 0))

# Add admin user
hashed_admin_pw = generate_password_hash('Admin@1234')
cursor.execute("INSERT OR IGNORE INTO users (email, password, full_name, pincode, address, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
    ('admin@admin.com', hashed_admin_pw, 'Admin Boss', '000000', 'HQ', 1))

# Add test parking data
parkings_to_add = [
    ('City Center Parking', '123 Main Road, Delhi', '110011', 12, 15),
    ('South Mall Basement', '45 South Avenue, Mumbai', '400001', 20, 25),
    ('Tech Park Plaza', '789 IT Hub, Bangalore', '560001', 30, 20)
]
cursor.executemany("INSERT INTO parkings (name, address, pincode, total_slots, price_per_hour) VALUES (?, ?, ?, ?, ?)", parkings_to_add)

# For each parking, create its spots
cursor.execute("SELECT id, total_slots FROM parkings")
parkings_data = cursor.fetchall()
for parking_id, total_slots in parkings_data:
    for i in range(1, total_slots + 1):
        spot_uid = f"A-{i}"
        cursor.execute("INSERT INTO spots (parking_id, spot_uid) VALUES (?, ?)", (parking_id, spot_uid))


conn.commit()
conn.close()
print("✅ Database re-initialized cleanly at", DB_PATH)
