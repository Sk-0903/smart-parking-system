from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
from math import ceil
import cv2
import pytesseract
import re
import os
import base64
import time
import logging
from werkzeug.utils import secure_filename
from ultralytics import YOLO
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# ================= CYBER SECURITY LAYER =================

# 🔐 ADMIN LOGIN DATA
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = generate_password_hash("admin123")

# 🔐 FILE VALIDATION
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# 🔐 LOGGING SYSTEM
logging.basicConfig(filename='activity.log', level=logging.INFO)

def log_action(msg):
    logging.info(f"{datetime.now()} - {msg}")

# 🔐 PLATE VALIDATION
def valid_plate(plate):
    return re.match(r'^[A-Z0-9]{5,10}$', plate)

# 🔐 SUSPICIOUS DETECTION
recent_attempts = {}

def detect_suspicious(plate):
    now = datetime.now()
    if plate in recent_attempts:
        if (now - recent_attempts[plate]).seconds < 10:
            return True
    recent_attempts[plate] = now
    return False

# 🔐 FILE CHECK
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- APP ----------------
app = Flask(__name__)
app.secret_key = "super_secure_key"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.permanent_session_lifetime = timedelta(minutes=5)

# ---------------- AI ----------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Keshav.S\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
model = YOLO("yolov8n.pt")

# 🔐 BLACKLIST SYSTEM
BLACKLIST = ["KA01AB1234", "KA05XY9999"]

# ---------------- AI ----------------
def detect_plate(image_path):
    img = cv2.imread(image_path)

    if img is None:
        return "NOT DETECTED"

    results = model(img)

    for r in results:
        for box in r.boxes.xyxy:
            x1, y1, x2, y2 = map(int, box)
            plate_img = img[y1:y2, x1:x2]

            if plate_img.size == 0:
                continue

            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)

            text = pytesseract.image_to_string(
                thresh,
                config='--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            )

            plate = re.findall(r'[A-Z]{2}\d{2}[A-Z]{2}\d{4}', text)
            if plate:
                return plate[0]

    return "NOT DETECTED"


# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            vehicle TEXT,
            plate TEXT UNIQUE,
            slot INTEGER,
            entry_time TEXT,
            exit_time TEXT,
            fee INTEGER,
            status TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()


# 🧠 SMART SLOT LOGIC
def get_available_slot():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT slot FROM users WHERE status='parked'")
    occupied = [row[0] for row in cur.fetchall()]

    conn.close()

    for i in range(1, 21):
        if i not in occupied:
            return i
    return None


# ---------------- ROUTES ----------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/attack123')
def attack_page():
    return render_template('attack.html')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():

    detected_plate = request.args.get('detected_plate')
    image_path = request.args.get('image')

    if request.method == 'POST':

        name = request.form['name']
        vehicle = request.form['vehicle']
        image = request.files.get('image')

        if image and image.filename != "":
            if not allowed_file(image.filename):
                return render_template('register.html', error="Invalid file type")

            filename = secure_filename(image.filename)
            os.makedirs("static", exist_ok=True)
            path = os.path.join("static", filename)
            image.save(path)

            plate = detect_plate(path)

            if plate == "NOT DETECTED":
                plate = request.form['plate']
        else:
            plate = request.form['plate']

        # 🔐 VALIDATION
        if plate and not valid_plate(plate):
            return render_template('register.html', error="Invalid plate")

        # 🚨 SUSPICIOUS CHECK
        if plate and detect_suspicious(plate):
            return render_template('register.html', error="Suspicious activity detected")

        log_action(f"Attempt to park: {plate}")    

        if not plate:
            return render_template('register.html', error="Plate required!")

        # 🔐 BLACKLIST CHECK
        if plate in BLACKLIST:
            return render_template('register.html', error="🚫 Blacklisted Vehicle!")

        conn = sqlite3.connect('parking.db')
        cur = conn.cursor()

        # 🔐 DUPLICATE DETECTION
        cur.execute("SELECT * FROM users WHERE plate=? AND status='parked'", (plate,))
        existing = cur.fetchone()

        if existing:
            conn.close()
            return render_template('register.html', error="⚠️ Vehicle already parked!")

        slot = get_available_slot()
        if slot is None:
            conn.close()
            return render_template('register.html', error="Parking Full!")

        entry_time = datetime.now()

        try:
            cur.execute("""
            INSERT INTO users (name, vehicle, plate, slot, entry_time, status)
            VALUES (?, ?, ?, ?, ?, 'parked')
            """, (name, vehicle, plate, slot, entry_time))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Plate already exists!")

        conn.close()
        return redirect(url_for('dashboard', plate=plate))

    return render_template(
        'register.html',
        detected_plate=detected_plate,
        image_path=image_path,
        cache_bust=time.time()
    )


# ---------------- RESERVATION SYSTEM ----------------
@app.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if request.method == 'POST':
        name = request.form['name']
        plate = request.form['plate']

        slot = get_available_slot()

        return render_template('reserve.html',
                               message=f"Slot {slot} reserved for {plate}")

    return render_template('reserve.html')


# ---------------- PARKING MAP ----------------
@app.route('/map')
def parking_map():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT slot FROM users WHERE status='parked'")
    occupied = [row[0] for row in cur.fetchall()]

    conn.close()

    return render_template('map.html', occupied=occupied)


# ---------------- ANALYTICS ----------------
@app.route('/analytics')
def analytics():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT status FROM users")
    data = cur.fetchall()

    cur.execute("SELECT SUM(fee) FROM users WHERE fee IS NOT NULL")
    revenue = cur.fetchone()[0] or 0

    parked = sum(1 for d in data if d[0] == 'parked')
    exited = sum(1 for d in data if d[0] == 'exited')

    conn.close()

    return render_template('analytics.html',
                           parked=parked,
                           exited=exited,
                           revenue=revenue)


# ---------------- CAMERA ----------------
@app.route('/camera')
def camera():
    return render_template('camera.html')


@app.route('/capture', methods=['POST'])
def capture():
    data = request.form['image_data']
    image_data = data.split(",")[1]
    img_bytes = base64.b64decode(image_data)

    os.makedirs("static", exist_ok=True)

    filename = f"captured_{int(time.time())}.png"
    path = os.path.join("static", filename)

    with open(path, "wb") as f:
        f.write(img_bytes)

    plate = detect_plate(path)

    return redirect(url_for('register', detected_plate=plate, image=filename))


# ---------------- DASHBOARD ----------------
@app.route('/dashboard/<string:plate>')
def dashboard(plate):
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE plate=?", (plate,))
    user = cur.fetchone()

    conn.close()

    return render_template('dashboard.html', user=user)


# ---------------- EXIT ----------------
@app.route('/exit', methods=['GET', 'POST'])
def exit_vehicle():
    fee = None

    if request.method == 'POST':
        plate = request.form['plate']

        conn = sqlite3.connect('parking.db')
        cur = conn.cursor()

        cur.execute("SELECT entry_time, vehicle FROM users WHERE plate=? AND status='parked'", (plate,))
        data = cur.fetchone()

        if data:
            entry_time = datetime.fromisoformat(data[0])
            vehicle = data[1]

            exit_time = datetime.now()
            hours = ceil((exit_time - entry_time).seconds / 3600)
            rate = 20 if vehicle == "bike" else 50
            fee = hours * rate

            cur.execute("""
            UPDATE users
            SET exit_time=?, fee=?, status='exited'
            WHERE plate=?
            """, (exit_time, fee, plate))

            conn.commit()

            log_action(f"{plate} exited system")

        conn.close()

    return render_template('exit.html', fee=fee)


# ---------------- ADMIN ----------------
@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/login')

    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    conn.close()

    return render_template('admin.html', users=users)


# ---------------- RESET ----------------
    
@app.route('/reset')
def reset():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("DELETE FROM users")

    conn.commit()
    conn.close()

    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        if user == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD, pwd):
            session.permanent = True
            session['admin'] = True
            return redirect('/admin')
        else:
            return "Invalid Credentials"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')


@app.route('/simulate-attack/<attack_type>')
def simulate_attack(attack_type):

    if attack_type == "sql":
        test_input = "' OR '1'='1"
        if not valid_plate(test_input):
            return "❌ SQL Injection Blocked by Validation!"

    elif attack_type == "spam":
        plate = "KA01AB1234"
        if detect_suspicious(plate):
            return "🚨 Spam Attack Detected!"

    elif attack_type == "invalid":
        plate = "@@@###"
        if not valid_plate(plate):
            return "❌ Invalid Input Blocked!"

    return "System Safe ✅"

@app.route('/test123')
def test():
    return "TEST WORKING"

@app.route('/upload', methods=['POST'])
def upload_api():

    file = request.files.get('file')

    if not file:
        return jsonify({"plate": "NO FILE"})

    if not allowed_file(file.filename):
        return jsonify({"plate": "INVALID FILE"})

    filename = secure_filename(file.filename)
    os.makedirs("static", exist_ok=True)

    path = os.path.join("static", filename)
    file.save(path)

    try:
        plate = detect_plate(path)
    except Exception as e:
        return jsonify({"plate": "ERROR"})

    return jsonify({"plate": plate})

if __name__ == '__main__':
    print("STARTING SERVER...")
    app.run(host="0.0.0.0", port=8000)