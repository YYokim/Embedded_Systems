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

String acceptedUIDs[] = {
  "9b687c13",
  "e3fe5d31"
};

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
    display.println("Welcome to MarjEx");
    display.setCursor(0, 30);
    display.println("Please use your card");
    display.display();

    digitalWrite(RED_LED, HIGH);

    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      char uidBuffer[32] = "";
      for (byte i = 0; i < rfid.uid.size; i++) {
        char byteString[3];
        sprintf(byteString, "%02x", rfid.uid.uidByte[i]); // always 2-digit hex
        strcat(uidBuffer, byteString);
      }
      String uid = String(uidBuffer);

      Serial.print("Card UID: ");
      Serial.println(uid);

      if (isAccepted(uid)) {
        digitalWrite(RED_LED, LOW);
        digitalWrite(GREEN_LED, HIGH);
        display.clearDisplay();
        display.setCursor(0, 20);
        display.println("Card accepted.");
        display.setCursor(0, 40);
        display.println("Have a safe trip");
        display.display();

        gateServo.attach(SERVO_PIN);
        gateServo.write(180); 
        delay(2000);
        gateServo.write(0);   
        delay(500);
        gateServo.detach();   

        digitalWrite(GREEN_LED, LOW);
      } else {
        blinkRedTwice();
        display.clearDisplay();
        display.setCursor(0, 20);
        display.println("Card not accepted.");
        display.setCursor(0, 40);
        display.println("Please register your car");
        display.display();
        digitalWrite(RED_LED, HIGH);
      }

      rfid.PICC_HaltA();
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

bool isAccepted(String uid) {
  for (int i = 0; i < sizeof(acceptedUIDs) / sizeof(acceptedUIDs[0]); i++) {
    if (uid == acceptedUIDs[i]) {
      return true;
    }
  }
  return false;
}

void blinkRedTwice() {
  for (int i = 0; i < 2; i++) {
    digitalWrite(RED_LED, LOW);
    delay(300);
    digitalWrite(RED_LED, HIGH);
    delay(300);
  }
}
