// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

// The Infallible Safe's microcontroller side: the LED matrix and the door's servo.
// What to show and where the servo goes is decided on the Linux side
// (python/main.py, python/leds.py); this sketch just does it.
//
// LED matrix: the generic frame receiver copied from ArduinoDisplay/sketch:
// keeps redrawing whatever frame Python last pushed with Bridge "draw".
//
// Servo: Bridge "servo" takes an angle, 0-180. The Zephyr core on the board
// (1.0.0) has no Servo library, so the sketch makes the pulses itself: a pulse
// every 20 ms on SERVO_PIN, 500-2400 us wide for 0-180 degrees (a micro servo's
// usual range). The pulses only run for SERVO_MOVE_MS after each move, then
// stop: software-timed pulses get stretched now and then by the board's other
// work, and a stretched pulse is a different angle, so a servo held with
// pulses twitches. Unpowered, its gears still hold the arm, and pulling the
// door pushes along the shaft rather than turning it. An angle below 0 stops
// the pulses at once.
// Wiring: servo signal (orange/yellow) to D9, red to 5V, brown/black to GND.
//
// Button: the safe's start button between D2 and GND (its COM to GND, NO to
// D2; NC works too, because the sketch learns the button's resting level at
// start, so don't hold it down while the board starts). The sketch counts
// presses (debounced), and Bridge "button" returns how many since Python
// last asked, so a quick press between two camera frames isn't missed.

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>

Arduino_LED_Matrix matrix;

const uint8_t FRAME_ROWS = 8;
const uint8_t FRAME_COLS = 13;
const uint8_t FRAME_SIZE = FRAME_ROWS * FRAME_COLS;
uint8_t frame[FRAME_SIZE] = {0};

const int SERVO_PIN = 9;
const unsigned long SERVO_PERIOD_US = 20000;   // 50 Hz
const int SERVO_MIN_US = 500;                  // pulse width at 0 degrees
const int SERVO_MAX_US = 2400;                 // pulse width at 180 degrees
const unsigned long SERVO_MOVE_MS = 1000;      // pulse this long after a move (a full sweep takes ~0.4 s)
int servoPulseUs = 0;                          // 0 = no pulses
unsigned long servoStopMs = 0;                 // when the pulses stop
unsigned long lastPulseUs = 0;
unsigned long lastDrawUs = 0;

const int BUTTON_PIN = 2;
const unsigned long DEBOUNCE_MS = 30;
int buttonRest = HIGH;                         // its level when not pressed (read at start)
int buttonStable = HIGH;                       // last debounced level
int buttonRaw = HIGH;
unsigned long buttonRawMs = 0;                 // when buttonRaw last changed
int buttonPresses = 0;                         // since Python last asked

int button() {                                 // Bridge "button" (provide_safe: runs in loop()'s thread)
  int n = buttonPresses;
  buttonPresses = 0;
  return n;
}

void readButton() {
  int raw = digitalRead(BUTTON_PIN);
  unsigned long now = millis();
  if (raw != buttonRaw) {
    buttonRaw = raw;
    buttonRawMs = now;
  } else if (raw != buttonStable && now - buttonRawMs >= DEBOUNCE_MS) {
    buttonStable = raw;
    if (raw != buttonRest) buttonPresses++;    // it just left its resting level: a press
  }
}

void draw(std::vector<uint8_t> newFrame) {
  size_t len = min(newFrame.size(), (size_t)FRAME_SIZE);
  memcpy(frame, newFrame.data(), len);
}

void servo(int angle) {                        // Bridge "servo" (provide_safe: runs in loop()'s thread)
  if (angle < 0) {
    servoPulseUs = 0;
    return;
  }
  angle = constrain(angle, 0, 180);
  servoPulseUs = map(angle, 0, 180, SERVO_MIN_US, SERVO_MAX_US);
  servoStopMs = millis() + SERVO_MOVE_MS;
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);  // brightness values 0-7, matches Frame()
  matrix.clear();
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  delay(10);
  buttonRest = buttonStable = buttonRaw = digitalRead(BUTTON_PIN);

  Bridge.begin();
  Bridge.provide("draw", draw);
  Bridge.provide_safe("servo", servo);
  Bridge.provide_safe("button", button);
}

void loop() {
  unsigned long now = micros();
  if (servoPulseUs > 0 && (long)(millis() - servoStopMs) >= 0) {
    servoPulseUs = 0;                            // moved: stop pulsing so it can't twitch
  }
  int pulse = servoPulseUs;
  if (pulse > 0 && now - lastPulseUs >= SERVO_PERIOD_US) {
    lastPulseUs = now;
    digitalWrite(SERVO_PIN, HIGH);
    delayMicroseconds(pulse);
    digitalWrite(SERVO_PIN, LOW);
  }
  if (now - lastDrawUs >= 10000) {
    lastDrawUs = now;
    matrix.draw(frame);
  }
  readButton();
  delay(1);  // let the bridge's thread run
}
