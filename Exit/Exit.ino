#include <Wire.h>
#include <SPI.h>
#include <Servo.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <MFRC522.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

#define TRIG_PIN 9
#define ECHO_PIN 8

#define RED_LED 4
#define GREEN_LED 5

#define SS_PIN 10
#define RST_PIN 7
MFRC522 rfid(SS_PIN, RST_PIN);

#define SERVO_PIN 6
Servo gateServo;

int detectionCount = 0;

void setup() {
  Serial.begin(9600);

  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("OLED failed"));
    while (true);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);

  SPI.begin();
  rfid.PCD_Init();

  gateServo.attach(SERVO_PIN);
  gateServo.write(0);
  gateServo.detach();

  // Notify Python listener that Arduino is ready
  Serial.println("READY");
}

void loop() {
  long distance = getDistance();

  if (distance > 2 && distance <= 10) {
    detectionCount++;
  } else {
    detectionCount = 0;
    digitalWrite(RED_LED, LOW);
    display.clearDisplay();
    display.display();
  }

  if (detectionCount >= 2) {
    display.clearDisplay();
    display.setCursor(0, 10);
    display.println("MarjEx exit");
    display.setCursor(0, 30);
    display.println("Please scan your card");
    display.display();

    digitalWrite(RED_LED, HIGH);

    // When card is scanned, send UID to Python
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      String uid = "";
      for (byte i = 0; i < rfid.uid.size; i++) {
        if (rfid.uid.uidByte[i] < 0x10) uid += "0";
        uid += String(rfid.uid.uidByte[i], HEX);
      }
      uid.toUpperCase();

      // Send UID to Python listener
      Serial.print("UID:");
      Serial.println(uid);

      rfid.PICC_HaltA();
      delay(1000);
    }
  }

  // Listen for commands from Python (listener.py)
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "OPEN") {
      openGate();

      // Send confirmation to Python to update Firebase to true
      Serial.println("FIREBASE:TRUE");
    } 
    else if (command == "CLOSE") {
      closeGate();

      // Send confirmation to Python to update Firebase to false
      Serial.println("FIREBASE:FALSE");
    }
  }

  delay(300);
}

long getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  long distance = duration * 0.034 / 2;

  Serial.print("Distance: ");
  Serial.println(distance);
  return distance;
}

void openGate() {
  Serial.println("Opening gate...");
  digitalWrite(RED_LED, LOW);
  digitalWrite(GREEN_LED, HIGH);

  display.clearDisplay();
  display.setCursor(0, 20);
  display.println("Card accepted.");
  display.setCursor(0, 40);
  display.println("Gate opening...");
  display.display();

  gateServo.attach(SERVO_PIN);
  gateServo.write(90);
  delay(3000);
  gateServo.write(0);
  delay(500);
  gateServo.detach();

  digitalWrite(GREEN_LED, LOW);

  display.clearDisplay();
  display.setCursor(0, 20);
  display.println("Gate closed");
  display.display();

  Serial.println("Gate closed.");
}

void closeGate() {
  Serial.println("Closing gate...");
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED_LED, HIGH);

  gateServo.attach(SERVO_PIN);
  gateServo.write(0);
  delay(500);
  gateServo.detach();

  display.clearDisplay();
  display.setCursor(0, 20);
  display.println("Access denied.");
  display.setCursor(0, 40);
  display.println("Please register your card.");
  display.display();
}
