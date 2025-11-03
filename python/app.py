# app.py
import json
import threading
import serial
import re
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, get_flashed_messages
from toll_functions import fetch_recent_transactions, top_up_balance # Ensure these functions are in toll_functions.py
from firebase_admin import db, credentials
import firebase_admin

# ==================================
# GLOBAL CONFIG & STATE
# ==================================
STATUS_FILE = 'rfid_status.json'
LAST_SCANNED_UID = None
UID_LOCK = threading.Lock() 
TOPUP_PORT = '' #Add the proper port for the top-up RFID reader 
BAUD_RATE = 9600
FLOOD_CONTROL_PATH = '/FloodControlStatus' # Path in Firebase DB

# Initialize Flask
app = Flask(__name__)
# *** 2. PLACEHOLDER FOR GENERATED SECRET KEY ***
app.secret_key = 'GENERATE_A_LONG_RANDOM_SECRET_KEY_HERE' # Necessary for flash messages

# Initialize Firebase
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate('embedded.json')
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://embedded-project-ba95c-default-rtdb.firebaseio.com/'
        })
        print("Firebase initialized successfully.")
    except Exception as e:
        print(f"FIREBASE INIT ERROR: {e}")
        
# ==================================
# DATA READING HELPERS
# ==================================

def read_rfid_status():
    """Reads the latest status from the file created by listener5.py."""
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return default data if file doesn't exist or is corrupted
        return {
            "entrance_reader_status": "OFFLINE",
            "exit_reader_status": "OFFLINE",
            "last_activity_time": "N/A",
            "last_activity": "No status file found. Check listener5.py.",
            "listener_state": "STOPPED"
        }

# ==================================
# TOP-UP SERIAL LISTENING THREAD
# ==================================
def serial_listener_thread():
    """Continuously listens to the top-up serial port in the background."""
    print(f"\n[TOPUP-READER] Starting listener on {TOPUP_PORT}...")
    try:
        ser = serial.Serial(TOPUP_PORT, BAUD_RATE, timeout=1)
        ser.flushInput()
        
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            if not line:
                continue

            match = re.search(r'\b[A-F0-9]{8}\b', line, re.IGNORECASE)
            if match:
                uid = match.group(0).upper()
                with UID_LOCK:
                    global LAST_SCANNED_UID
                    LAST_SCANNED_UID = uid
                    print(f"[TOPUP-READER] Detected UID: {uid}")
            time.sleep(0.1) 

    except serial.SerialException as e:
        print(f"[TOPUP-READER] ERROR: Serial connection failed on {TOPUP_PORT}. {e}")
    except Exception as e:
        print(f"[TOPUP-READER] UNEXPECTED ERROR: {e}")

# ==================================
# API ENDPOINTS (Returns JSON for JS Polling)
# ==================================

@app.route('/api/transactions')
def api_transactions():
    """API 1: Feeds the Transaction History Panel (from SQLite)."""
    try:
        # Fetching 15 transactions to match the updated HTML header
        data = fetch_recent_transactions(limit=15)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rfid_status')
def api_rfid_status():
    """API 2: Feeds the RFID Status Panel AND Last Scanned UID (from rfid_status.json)."""
    status_data = read_rfid_status()
    
    # *** 3. API ENHANCEMENT: ADD LAST_SCANNED_UID FOR LIVE TOP-UP FIELD ***
    with UID_LOCK:
        status_data['last_scanned_uid'] = LAST_SCANNED_UID or '' 
        
    return jsonify(status_data)

@app.route('/api/flood_control')
def api_flood_control():
    """API 3: Feeds the Flood Control Panel (from Firebase)."""
    try:
        # Listening to another directory in Firebase
        flood_ref = db.reference(FLOOD_CONTROL_PATH) 
        status_data = flood_ref.get() or {"status": "N/A", "level": "N/A"} 
        return jsonify(status_data)
    except Exception as e:
        # Returns a friendly error if Firebase fails to connect
        return jsonify({"status": "Firebase Error", "level": "N/A"}), 500

# ==================================
# WEB ROUTES (Renders HTML)
# ==================================

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    """Main dashboard logic and handles Top-Up POST request."""
    
    # 1. Handle Top-Up Submission (POST request)
    if request.method == 'POST' and 'process_topup' in request.form:
        uid = request.form['topup_uid'].upper()
        
        try:
            amount = int(request.form['topup_amount'])
            if amount > 0 and re.match(r'[A-F0-9]{8}', uid):
                result = top_up_balance(uid, amount) # Updates Firebase and SQLite
                if result:
                    flash(f"✅ Success! {result['Name']} New Balance: ₱{result['Balance']}", 'success')
                    # Clear the scanned UID after successful top-up
                    with UID_LOCK:
                        global LAST_SCANNED_UID
                        LAST_SCANNED_UID = None 
                else:
                    flash(f"❌ Top-Up Failed for UID {uid}. User not found or error.", 'error')
            else:
                 flash("Invalid UID or amount entered.", 'error')
        except ValueError:
            flash("Invalid amount entered.", 'error')
        
        return redirect(url_for('dashboard')) 
        
    # 2. Handle GET request and render
    
    with UID_LOCK:
        current_scanned_uid = LAST_SCANNED_UID
        
    # Initial data fetch for table (matching the API limit of 15)
    transactions = fetch_recent_transactions(limit=15) 
    
    return render_template(
        'transactions.html', 
        transactions=transactions, 
        rfid_status=read_rfid_status(),
        last_uid=current_scanned_uid 
    )

if __name__ == '__main__':
    # Initialize and start the serial listener thread
    topup_thread = threading.Thread(target=serial_listener_thread, daemon=True)
    topup_thread.start()

    print("Flask Web Server Starting on http://0.0.0.0:5000")
    # Use 0.0.0.0 to make it accessible over the Raspi's network
    app.run(host='0.0.0.0', port=5000, debug=True)