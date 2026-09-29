// ==========================================
// CONFIGURATION FLAG
// ==========================================
const bool USE_USB_SERIAL = false; // Set true for USB Serial, false for Hardware Serial 1

// Define a structure to bundle pins for any given motor
struct Motor {
  int pwmPin;
  int in1Pin;
  int in2Pin;
};

// Define your array of motors. Adjust pins as necessary.
Motor motors[] = {
  {2, 3, 4},  // Motor 0
  {5, 6, 7},  // Motor 1
  {8, 9, 10}  // Motor 2
};

const int NUM_MOTORS = sizeof(motors) / sizeof(motors);

// --- Watchdog Configuration ---
unsigned long lastHeartbeatTime = 0;
const unsigned long TIMEOUT_THRESHOLD = 20; // 20 milliseconds absolute limit
bool systemsHalted = true;                  

// --- Dynamic Stream Pointer ---
Stream* serialSource = nullptr;

void setup() {
  // Always initialize both physical ports so they are ready
  Serial.begin(115200);   // USB Serial
  Serial1.begin(115200);  // Hardware Serial 1 (Pins 18/19)
  
  // Assign our stream pointer based on your boolean flag
  if (USE_USB_SERIAL) {
    serialSource = &Serial;
    Serial.println("SYSTEM: Routing motor commands through USB SERIAL.");
  } else {
    serialSource = &Serial1;
    Serial.println("SYSTEM: Routing motor commands through HARDWARE SERIAL 1.");
  }
  
  // Initialize motor pins
  for (int i = 0; i < NUM_MOTORS; i++) {
    pinMode(motors[i].pwmPin, OUTPUT);
    pinMode(motors[i].in1Pin, OUTPUT);
    pinMode(motors[i].in2Pin, OUTPUT);
  }
  
  haltAllMotors();
  lastHeartbeatTime = millis(); 
}

void loop() {
  // 1. Process data from our active stream source
  processIncomingSerial();

  // 2. Watchdog Check
  if (millis() - lastHeartbeatTime > TIMEOUT_THRESHOLD) {
    if (!systemsHalted) { 
      haltAllMotors();
      // Always print errors to USB Serial so you can see it on your PC
      Serial.println("⚠️ WATCHDOG TRIGGERED: Timeout exceeded, halting all motors!");
    }
  }
}

void processIncomingSerial() {
  const byte numChars = 64; 
  static char receivedChars[numChars];
  static byte ndx = 0;
  char endMarker = '\n'; 
  
  // Use the pointer to check the active serial buffer
  while (serialSource->available() > 0) {
    char rc = serialSource->read();

    if (rc != endMarker) {
      if (ndx < numChars - 1) {
        receivedChars[ndx] = rc;
        ndx++;
      }
    } else {
      receivedChars[ndx] = '\0'; 
      ndx = 0;
      
      // Valid packet frame processed!
      lastHeartbeatTime = millis(); 
      systemsHalted = false;        
      parseAndExecuteAll(receivedChars);
    }
  }
}

void parseAndExecuteAll(char* data) {
  char* token = strtok(data, ",");
  
  for (int i = 0; i < NUM_MOTORS; i++) {
    if (token == NULL) {
      haltAllMotors();
      Serial.println("❌ Error: Packet layout mismatch, unexpected end of line!");
      return;
    }
    int targetSpeed = atoi(token);
    targetSpeed = constrain(targetSpeed, 0, 255);
    
    token = strtok(NULL, ",");
    if (token == NULL) {
      haltAllMotors();
      return;
    }
    char targetDirection = token; 
    
    if (targetDirection == 'F' || targetDirection == 'f') {
      digitalWrite(motors[i].in1Pin, HIGH);
      digitalWrite(motors[i].in2Pin, LOW);
      analogWrite(motors[i].pwmPin, targetSpeed);
    } 
    else if (targetDirection == 'B' || targetDirection == 'b') {
      digitalWrite(motors[i].in1Pin, LOW);
      digitalWrite(motors[i].in2Pin, HIGH);
      analogWrite(motors[i].pwmPin, targetSpeed);
    } 
    else { 
      digitalWrite(motors[i].in1Pin, LOW);
      digitalWrite(motors[i].in2Pin, LOW);
      analogWrite(motors[i].pwmPin, 0);
    }

    token = strtok(NULL, ",");
  }
}

void haltAllMotors() {
  for (int i = 0; i < NUM_MOTORS; i++) {
    digitalWrite(motors[i].in1Pin, LOW);
    digitalWrite(motors[i].in2Pin, LOW);
    analogWrite(motors[i].pwmPin, 0);
  }
  systemsHalted = true;
}
