import sqlite3
import os

DB_PATH = os.path.join('data', 'user.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user



def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user



def get_all_parkings():
    conn = get_db_connection()
    parkings = conn.execute("SELECT * FROM parkings").fetchall()
    conn.close()
    return parkings



def get_parking_by_id(parking_id):
    conn = get_db_connection()
    parking = conn.execute("SELECT * FROM parkings WHERE id = ?", (parking_id,)).fetchone()
    conn.close()
    return parking



def get_user_bookings(user_id):
    conn = get_db_connection()
    bookings = conn.execute("SELECT b.*, p.name AS parking_name, p.address FROM bookings b JOIN parkings p ON b.parking_id = p.id WHERE b.user_id = ? ORDER BY b.start_time DESC", (user_id,)).fetchall()
    conn.close()
    return bookings



def search_parkings_by_pin_or_location(search_term):
    conn = get_db_connection()
    search_term = f'%{search_term}%'
    results = conn.execute("SELECT * FROM parkings WHERE pincode LIKE ? OR name LIKE ? OR address LIKE ?", (search_term, search_term, search_term)).fetchall()
    conn.close()
    return results



def update_parking_slots(parking_id, delta):
    conn = get_db_connection()
    conn.execute("UPDATE parkings SET available_slots = available_slots + ? WHERE id = ?", (delta, parking_id))
    conn.commit()
    conn.close()



def insert_booking(data):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO bookings (user_id, parking_id, spot_number, vehicle_number, start_time, status)
        VALUES (?, ?, ?, ?, ?, 'booked')
    """, (data['user_id'], data['parking_id'], data['spot_number'], data['vehicle_number'], data['start_time']))
    conn.commit()
    conn.close()



def update_booking_time(booking_id, field, value):
    conn = get_db_connection()
    conn.execute(f"UPDATE bookings SET {field} = ? WHERE id = ?", (value, booking_id))
    conn.commit()
    conn.close()



def finalize_booking(booking_id, duration, cost, end_time):
    conn = get_db_connection()
    conn.execute("""
        UPDATE bookings SET end_time = ?, duration = ?, cost = ?, status = 'completed'
        WHERE id = ?
    """, (end_time, duration, cost, booking_id))
    conn.commit()
    conn.close()



def get_summary_stats(user_id):
    conn = get_db_connection()
    summary = conn.execute("""
        SELECT SUM(duration) AS total_duration, SUM(cost) AS total_cost
        FROM bookings WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return summary



def get_graph_data(user_id):
    conn = get_db_connection()
    graph_data = conn.execute("""
        SELECT DATE(start_time) as date, SUM(duration) as time_spent, SUM(cost) as total_cost
        FROM bookings
        WHERE user_id = ?
        GROUP BY DATE(start_time)
        ORDER BY date ASC
    """, (user_id,)).fetchall()
    conn.close()
    return graph_data
