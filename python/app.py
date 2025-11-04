import json
import threading
import re
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from toll_functions import fetch_recent_transactions, top_up_balance
from firebase_admin import db, credentials
import firebase_admin

# ==================================
# GLOBAL CONFIG & STATE
# ==================================
STATUS_FILE = 'rfid_status.json'

# Initialize Flask
app = Flask(__name__)
app.secret_key = 'GENERATE_A_LONG_RANDOM_SECRET_KEY_HERE'  # Necessary for flash messages

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
        return {
            "entrance_reader_status": "OFFLINE",
            "exit_reader_status": "OFFLINE",
            "last_activity_time": "N/A",
            "last_activity": "No status file found. Check listener5.py.",
            "listener_state": "STOPPED",
            "last_scanned_uid": ""
        }

# ==================================
# API ENDPOINTS
# ==================================
@app.route('/api/transactions')
def api_transactions():
    """Feeds the Transaction History Panel."""
    try:
        data = fetch_recent_transactions(limit=15)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rfid_status')
def api_rfid_status():
    """Feeds the RFID Status Panel AND Last Scanned UID."""
    status_data = read_rfid_status()
    return jsonify(status_data)

@app.route('/api/flood_control')
def api_flood_control():
    return jsonify({
        "status": "OK",
        "level": 23
    })

# ==================================
# WEB ROUTES
# ==================================
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    """Main dashboard logic and handles Top-Up POST request."""
    
    if request.method == 'POST' and 'process_topup' in request.form:
        uid = request.form['topup_uid'].upper()
        try:
            amount = int(request.form['topup_amount'])
            if amount > 0 and re.match(r'[A-F0-9]{8}', uid):
                result = top_up_balance(uid, amount)  # Updates Firebase and SQLite
                if result:
                    flash(f"✅ Success! {result['Name']} New Balance: ₱{result['Balance']}", 'success')
                    # Clear the scanned UID after successful top-up
                    status = read_rfid_status()
                    status['last_scanned_uid'] = ""
                    with open(STATUS_FILE, 'w') as f:
                        json.dump(status, f, indent=4)
                else:
                    flash(f"❌ Top-Up Failed for UID {uid}. User not found or error.", 'error')
            else:
                flash("Invalid UID or amount entered.", 'error')
        except ValueError:
            flash("Invalid amount entered.", 'error')
        return redirect(url_for('dashboard')) 
    
    # GET request
    status_data = read_rfid_status()
    current_scanned_uid = status_data.get('last_scanned_uid', '')
    transactions = fetch_recent_transactions(limit=15)
    
    return render_template(
        'transactions.html', 
        transactions=transactions, 
        rfid_status=status_data,
        last_uid=current_scanned_uid
    )

# ==================================
# RUN FLASK
# ==================================
if __name__ == '__main__':
    print("Flask Web Server Starting on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
