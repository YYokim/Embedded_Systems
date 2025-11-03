import serial
import threading
import re
import json
from datetime import datetime
from toll_functions import get_user_data, deduct_balance, insert_transaction  # Firebase helper functions

# ===============================
# Serial Configuration
# ===============================
entrance_port = ''   # Edit port for entrance
exit_port = ''      # Edit port for exit
baud_rate = 9600
print_lock = threading.Lock()
STATUS_FILE = 'rfid_status.json' #if doesnt work, add a rfid_status.json file directly

# ===============================
# NEW: RFID Status Reporting Function
# ===============================
def update_rfid_status(reader_label, message):
    """Writes the latest activity to a shared JSON file for the web dashboard."""
    try:
        # Attempt to read existing data
        try:
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Default state if file is new or corrupt
            data = {
                "entrance_reader_status": "Listening...",
                "exit_reader_status": "Listening...",
                "listener_state": "RUNNING"
            }

        # Update specific fields based on the event
        if reader_label == "ENTRANCE":
            data["entrance_reader_status"] = message
        elif reader_label == "EXIT":
            data["exit_reader_status"] = message
        
        data["last_activity_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data["last_activity"] = f"[{reader_label}] {message}"
        
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        # Log the error, but don't crash the main listener thread
        print(f"[STATUS-UPDATE-ERROR] {e}")

# ===============================
# UID Cleaning Function
# ===============================
def clean_uid(uid_raw):
    """Extract valid 8-character UID from RFID reader string"""
    uid_raw = uid_raw.strip()
    match = re.search(r'\b[A-F0-9]{8}\b', uid_raw, re.IGNORECASE)
    return match.group(0).upper() if match else None


# ===============================
# RFID Listening Thread
# ===============================
def listen_to_port(port_name, label):
    """Continuously listen to RFID serial port"""
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1)
        print(f"[{label}] Listening on {port_name}")
        update_rfid_status(label, "Listening...")

        while True:
            line = ser.readline().decode('utf-8').strip()
            if not line or "Card detected!" in line or "Scan your RFID" in line:
                continue

            with print_lock:
                print(f"[{label}] Scanned UID: {line}")
                cleaned_uid = clean_uid(line)
                if not cleaned_uid:
                    continue

                # Fetch user info from Firebase
                user_info = get_user_data(cleaned_uid)
                if not user_info:
                    print(f"[{label}] UID not found in Firebase → Access Denied")
                    ser.write(b'CLOSE\n')
                    update_rfid_status(label, f"Access Denied: UID {cleaned_uid} Not Found")
                    continue

                access_granted = False

                if label == "EXIT":
                    # Deduct ₱50 if EXIT
                    updated_user = deduct_balance(cleaned_uid)
                    if updated_user:
                        user_info = updated_user
                        access_granted = True if user_info['Balance'] >= 0 else False
                    else:
                        access_granted = False
                else:
                    # ENTRANCE: Allow entry only if balance > 0
                    if user_info['Balance'] > 0:
                        access_granted = True
                    else:
                        print(f"[{label}] Insufficient balance → ₱{user_info['Balance']}. Access Denied.")
                        access_granted = False

                # Control Arduino servo
                if access_granted:
                    ser.write(b'OPEN\n')
                    print(f"[{label}] Access Granted → Opening gate...")
                else:
                    ser.write(b'CLOSE\n')
                    print(f"[{label}] Access Denied → Gate remains closed.")

                # Record every scan (entry or exit)
                insert_transaction(
                    user_info['UID'],
                    user_info['Name'],
                    user_info['Address'],
                    user_info['Balance'],
                    user_info['Role'],
                    "Entry" if label == "ENTRANCE" else "Exit"
                )

    except serial.SerialException as e:
        with print_lock:
            print(f"[{label}] Serial error: {e}")
    except Exception as e:
        with print_lock:
            print(f"[{label}] Unexpected error: {e}")


# ===============================
# Start Threads for Both Readers
# ===============================
try:
    entrance_thread = threading.Thread(target=listen_to_port, args=(entrance_port, "ENTRANCE"))
    exit_thread = threading.Thread(target=listen_to_port, args=(exit_port, "EXIT"))

    entrance_thread.start()
    exit_thread.start()

    entrance_thread.join()
    exit_thread.join()

except KeyboardInterrupt:
    print("Program interrupted. Exiting...")
