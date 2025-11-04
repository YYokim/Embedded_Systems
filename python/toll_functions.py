import os
import firebase_admin
from firebase_admin import credentials, db
import sqlite3
from datetime import datetime

# ===============================
# Firebase Initialization
# ===============================
if not firebase_admin._apps:
    # Dynamically locate embedded.json in the same folder as this script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(script_dir, 'embedded.json')

    cred = credentials.Certificate(json_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://embedded-project-ba95c-default-rtdb.firebaseio.com/'
    })

firebase_ref = db.reference('/RFID')


# ===============================
# SQLite Local Database
# ===============================
def get_db_connection():
    # Dynamically locate the SQLite DB file in the same folder as this script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    db_path = os.path.join(script_dir, 'Toll_System.db')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def insert_transaction(uid, name, address, balance, role, entry_exit):
    """Save scanned user info to local SQLite database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO Transaction_TB (UID, Name, Address, Balance, Role, Type, Date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (uid, name, address, balance, role, entry_exit, current_date))

        conn.commit()
        conn.close()
        print(f"Saved locally → UID: {uid}, Type: {entry_exit}, Balance: ₱{balance}")
    except Exception as e:
        print(f"Database insert error: {e}")
        
# ===============================
# NEW: SQLite Fetch Function for Dashboard
# ===============================
def fetch_recent_transactions(limit=10):
    """Fetch the latest transactions from SQLite for web dashboard display."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ID, UID, Name, Address, Balance, Role, Type, Date
            FROM Transaction_TB
            ORDER BY ID DESC
            LIMIT ?
        ''', (limit,))
        transactions = cursor.fetchall()
        conn.close()
        # Convert Row objects to list of dictionaries for Flask's jsonify
        return [dict(row) for row in transactions]
    except Exception as e:
        print(f"Database fetch error: {e}")
        return []

# ===============================
# Firebase Helper Functions
# ===============================
def get_user_data(uid):
    """Fetch specific UID data from Firebase"""
    try:
        data = firebase_ref.get()
        if not data:
            print("No data found in Firebase.")
            return None

        user_data = data.get(uid)
        if user_data:
            name = user_data.get('Name') or user_data.get('Name:', 'Unknown')
            address = user_data.get('Address', 'N/A')
            balance = user_data.get('Balance', 0)
            role = user_data.get('Role', 'Unknown')

            return {'UID': uid, 'Name': name, 'Address': address, 'Balance': balance, 'Role': role}
        else:
            print(f"UID {uid} not found in Firebase.")
            return None

    except Exception as e:
        print(f"Firebase fetch error: {e}")
        return None


def update_balance_in_firebase(uid, new_balance):
    """Update user's balance in Firebase"""
    try:
        firebase_ref.child(uid).update({'Balance': new_balance})
        print(f"Firebase balance updated → ₱{new_balance}")
    except Exception as e:
        print(f"Firebase update error: {e}")


def deduct_balance(uid, amount=50):
    """Deduct ₱50 from user balance when exiting"""
    user = get_user_data(uid)
    if not user:
        return None

    if user['Balance'] < amount:
        print(f"UID {uid} has insufficient balance (₱{user['Balance']}).")
        return None

    new_balance = user['Balance'] - amount
    update_balance_in_firebase(uid, new_balance)
    user['Balance'] = new_balance
    print(f"Deducted ₱{amount} → New balance: ₱{new_balance}")
    return user


# ===============================
# NEW: Top-Up Function
# ===============================
def top_up_balance(uid, amount):
    """Add top-up amount to user balance and record in local DB"""
    user = get_user_data(uid)
    if not user:
        print("UID not found in Firebase. Cannot top up.")
        return None

    new_balance = user['Balance'] + amount
    update_balance_in_firebase(uid, new_balance)
    user['Balance'] = new_balance

    # Record locally
    insert_transaction(
        user['UID'],
        user['Name'],
        user['Address'],
        user['Balance'],
        user['Role'],
        "Top Up"
    )

    print(f"Top-up successful → New balance: ₱{new_balance}")
    return user
