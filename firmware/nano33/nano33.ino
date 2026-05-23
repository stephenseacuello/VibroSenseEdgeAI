// VibroSense Edge AI — Nano 33 BLE Sense firmware
// See PROJECT_PLAN.md §11.

#include <ArduinoBLE.h>
#include <Arduino_LSM9DS1.h>

#include "src/inference.h"
#include "src/ble_service.h"

constexpr uint16_t SAMPLE_RATE_HZ      = 952;
constexpr uint16_t WINDOW_SIZE         = 256;
constexpr uint32_t WATCHDOG_TIMEOUT_MS = 30000;  // PROJECT_PLAN.md §11.1 (6)

static float ax_buf[WINDOW_SIZE];
static float ay_buf[WINDOW_SIZE];
static float az_buf[WINDOW_SIZE];
static uint16_t fill = 0;
static uint32_t seq  = 0;

static BLEService::Mode lastModeReported = BLEService::Mode::INFER;
static bool             lastConnected    = false;

void setup() {
  Serial.begin(115200);
  // Optional: wait briefly for Serial in DEBUG builds; do not block production boot.

  StatusLed::begin();
  StatusLed::set(StatusLed::State::ADVERTISING);

  if (!IMU.begin()) {
    Serial.println("IMU init failed");
    StatusLed::set(StatusLed::State::ERROR);
    while (true) { StatusLed::update(); delay(50); }
  }
  Serial.print("Accel ODR (Hz): ");
  Serial.println(IMU.accelerationSampleRate());

  if (!Inference::begin()) {
    Serial.println("Inference init failed");
    StatusLed::set(StatusLed::State::ERROR);
    while (true) { StatusLed::update(); delay(50); }
  }

  if (!BLEService::begin()) {
    Serial.println("BLE init failed");
    StatusLed::set(StatusLed::State::ERROR);
    while (true) { StatusLed::update(); delay(50); }
  }
  Serial.println("VibroSense-Nano advertising");
}

void loop() {
  BLEService::poll();
  StatusLed::update();

  // LED reflects connection + mode.
  const bool connected = BLEService::isCentralConnected();
  const BLEService::Mode m = BLEService::mode();
  if (connected != lastConnected || m != lastModeReported) {
    lastConnected = connected;
    lastModeReported = m;
    if (!connected) {
      StatusLed::set(StatusLed::State::ADVERTISING);
    } else if (m == BLEService::Mode::CAPTURE) {
      StatusLed::set(StatusLed::State::CAPTURE);
    } else {
      StatusLed::set(StatusLed::State::CONNECTED);
    }
  }

  // Watchdog: if BLE has been silent for too long while we believe a central
  // is connected, soft-reset the radio. PROJECT_PLAN.md §11.1 (6).
  if (connected && BLEService::msSinceLastPublish() > WATCHDOG_TIMEOUT_MS) {
    Serial.println("watchdog: BLE silent > 30 s, soft-resetting radio");
    BLEService::softReset();
    lastConnected = false;
    StatusLed::set(StatusLed::State::ADVERTISING);
  }

  if (IMU.accelerationAvailable() && fill < WINDOW_SIZE) {
    IMU.readAcceleration(ax_buf[fill], ay_buf[fill], az_buf[fill]);
    fill++;
  }

  if (fill >= WINDOW_SIZE) {
#ifdef DEBUG_TIMING
    const uint32_t t0 = micros();
#endif
    Inference::Result r = Inference::run(ax_buf, ay_buf, az_buf, WINDOW_SIZE);
    seq++;

    if (m == BLEService::Mode::INFER) {
      BLEService::publishState(r.label, r.confidence, millis(), seq);
    } else {
      BLEService::publishRawWindow(ax_buf, ay_buf, az_buf, WINDOW_SIZE);
    }

#ifdef DEBUG_TIMING
    const uint32_t dt = micros() - t0;
    Serial.print("infer_us=");
    Serial.println(dt);
#endif
    fill = 0;  // non-overlapping windows for the initial implementation
  }
}
