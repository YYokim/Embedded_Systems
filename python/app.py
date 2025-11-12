import json
import threading
import re
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from toll_functions import fetch_recent_transactions, top_up_balance, set_gate_state
from firebase_admin import db, credentials
import firebase_admin

STATUS_FILE = 'rfid_status.json'

app = Flask(__name__)
app.secret_key = 'GENERATE_A_LONG_RANDOM_SECRET_KEY_HERE'

# Firebase Initialization
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate('embedded.json')
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://embedded-project-ba95c-default-rtdb.firebaseio.com/'
        })
        print("Firebase initialized successfully.")
    except Exception as e:
        print(f"FIREBASE INIT ERROR: {e}")

def read_rfid_status():
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "entrance_reader_status": "OFFLINE",
            "exit_reader_status": "OFFLINE",
            "last_activity_time": "N/A",
            "last_activity": "No status file found.",
            "listener_state": "STOPPED",
            "last_scanned_uid": ""
        }

# ===============================
# 🔘 New Auto-Closing Gate Endpoint
# ===============================
def auto_close_gate(gate):
    """Automatically closes gate after 3 seconds."""
    time.sleep(3)
    set_gate_state(gate, False)
    print(f"[AUTO] {gate} gate closed after 3 seconds")

@app.route('/api/open_gate/<gate>', methods=['POST'])
def api_open_gate(gate):
    """Opens a gate for 3 seconds, then auto-closes."""
    gate = gate.upper()
    if gate not in ["ENTRANCE", "EXIT"]:
        return jsonify({"message": "Invalid gate."}), 400

    set_gate_state(gate, True)
    print(f"[API] {gate} gate opened")

    # Threaded auto-close
    threading.Thread(target=auto_close_gate, args=(gate,), daemon=True).start()

    return jsonify({"message": f"{gate} gate opened (auto-closing in 3 seconds)"})

# ===============================
# Other API Endpoints
# ===============================
@app.route('/api/transactions')
def api_transactions():
    try:
        data = fetch_recent_transactions(limit=15)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rfid_status')
def api_rfid_status():
    return jsonify(read_rfid_status())

# ===============================
# Dashboard Route
# ===============================
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST' and 'process_topup' in request.form:
        uid = request.form['topup_uid'].upper()
        try:
            amount = int(request.form['topup_amount'])
            if amount > 0 and re.match(r'[A-F0-9]{8}', uid):
                result = top_up_balance(uid, amount)
                if result:
                    flash(f"✅ Success! {result['Name']} New Balance: ₱{result['Balance']}", 'success')
                    status = read_rfid_status()
                    status['last_scanned_uid'] = ""
                    with open(STATUS_FILE, 'w') as f:
                        json.dump(status, f, indent=4)
                else:
                    flash(f"❌ Top-Up Failed for UID {uid}.", 'error')
            else:
                flash("Invalid UID or amount.", 'error')
        except ValueError:
            flash("Invalid amount entered.", 'error')
        return redirect(url_for('dashboard'))

    status_data = read_rfid_status()
    transactions = fetch_recent_transactions(limit=15)
    return render_template('transactions.html', transactions=transactions, rfid_status=status_data, last_uid=status_data.get('last_scanned_uid', ''))

# ===============================
# Run Flask
# ===============================
if __name__ == '__main__':
    print("✅ Flask Server Running at http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
