from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime, timedelta
import re

app = Flask(__name__)
app.secret_key = 'a_very_bad_secret_key'
DATABASE = os.path.join('data', 'user.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.context_processor
def utility_processor():
    def get_css_variable(var_name):
        if var_name == '--primary-cyan':
            return 'rgba(3, 218, 198, 1)'
        return ''
    return dict(get_css_variable=get_css_variable)




@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))





@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        errors = []
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one capital letter.")
        if not re.search(r"[0-9]", password):
            errors.append("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\+_-]", password):
            errors.append("Password must contain at least one special character (e.g., +@_).")


        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (email, password, full_name, pincode, address) VALUES (?, ?, ?, ?, ?)',
                         (email, hashed_password, request.form['full_name'], request.form['pin_code'], request.form['address']))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            
        except sqlite3.IntegrityError:
            flash('Email already exists.', 'warning')
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')





@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (request.form['email'],)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['full_name'] = user['full_name']
            session['is_admin'] = bool(user['is_admin'])
            if session['is_admin']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))

    conn = get_db_connection()
    
    parkings = conn.execute('''
        SELECT p.id, p.name, p.address, p.pincode, p.price_per_hour,
               (SELECT COUNT(id) FROM spots WHERE parking_id = p.id AND status = 'available') AS available_slots,
               p.total_slots
        FROM parkings p
    ''').fetchall()
    
    recent_bookings = conn.execute('''
        SELECT b.id, b.status, b.start_time, b.end_time, s.spot_uid, p.name as parking_name
        FROM bookings b
        JOIN spots s ON b.spot_id = s.id
        JOIN parkings p ON b.parking_id = p.id
        WHERE b.user_id = ? ORDER BY b.id DESC LIMIT 5
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('user_dashboard.html',
                           user_name=session.get('full_name'),
                           available_parkings=parkings,
                           parking_history=recent_bookings)





@app.route('/book', methods=['POST'])
def book():
    if 'user_id' not in session: return redirect(url_for('login'))

    parking_id = request.form['parking_id']
    start_time_str = request.form['start_time']
    duration = int(request.form['duration'])
    start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
    end_time_dt = start_time_dt + timedelta(hours=duration)

    conn = get_db_connection()
    available_spot = conn.execute("SELECT id FROM spots WHERE parking_id = ? AND status = 'available' LIMIT 1", (parking_id,)).fetchone()

    if not available_spot:
        flash('No available spots in this parking lot.', 'danger')
        return redirect(url_for('dashboard'))

    spot_id = available_spot['id']
    
    # Create booking
    conn.execute('''
        INSERT INTO bookings (user_id, parking_id, spot_id, vehicle_number, start_time, end_time, status)
        VALUES (?, ?, ?, ?, ?, ?, 'booked')
    ''', (session['user_id'], parking_id, spot_id, request.form['vehicle_number'],
          start_time_dt.strftime("%Y-%m-%d %H:%M"), end_time_dt.strftime("%Y-%m-%d %H:%M")))
    
    
    # Mark    occupied
    conn.execute("UPDATE spots SET status = 'occupied' WHERE id = ?", (spot_id,))
    conn.commit()
    conn.close()
    
    flash('Booking successful!', 'success')
    return redirect(url_for('dashboard'))



@app.route('/update_booking_status/<int:booking_id>/<new_status>', methods=['POST'])
def update_booking_status(booking_id, new_status):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    booking = conn.execute("SELECT * FROM bookings WHERE id = ? AND user_id = ?", (booking_id, session['user_id'])).fetchone()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for('dashboard'))

    if new_status == 'ongoing':
        conn.execute("UPDATE bookings SET status = 'ongoing', start_time = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), booking_id))
        flash("Parking started!", "info")

    elif new_status == 'completed':
        details = conn.execute('''
            SELECT b.start_time, p.price_per_hour FROM bookings b
            JOIN parkings p ON b.parking_id = p.id
            WHERE b.id = ?
        ''', (booking_id,)).fetchone()

        end_time = datetime.now()
        start_time = datetime.strptime(details['start_time'], "%Y-%m-%d %H:%M")
        
        duration_hours = (end_time - start_time).total_seconds() / 3600
        cost = duration_hours * details['price_per_hour']

        conn.execute("UPDATE bookings SET status = 'completed', end_time = ?, duration = ?, cost = ? WHERE id = ?",
                     (end_time.strftime("%Y-%m-%d %H:%M"), duration_hours, cost, booking_id))
        
        conn.execute("UPDATE spots SET status = 'available' WHERE id = ?", (booking['spot_id'],))
        flash("Parking completed. Hope to see you again!", "success")

    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))




# ADMIN ROUTES
@app.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    parkings = conn.execute('''
        SELECT p.id, p.name, p.total_slots,
               (SELECT COUNT(id) FROM spots WHERE parking_id = p.id AND status = 'available') as available_slots
        FROM parkings p
    ''').fetchall()
    conn.close()
    
    return render_template('admin_dashboard.html', parkings=parkings)




@app.route('/admin/add_parking', methods=['POST'])
def admin_add_parking():
    if not session.get('is_admin'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO parkings (name, address, pincode, price_per_hour, total_slots)
        VALUES (?, ?, ?, ?, ?)
    ''', (request.form['name'], request.form['address'], request.form['pincode'], request.form['price'], request.form['slots']))
    
    parking_id = cursor.lastrowid
    

    total_slots = int(request.form['slots'])
    for i in range(1, total_slots + 1):
        cursor.execute("INSERT INTO spots (parking_id, spot_uid) VALUES (?, ?)", (parking_id, f"A-{i}"))

    conn.commit()
    conn.close()
    flash(f"Parking lot '{request.form['name']}' added successfully!", "success")
    return redirect(url_for('admin_dashboard'))




@app.route('/admin/edit_parking/<int:parking_id>', methods=['POST'])
def admin_edit_parking(parking_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE parkings SET name = ?, address = ?, pincode = ?, price_per_hour = ?
        WHERE id = ?
    ''', (request.form['name'], request.form['address'], request.form['pincode'], request.form['price'], parking_id))
    conn.commit()
    conn.close()
    
    flash("Parking lot details updated.", "success")
    return redirect(url_for('admin_dashboard'))




@app.route('/admin/users')
def admin_users():
    if not session.get('is_admin'): return redirect(url_for('login'))
    conn = get_db_connection()
    users = conn.execute("SELECT id, email, full_name, address, pincode FROM users WHERE is_admin = 0").fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)



@app.route('/admin/stats')
def admin_stats():
    if not session.get('is_admin'): return redirect(url_for('login'))
    conn = get_db_connection()
    
  
    revenue_by_lot = conn.execute('''
        SELECT p.name, SUM(b.cost) as total_revenue
        FROM bookings b
        JOIN parkings p ON b.parking_id = p.id
        WHERE b.status = 'completed'
        GROUP BY p.name
    ''').fetchall()




    revenue_by_day = conn.execute('''
        SELECT DATE(end_time) as date, SUM(cost) as daily_revenue
        FROM bookings
        WHERE status = 'completed'
        GROUP BY date
        ORDER BY date ASC
    ''').fetchall()
    
    conn.close()

    lot_labels = [row['name'] for row in revenue_by_lot]
    lot_data = [row['total_revenue'] for row in revenue_by_lot]
    
    day_labels = [row['date'] for row in revenue_by_day]
    day_data = [row['daily_revenue'] for row in revenue_by_day]

    return render_template('admin_stats.html',
                           lot_labels=lot_labels, lot_data=lot_data,
                           day_labels=day_labels, day_data=day_data)




@app.route('/profile')
def profile():
    if 'user_id' not in session: return redirect(url_for('login'))

    conn = get_db_connection()
    user_id = session['user_id']
    
    # Sloppy, but it's what the customer wants
    all_bookings = conn.execute('''
        SELECT b.id, b.start_time, b.end_time, b.duration, b.cost, p.name as parking_name, s.spot_uid
        FROM bookings b
        JOIN parkings p ON b.parking_id = p.id
        JOIN spots s ON b.spot_id = s.id
        WHERE b.user_id = ? AND b.status = 'completed'
        ORDER BY b.id DESC
    ''', (user_id,)).fetchall()

    summary = conn.execute("SELECT SUM(duration) as total_duration, SUM(cost) as total_cost FROM bookings WHERE user_id = ? AND status = 'completed'", (user_id,)).fetchone()
    

    graph_data = conn.execute('''
        SELECT DATE(start_time) as date, SUM(cost) as daily_cost, SUM(duration) as daily_duration
        FROM bookings
        WHERE user_id = ? AND status = 'completed'
        GROUP BY DATE(start_time)
        ORDER BY date ASC
    ''', (user_id,)).fetchall()
    
    conn.close()


    labels = [row['date'] for row in graph_data]
    cost_data = [row['daily_cost'] for row in graph_data]
    duration_data = [row['daily_duration'] for row in graph_data]

    return render_template('profile.html',
                           bookings=all_bookings,
                           total_duration=summary['total_duration'] or 0,
                           total_cost=summary['total_cost'] or 0,
                           labels=labels,
                           cost_data=cost_data,
                           duration_data=duration_data)




@app.route('/admin/parking/<int:parking_id>')
def admin_parking_details(parking_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    parking = conn.execute("SELECT * FROM parkings WHERE id = ?", (parking_id,)).fetchone()
    spots = conn.execute("SELECT * FROM spots WHERE parking_id = ? ORDER BY spot_uid", (parking_id,)).fetchall()
    conn.close()
    
    if not parking: return "Parking not found", 404
    
    return render_template('admin_parking_details.html', parking=parking, spots=spots)



@app.route('/admin/spot_details/<int:spot_id>')
def admin_spot_details(spot_id):
    if not session.get('is_admin'): return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    details = conn.execute('''
        SELECT
            s.id as spot_id,
            s.spot_uid,
            s.status,
            u.id as user_id,
            u.full_name,
            b.vehicle_number,
            b.start_time,
            b.end_time,
            p.price_per_hour
        FROM spots s
        LEFT JOIN bookings b ON b.spot_id = s.id AND b.status IN ('booked', 'ongoing')
        LEFT JOIN users u ON b.user_id = u.id
        LEFT JOIN parkings p ON s.parking_id = p.id
        WHERE s.id = ?
    ''', (spot_id,)).fetchone()
    conn.close()

    if not details: return jsonify({'error': 'Spot not found'}), 404



    cost = "N/A"
    if details['start_time']:
        start = datetime.strptime(details['start_time'], "%Y-%m-%d %H:%M")
        duration = (datetime.now() - start).total_seconds() / 3600
        cost = f"₹{duration * (details['price_per_hour'] or 10):.2f} (est.)"

    return jsonify({
        'spot_id': details['spot_id'],
        'spot_uid': details['spot_uid'],
        'status': details['status'],
        'customer_name': details['full_name'] or 'N/A',
        'vehicle_number': details['vehicle_number'] or 'N/A',
        'start_time': details['start_time'] or 'N/A',
        'est_cost': cost,
    })




@app.route('/admin/delete_spot/<int:spot_id>', methods=['POST'])
def admin_delete_spot(spot_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    spot = conn.execute("SELECT status, parking_id FROM spots WHERE id = ?", (spot_id,)).fetchone()
    if spot and spot['status'] == 'available':
        parking_id = spot['parking_id']
        conn.execute("DELETE FROM spots WHERE id = ?", (spot_id,))
        conn.execute("UPDATE parkings SET total_slots = total_slots - 1 WHERE id = ?", (parking_id,))
        conn.commit()
        flash('Spot deleted successfully.', 'success')
    else:
        flash('Cannot delete an occupied or non-existent spot.', 'danger')
    conn.close()
    return redirect(url_for('admin_parking_details', parking_id=spot['parking_id']))



@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True, port=5001)
