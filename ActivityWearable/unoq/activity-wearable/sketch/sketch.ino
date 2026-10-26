// UNO Q - microcontroller side of the activity wearable.
//
// Samples the GY-521 (MPU-6050) at 100 Hz on its own clock into a ring
// buffer, and Python drains it over the Bridge in small batches. One call per
// sample would be too slow (a Bridge round trip is ~10 ms), and a batch has to
// fit the Bridge's 256-byte RPC buffer. Python also pushes LED matrix frames.
//
// Bridge calls (all provide_safe, so they run on the loop thread and never
// overlap with sampling):
//   imu_status() -> "Wire 0x68 WHO_AM_I 0x68" or "not found"
//   imu_batch()  -> "<first seq>,<drops>,<read errors>,<hex>": up to MAX_BATCH
//                   consecutive samples, each 6 big-endian int16 as 24 hex chars,
//                   ax ay az gx gy gz raw (2048 LSB/g, 16.4 LSB per deg/s).
//                   seq counts 10 ms ticks since boot, so a gap in seq is a
//                   missed sample.
//   draw(frame)  -> show a 13x8 frame (104 brightness values, 0-7)
//
// Wiring: GY-521 VCC -> 3.3V, GND -> GND, SDA -> SDA, SCL -> SCL (header by AREF).

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <Wire.h>
#include <vector>

// ---- LED matrix -------------------------------------------------------------
Arduino_LED_Matrix matrix;
const size_t FRAME_SIZE = 8 * 13;
uint8_t frame[FRAME_SIZE] = {0};
bool frameDirty = true;

// ---- IMU --------------------------------------------------------------------
// The core has three I2C buses; the bench check found the GY-521 on Wire, but
// searching all three costs nothing.
arduino::ZephyrI2C *const BUSES[] = {&Wire, &Wire1, &Wire2};
const char *const BUS_NAMES[] = {"Wire", "Wire1", "Wire2"};
const int NUM_BUSES = 3;

const uint8_t REG_SMPLRT_DIV = 0x19;
const uint8_t REG_CONFIG = 0x1A;
const uint8_t REG_GYRO_CONFIG = 0x1B;
const uint8_t REG_ACCEL_CONFIG = 0x1C;
const uint8_t REG_ACCEL_XOUT_H = 0x3B;   // 14 bytes: accel xyz, temp, gyro xyz
const uint8_t REG_PWR_MGMT_1 = 0x6B;
const uint8_t REG_WHO_AM_I = 0x75;

arduino::ZephyrI2C *imu = nullptr;
uint8_t imuAddr = 0;
const char *imuBus = "";
uint8_t whoAmI = 0;
uint32_t lastFindMs = 0;
uint32_t errorStreak = 0;

// ---- Sampling ---------------------------------------------------------------
const uint32_t PERIOD_US = 10000;   // 100 Hz
const int RING = 128;               // 1.28 s of samples (divides 2^32, so counters can wrap)
const int MAX_BATCH = 7;            // 7 x 24 hex chars + header stays under the 256-byte RPC buffer

struct Sample {
  uint32_t seq;
  int16_t v[6];
};
Sample ring[RING];
uint32_t written = 0, sent = 0;   // samples put into / taken out of the ring
uint32_t seq = 0;                 // 10 ms ticks since boot
uint32_t drops = 0;               // samples lost because Python fell behind
uint32_t readErrors = 0;          // failed I2C reads
uint32_t nextUs = 0;

bool answers(arduino::ZephyrI2C *bus, uint8_t addr) {
  if (bus->requestFrom(addr, (size_t)1) != 1) return false;
  bus->read();
  return true;
}

bool writeReg(uint8_t reg, uint8_t val) {
  imu->beginTransmission(imuAddr);
  imu->write(reg);
  imu->write(val);
  return imu->endTransmission() == 0;
}

bool readRegs(uint8_t reg, uint8_t *buf, size_t n) {
  imu->beginTransmission(imuAddr);
  imu->write(reg);
  if (imu->endTransmission() != 0) return false;
  if (imu->requestFrom(imuAddr, n) != n) return false;
  for (size_t i = 0; i < n; i++) buf[i] = imu->read();
  return true;
}

// Find the MPU-6050 and set it to +-16 g, +-2000 deg/s, ~44 Hz low-pass, 100 Hz.
void findImu() {
  const uint8_t addrs[] = {0x68, 0x69};
  imu = nullptr;
  for (int b = 0; b < NUM_BUSES && !imu; b++) {
    BUSES[b]->begin();
    for (uint8_t a : addrs) {
      if (answers(BUSES[b], a)) {
        imu = BUSES[b];
        imuAddr = a;
        imuBus = BUS_NAMES[b];
        break;
      }
    }
  }
  if (!imu) return;
  imu->setClock(400000);
  readRegs(REG_WHO_AM_I, &whoAmI, 1);
  writeReg(REG_PWR_MGMT_1, 0x80);   // reset
  delay(100);
  bool ok = writeReg(REG_PWR_MGMT_1, 0x01)       // wake, clock from the X gyro
            && writeReg(REG_CONFIG, 0x03)        // low-pass ~44 Hz accel / 42 Hz gyro
            && writeReg(REG_SMPLRT_DIV, 9)       // 1 kHz / (1 + 9) = 100 Hz
            && writeReg(REG_GYRO_CONFIG, 0x18)   // +-2000 deg/s
            && writeReg(REG_ACCEL_CONFIG, 0x18); // +-16 g
  if (!ok) imu = nullptr;
  delay(20);
  errorStreak = 0;
}

void takeSample() {
  uint32_t s = seq++;
  if (!imu) return;
  uint8_t b[14];
  if (!readRegs(REG_ACCEL_XOUT_H, b, 14)) {
    readErrors++;
    if (++errorStreak > 50) imu = nullptr;   // half a second of failures: look for it again
    return;
  }
  errorStreak = 0;
  if (written - sent >= (uint32_t)RING) {   // Python fell behind: drop the oldest
    sent++;
    drops++;
  }
  Sample &out = ring[written % RING];
  out.seq = s;
  const int word[6] = {0, 1, 2, 4, 5, 6};   // skip temperature (word 3)
  for (int i = 0; i < 6; i++) {
    out.v[i] = (int16_t)((b[2 * word[i]] << 8) | b[2 * word[i] + 1]);
  }
  written++;
}

// ---- Bridge calls -----------------------------------------------------------
String imu_status() {
  if (!imu) return "not found";
  return String(imuBus) + " 0x" + String(imuAddr, HEX) + " WHO_AM_I 0x" + String(whoAmI, HEX);
}

String imu_batch() {
  String hex;
  hex.reserve(MAX_BATCH * 24);
  uint32_t first = 0;
  int n = 0;
  while (sent != written && n < MAX_BATCH) {
    Sample &s = ring[sent % RING];
    if (n == 0) first = s.seq;
    else if (s.seq != first + n) break;   // a gap: the next batch starts after it
    for (int i = 0; i < 6; i++) {
      char buf[5];
      snprintf(buf, sizeof buf, "%04x", (uint16_t)s.v[i]);
      hex += buf;
    }
    sent++;
    n++;
  }
  return String(first) + "," + String(drops) + "," + String(readErrors) + "," + hex;
}

void draw(std::vector<uint8_t> newFrame) {
  size_t len = min(newFrame.size(), FRAME_SIZE);
  memcpy(frame, newFrame.data(), len);
  frameDirty = true;
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);   // brightness 0-7, matches Python's Frame()
  matrix.clear();

  Bridge.begin();
  Bridge.provide_safe("imu_status", imu_status);
  Bridge.provide_safe("imu_batch", imu_batch);
  Bridge.provide_safe("draw", draw);

  findImu();
  nextUs = micros();
}

void loop() {
  uint32_t now = micros();
  int32_t late = (int32_t)(now - nextUs);
  if (late >= 0) {
    if (late > (int32_t)(5 * PERIOD_US)) {
      // Far behind (something blocked the loop): skip the missed ticks so
      // seq stays true to time, instead of bursting out stale samples.
      uint32_t missed = late / PERIOD_US;
      seq += missed;
      nextUs += missed * PERIOD_US;
    }
    nextUs += PERIOD_US;
    takeSample();
  }
  if (!imu && millis() - lastFindMs > 1000) {
    lastFindMs = millis();
    findImu();
  }
  if (frameDirty) {
    matrix.draw(frame);
    frameDirty = false;
  }
}
