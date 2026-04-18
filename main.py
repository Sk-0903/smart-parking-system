from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
from math import ceil
import cv2
import re
import os
import base64
import time
import logging
import numpy as np
from werkzeug.utils import secure_filename
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

# 🔐 BLACKLIST SYSTEM
BLACKLIST = ["KA01AB1234", "KA05XY9999"]

# ---------------- AI ----------------


import cv2
import numpy as np
import requests
import re
import os

def detect_plate(image_path):
    try:
        print("===== DEBUG START =====")

        # 🔍 Debug info
        print("API KEY:", os.getenv("K84237357888957"))
        print("IMAGE PATH:", image_path)
        print("FILE EXISTS:", os.path.exists(image_path))

        img = cv2.imread(image_path)

        if img is None:
            print("❌ Image not loaded")
            return "NOT DETECTED"

        # 🔥 Resize
        img = cv2.resize(img, None, fx=4, fy=4)

        # 🔥 Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 🔥 Strong contrast boost
        gray = cv2.convertScaleAbs(gray, alpha=4.5, beta=120)

        # 🔥 CLAHE
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)

        # 🔥 Sharpen
        kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
        gray = cv2.filter2D(gray, -1, kernel)

        # 🔥 Threshold
        _, thresh = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # 🔥 Noise removal
        thresh = cv2.medianBlur(thresh, 3)

        # 🔥 Save processed images
        processed_path = "processed.jpg"
        cv2.imwrite(processed_path, thresh)

        # 🔥 Inverted version (important for faint text)
        thresh_inv = cv2.bitwise_not(thresh)
        inv_path = "processed_inv.jpg"
        cv2.imwrite(inv_path, thresh_inv)

        # 🔥 OCR function
        def ocr_call(path):
            url = "https://api.ocr.space/parse/image"

            payload = {
                'apikey': 'K84237357888957'
                'language': 'eng',
                'OCREngine': 3,  # 🔥 best engine
                'scale': True,
                'detectOrientation': True,
                'isOverlayRequired': False
            }

            with open(path, 'rb') as f:
                response = requests.post(url, files={'file': f}, data=payload)

            try:
                result = response.json()
            except:
                print("❌ Invalid OCR response:", response.text)
                return ""

            print(f"OCR RESULT ({path}):", result)

            if "ParsedResults" not in result:
                return ""

            return result['ParsedResults'][0]['ParsedText']

        # 🔥 Try all versions
        text_raw = ocr_call(image_path)
        text_processed = ocr_call(processed_path)
        text_inv = ocr_call(inv_path)

        print("RAW:", text_raw)
        print("PROCESSED:", text_processed)
        print("INVERTED:", text_inv)

        # 🔥 Pick best result
        texts = [text_raw, text_processed, text_inv]
        text = max(texts, key=lambda t: len(t) if t else 0)

        if not text:
            print("❌ No text detected")
            return "NOT DETECTED"

        # 🔥 Clean text
        text = text.upper()
        text = re.sub(r'[^A-Z0-9]', '', text)

        # 🔥 Smart corrections
        text = text.replace("O", "0")
        text = text.replace("I", "1")
        text = text.replace("Z", "2")
        text = text.replace("S", "5")

        print("CLEANED TEXT:", text)

        # 🔥 Indian plate format
        match = re.findall(r'[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}', text)
        if match:
            print("✅ MATCH FOUND:", match[0])
            return match[0]

        # 🔥 fallback
        match = re.findall(r'[A-Z0-9]{6,12}', text)
        if match:
            print("⚠️ FALLBACK MATCH:", match[0])
            return match[0]

        print("❌ FINAL: NOT DETECTED")
        return "NOT DETECTED"

    except Exception as e:
        print("🔥 OCR ERROR:", e)
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


@app.route('/register', methods=['GET', 'POST'])
def register():

    # 🔥 Detect if request is from Android (JSON)
    is_api = request.is_json

    if is_api:
        data = request.get_json()
        name = data.get("name")
        vehicle = data.get("vehicle")
        plate = data.get("plate")
        image = None
    else:
        detected_plate = request.args.get('detected_plate')
        image_path = request.args.get('image')

    # ---------------- POST ----------------
    if request.method == 'POST':

        if not is_api:
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
            if is_api:
                return jsonify({"error": "Invalid plate ❌"})
            return render_template('register.html', error="Invalid plate")

        # 🚨 SUSPICIOUS CHECK
        if plate and detect_suspicious(plate):
            if is_api:
                return jsonify({"error": "Suspicious activity 🚨"})
            return render_template('register.html', error="Suspicious activity detected")

        log_action(f"Attempt to park: {plate}")

        if not plate:
            if is_api:
                return jsonify({"error": "Plate required ❌"})
            return render_template('register.html', error="Plate required!")

        # 🔐 BLACKLIST
        if plate in BLACKLIST:
            if is_api:
                return jsonify({"error": "Blacklisted 🚫"})
            return render_template('register.html', error="🚫 Blacklisted Vehicle!")

        conn = sqlite3.connect('parking.db')
        cur = conn.cursor()

        # 🔐 DUPLICATE
        cur.execute("SELECT * FROM users WHERE plate=? AND status='parked'", (plate,))
        existing = cur.fetchone()

        if existing:
            conn.close()
            if is_api:
                return jsonify({"error": "Already Parked ⚠️"})
            return render_template('register.html', error="⚠️ Vehicle already parked!")

        slot = get_available_slot()
        if slot is None:
            conn.close()
            if is_api:
                return jsonify({"error": "Parking Full ❌"})
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
            if is_api:
                return jsonify({"error": "Plate already exists ❌"})
            return render_template('register.html', error="Plate already exists!")

        conn.close()

        # 🔥 FINAL RESPONSE
        if is_api:
            return jsonify({
                "slot": slot,
                "name": name,
                "vehicle": vehicle,
                "plate": plate
            })

        return redirect(url_for('dashboard', plate=plate))

    # ---------------- GET ----------------
    return render_template(
        'register.html',
        detected_plate=detected_plate if not is_api else None,
        image_path=image_path if not is_api else None,
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
from datetime import datetime
from math import ceil
import sqlite3

# ---------------- MAP ----------------
@app.route('/map')
def parking_map():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    # 🔥 IMPORTANT:
    # We fetch ONLY the latest parked vehicle per slot
    # This avoids duplicate slots appearing in UI
    # (because DB may contain multiple records for same slot)

    cur.execute("""
        SELECT u.slot, u.plate, u.entry_time, u.vehicle
        FROM users u
        INNER JOIN (
            SELECT slot, MAX(entry_time) as latest
            FROM users
            WHERE status='parked'
            GROUP BY slot
        ) latest_entries
        ON u.slot = latest_entries.slot 
        AND u.entry_time = latest_entries.latest
    """)
    data = cur.fetchall()

    # 🔥 Slot usage count (for heatmap)
    # Counts how many times each slot has been used historically
    cur.execute("""
        SELECT slot, COUNT(*) 
        FROM users 
        GROUP BY slot
    """)
    usage_data = cur.fetchall()

    conn.close()

    # 🔥 Convert usage into dictionary for easy access in frontend
    usage_dict = {slot: count for slot, count in usage_data}

    slots = []

    # 🔥 Process each parked vehicle
    for row in data:
        slot, plate, entry_time, vehicle = row

        entry_time = datetime.fromisoformat(entry_time)
        now = datetime.now()

        # 🔥 Calculate parking duration
        duration = now - entry_time
        total_minutes = int(duration.total_seconds() / 60)

        hours = total_minutes // 60
        minutes = total_minutes % 60

        time_display = f"{hours}h {minutes}m"

        # 🔥 Fee calculation logic
        rate = 20 if vehicle == "bike" else 50
        fee = max(1, ceil(total_minutes / 60)) * rate

        slots.append({
            "slot": slot,
            "plate": plate,
            "time": time_display,
            "fee": fee
        })

    # 🔥 SMART PREDICTION SYSTEM
    TOTAL_SLOTS = 20
    occupied = len(slots)
    free_slots = TOTAL_SLOTS - occupied

    # 🔥 Dynamic status message based on occupancy
    if occupied >= TOTAL_SLOTS * 0.8:
        prediction = f"🚀 Parking filling fast! | Free slots: {free_slots}"
    elif occupied >= TOTAL_SLOTS * 0.5:
        prediction = f"⚠️ Half capacity reached | Free slots: {free_slots}"
    else:
        prediction = f"✅ Plenty of space available | Free slots: {free_slots}"

    # 🔥 Send data to frontend
    occupied_slots = {s["slot"] for s in slots}
    return render_template(
    'map.html',
    slots=slots,
    usage=usage_dict,
    prediction=prediction,
    occupied_slots=occupied_slots   # 🔥 ADD THIS
)

# ---------------- ANALYTICS ----------------
@app.route('/analytics')
def analytics():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE status='parked'")
    parked = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE status='exited'")
    exited = cur.fetchone()[0]

    cur.execute("SELECT SUM(fee) FROM users WHERE fee IS NOT NULL")
    revenue = cur.fetchone()[0] or 0

    conn.close()

    return render_template(
        'analytics.html',
        total=total,
        parked=parked,
        exited=exited,
        revenue=revenue
    )

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

    # 🤖 Detect plate
    plate = detect_plate(path)

    # ❌ If not detected → fallback
    if plate == "NOT DETECTED":
        return redirect(url_for('register', detected_plate=plate, image=filename))

    # 🔐 Validation
    if not valid_plate(plate):
        return redirect(url_for('register', error="Invalid plate"))

    if detect_suspicious(plate):
        return redirect(url_for('register', error="Suspicious activity"))

    if plate in BLACKLIST:
        return redirect(url_for('register', error="Blacklisted vehicle"))

    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    # ❌ Already parked
    cur.execute("SELECT * FROM users WHERE plate=? AND status='parked'", (plate,))
    if cur.fetchone():
        conn.close()
        return redirect(url_for('register', error="Vehicle already parked"))

    # 🅿️ Slot
    slot = get_available_slot()
    if slot is None:
        conn.close()
        return redirect(url_for('register', error="Parking Full"))

    entry_time = datetime.now()

    return redirect(url_for('register', detected_plate=plate, image=filename))


# ---------------- DASHBOARD ----------------
from datetime import datetime
from math import ceil

# ---------------- DASHBOARD ----------------
@app.route('/dashboard/<string:plate>')
def dashboard(plate):
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE plate=?", (plate,))
    user = cur.fetchone()

    conn.close()

    if not user:
        return "Invalid plate or user not found"

    # 🔥 Entry time
    entry_time = datetime.fromisoformat(user[5])
    now = datetime.now()

    # 🔥 Duration
    duration = now - entry_time
    total_minutes = int(duration.total_seconds() / 60)

    hours = total_minutes // 60
    minutes = total_minutes % 60

    time_display = f"{hours}h {minutes}m"

    # 💰 Fee calculation
    rate = 20 if user[2] == "bike" else 50
    fee = max(1, ceil(total_minutes / 60)) * rate

    # 🔥 Convert for JS (IMPORTANT)
    entry_time_str = entry_time.isoformat()

    return render_template(
        'dashboard.html',
        user=user,
        duration=time_display,
        fee=fee,
        entry_time=entry_time_str
    )


# ---------------- EXIT ----------------
@app.route('/exit', methods=['GET', 'POST'])
def exit_vehicle():
    fee = None
    duration_display = None

    if request.method == 'POST':
        plate = request.form['plate']

        conn = sqlite3.connect('parking.db')
        cur = conn.cursor()

        cur.execute(
            "SELECT entry_time, vehicle FROM users WHERE plate=? AND status='parked'",
            (plate,)
        )
        data = cur.fetchone()

        if not data:
            conn.close()
            return render_template('exit.html', error="Vehicle not found or already exited")

        entry_time = datetime.fromisoformat(data[0])
        vehicle = data[1]

        exit_time = datetime.now()

        # 🔥 Duration
        duration = exit_time - entry_time
        total_minutes = int(duration.total_seconds() / 60)

        hours = total_minutes // 60
        minutes = total_minutes % 60
        duration_display = f"{hours}h {minutes}m"

        # 💰 Fee
        rate = 20 if vehicle == "bike" else 50
        fee = max(1, ceil(total_minutes / 60)) * rate

        # 🔥 Update DB
        cur.execute("""
            UPDATE users
            SET exit_time=?, fee=?, status='exited'
            WHERE plate=?
        """, (exit_time, fee, plate))

        conn.commit()
        conn.close()

        log_action(f"{plate} exited system")

    return render_template('exit.html', fee=fee, duration=duration_display)

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
def upload():
    file = request.files['file']

    # Read image
    img = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_COLOR)

    # 🔥 Resize (VERY IMPORTANT for speed)
    img = cv2.resize(img, (600, 300))

    # Convert to gray (faster OCR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # OCR
    plate = detect_plate(path)  # or your saved file path

    print("OCR RESULT:", result)

    plate = "NO_PLATE"

    if len(result) > 0:
        raw_text = result[0]
        plate = clean_plate(raw_text)

    return jsonify({"plate": plate})

import re

def clean_plate(text):
    text = text.upper()  # uppercase

    # Replace common OCR mistakes
    replacements = {
        '€': 'C',
        '<': '0',
        '(': 'C',
        ')': '',
        '-': '',
        ' ': '',
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    # Keep only alphanumeric
    text = re.sub(r'[^A-Z0-9]', '', text)

    return text

@app.route('/map-data')
def map_data():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()
    cur.execute("SELECT slot FROM users WHERE status='parked'")
    occupied = [row[0] for row in cur.fetchall()]
    conn.close()
    return jsonify(occupied)


@app.route('/status')
def status():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE status='parked'")
    count = cur.fetchone()[0]
    conn.close()
    return jsonify({"occupied": count})

@app.route("/slots", methods=["GET"])
def get_slots():
    conn = sqlite3.connect("parking.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT slot
        FROM users
        WHERE status='parked'
    """)

    rows = cur.fetchall()

    occupied_slots = [row[0] for row in rows]

    slots = []

    for i in range(1, 7):
        slots.append({
            "slot": i,
            "occupied": i in occupied_slots
        })

    conn.close()
    return jsonify(slots)

@app.route('/api/exit', methods=['POST'])
def exit_vehicle_api():
    data = request.json
    plate = data.get("plate")

    conn = sqlite3.connect("parking.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT slot, entry_time, vehicle
        FROM users
        WHERE plate=? AND status='parked'
    """, (plate,))

    row = cur.fetchone()

    if not row:
        return jsonify({"error": "Vehicle not found ❌"})

    slot, entry_time, vehicle = row

    entry_time = datetime.fromisoformat(entry_time)
    exit_time = datetime.now()

    duration = (exit_time - entry_time).total_seconds() / 60

    rate = 20 if vehicle == "bike" else 50
    fee = max(1, ceil(duration / 60)) * rate

    cur.execute("""
        UPDATE users
        SET exit_time=?, fee=?, status='exited'
        WHERE plate=?
    """, (exit_time.isoformat(), fee, plate))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Exited Successfully ✅",
        "slot": slot,
        "minutes": int(duration),
        "fee": fee
    })

@app.route('/stats')
def stats():
    conn = sqlite3.connect('parking.db')
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE status='parked'")
    active = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE status='exited'")
    exited = cur.fetchone()[0]

    cur.execute("SELECT SUM(fee) FROM users WHERE fee IS NOT NULL")
    revenue = cur.fetchone()[0] or 0

    conn.close()

    return jsonify({
        "total": total,
        "active": active,
        "exited": exited,
        "revenue": revenue
    })

if __name__ == '__main__':
    print("STARTING SERVER...")
    app.run(host="0.0.0.0", port=8000)