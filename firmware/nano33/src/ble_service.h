#pragma once
#include <stdint.h>

namespace BLEService {

enum class Mode : uint8_t {
  INFER   = 0,
  CAPTURE = 1,
};

bool begin();
void poll();
Mode mode();
bool isCentralConnected();

// JSON state payload — see PROJECT_PLAN.md §14.1 and ADR-0001.
void publishState(const char* label, float confidence, uint32_t ts_ms, uint32_t seq);

// Raw window — chunked binary frames per ADR-0004.
void publishRawWindow(const float* ax, const float* ay, const float* az, uint16_t n);

// Milliseconds since the most recent successful publish on either characteristic.
// Used by the watchdog in the main loop to recover from stuck BLE.
uint32_t msSinceLastPublish();

// Soft-reset BLE radio: tear down advertising, restart, then advertise again.
// Returns true on success.
bool softReset();

}  // namespace BLEService

namespace StatusLed {

// Visible at-a-glance device health on the Nano 33 BLE Sense's RGB LED.
//   ADVERTISING: blue solid
//   CONNECTED:   green solid
//   CAPTURE:     yellow solid (R + G)
//   ERROR:       red blinking (caller drives the blink cadence via update())
enum class State : uint8_t {
  OFF         = 0,
  ADVERTISING = 1,
  CONNECTED   = 2,
  CAPTURE     = 3,
  ERROR       = 4,
};

void begin();
void set(State s);
// Call from loop() so the ERROR state can blink without blocking.
void update();

}  // namespace StatusLed
