// UNO Q - microcontroller side. Bench check for the GY-521 (MPU-6050).
// Python calls these over the Bridge:
//   i2c_scan()  -> which addresses answer on each of the core's I2C buses
//   imu_setup() -> finds the MPU-6050, wakes it, sets +-16 g / +-2000 deg/s / 100 Hz
//   imu_read()  -> one raw reading as text: "ax,ay,az,temp,gx,gy,gz"
//
// Wiring (see ActivityWearable/README.md):
//   GY-521 VCC -> 3.3V, GND -> GND, SDA -> SDA, SCL -> SCL (header pins by AREF)
//   XDA, XCL, AD0, INT not connected (AD0 is pulled low on the GY-521 -> address 0x68)

#include <Arduino_RouterBridge.h>
#include <Wire.h>

// The UNO Q core defines three I2C buses. Rather than assume which one the
// header's SDA/SCL pins are on, the scan checks all three.
arduino::ZephyrI2C *const BUSES[] = {&Wire, &Wire1, &Wire2};
const char *const BUS_NAMES[] = {"Wire", "Wire1", "Wire2"};
const int NUM_BUSES = 3;

// MPU-6050 registers (InvenSense register map)
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

// A 1-byte read is either ACKed (something is there) or fails. The usual
// Arduino scan (an empty write) isn't reliable on this core's STM32 driver.
bool answers(arduino::ZephyrI2C *bus, uint8_t addr) {
  if (bus->requestFrom(addr, (size_t)1) != 1) return false;
  bus->read();   // empty the receive buffer
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

String i2c_scan() {
  String out;
  for (int b = 0; b < NUM_BUSES; b++) {
    BUSES[b]->begin();
    if (b) out += " | ";
    out += BUS_NAMES[b];
    out += ":";
    for (uint8_t a = 0x08; a < 0x78; a++) {
      if (answers(BUSES[b], a)) {
        out += " 0x";
        out += String(a, HEX);
      }
    }
  }
  return out;
}

String imu_setup() {
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
  if (!imu) return "not found";

  imu->setClock(400000);   // short jumpers: fast mode is fine
  uint8_t who = 0;
  readRegs(REG_WHO_AM_I, &who, 1);

  writeReg(REG_PWR_MGMT_1, 0x80);   // reset
  delay(100);
  bool ok = writeReg(REG_PWR_MGMT_1, 0x01)       // wake, clock from the X gyro
            && writeReg(REG_CONFIG, 0x03)        // low-pass ~44 Hz accel / 42 Hz gyro
            && writeReg(REG_SMPLRT_DIV, 9)       // 1 kHz / (1 + 9) = 100 Hz
            && writeReg(REG_GYRO_CONFIG, 0x18)   // +-2000 deg/s
            && writeReg(REG_ACCEL_CONFIG, 0x18); // +-16 g
  delay(50);
  uint8_t accelCfg = 0;
  readRegs(REG_ACCEL_CONFIG, &accelCfg, 1);

  String out = String(imuBus) + " addr 0x" + String(imuAddr, HEX) +
               " WHO_AM_I 0x" + String(who, HEX) +
               " ACCEL_CONFIG 0x" + String(accelCfg, HEX);
  out += ok ? " configured" : " CONFIG WRITE FAILED";
  return out;
}

String imu_read() {
  uint8_t b[14];
  if (!imu || !readRegs(REG_ACCEL_XOUT_H, b, 14)) return "";
  String out;
  for (int i = 0; i < 7; i++) {
    int16_t v = (int16_t)((b[2 * i] << 8) | b[2 * i + 1]);
    if (i) out += ",";
    out += (int)v;
  }
  return out;
}

void setup() {
  Bridge.begin();
  // provide_safe: these run on the loop thread, so the Wire calls never overlap
  Bridge.provide_safe("i2c_scan", i2c_scan);
  Bridge.provide_safe("imu_setup", imu_setup);
  Bridge.provide_safe("imu_read", imu_read);
}

void loop() {
}
