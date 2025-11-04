import serial
import re
from toll_functions import top_up_balance, get_user_data

port = '/dev/ttyUSB0'  # Change to your RFID reader port
baud_rate = 9600

print("=== RFID Top-Up Mode ===")
print("Waiting for RFID card...")

with serial.Serial(port, baud_rate, timeout=1) as ser:
    while True:
        line = ser.readline().decode('utf-8').strip()
        if not line:
            continue

        # Only consider lines that look like valid UID (8 hex characters)
        match = re.search(r'\b[A-F0-9]{8}\b', line, re.IGNORECASE)
        if not match:
            continue  # Ignore any startup messages or noise

        uid = match.group(0).upper()
        print(f"Detected UID: {uid}")

        # Fetch user info from Firebase
        user = get_user_data(uid)
        if not user:
            print("UID not found in Firebase. Try again.")
            continue

        print(f"User: {user['Name']} | Current Balance: ₱{user['Balance']}")
        try:
            amount = int(input("Enter top-up amount: ₱"))
            top_up_balance(uid, amount)
            print("Top-up successful!\n")
            print("Waiting for next RFID card...\n")
        except ValueError:
            print("Invalid input. Please enter a number.")
