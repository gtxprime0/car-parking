import sqlite3
import datetime
from data.config import DATABASE

def get_user_by_email(email):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()
    return user


def dbcon():
    return sqlite3.connect('parking.db')



def get_user_by_name(name):
    con = dbcon()
    cur = con.cursor()
    q = "SELECT * FROM users WHERE username = ?"
    cur.execute(q, (name,))
    u = cur.fetchone()
    con.close()
    return u



def add_user(name, passw):
    con = dbcon()
    cur = con.cursor()
    cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (name, passw))
    con.commit()
    con.close()



def get_lots_all():
    con = dbcon()
    cur = con.cursor()
    cur.execute("SELECT * FROM parking_lot")
    d = cur.fetchall()
    con.close()
    return d



def get_spot_avail(lotid):
    con = dbcon()
    cur = con.cursor()
    cur.execute("SELECT id FROM parking_spot WHERE lot_id=? AND status='A'", (lotid,))
    spot = cur.fetchone()
    con.close()
    return spot



def mark_spot(spotid, stat):
    con = dbcon()
    cur = con.cursor()
    cur.execute("UPDATE parking_spot SET status=? WHERE id=?", (stat, spotid))
    con.commit()
    con.close()



def create_booking(user_id, spot_id, cost):
    con = dbcon()
    cur = con.cursor()
    now = str(datetime.datetime.now())
    cur.execute("INSERT INTO bookings (spot_id, user_id, parking_time, cost_per_hour) VALUES (?, ?, ?, ?)", (spot_id, user_id, now, cost))
    con.commit()
    con.close()



def free_booking(spot_id):
    con = dbcon()
    cur = con.cursor()
    now = str(datetime.datetime.now())
    cur.execute("UPDATE bookings SET leaving_time = ? WHERE spot_id = ? AND leaving_time IS NULL", (now, spot_id))
    con.commit()
    con.close()
