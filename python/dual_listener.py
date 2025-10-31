import serial
import threading

entrance_port = '/dev/ttyUSB0'
exit_port = '/dev/ttyUSB1'
baud_rate = 9600

def listen_to_port(port_name, label):
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1)
        print(f"[{label}] Listening on {port_name}")
        while True:
            line = ser.readline().decode('utf-8').strip()
            if line:
                print(f"[{label}] {line}")
    except serial.SerialException as e:
        print(f"[{label}] ERROR: {e}")

entrance_thread = threading.Thread(target=listen_to_port, args=(entrance_port, "ENTRANCE"))
exit_thread = threading.Thread(target=listen_to_port, args=(exit_port, "EXIT"))

entrance_thread.start()
exit_thread.start()
