#include "ble_service.h"

#include <Arduino.h>
#include <ArduinoBLE.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>

namespace BLEService {

// Frozen UUIDs — must match ml/src/capture.py + gateway/ble_central.py.
// Generated 2026-05-23. See ADR-0001 for the freeze record.
static const char* SERVICE_UUID    = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e0f";
static const char* STATE_UUID      = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e10";
static const char* MODE_UUID       = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e11";
static const char* VERSION_UUID    = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e12";
static const char* RAW_WINDOW_UUID = "7e5c0001-d9b7-4f12-8a6b-0a0b0c0d0e13";

// raw_window protocol — see ADR-0004.
static constexpr uint16_t SAMPLES_PER_CHUNK = 32;
static constexpr uint16_t HEADER_SIZE       = 8;
static constexpr uint16_t CHUNK_BYTES       = HEADER_SIZE + SAMPLES_PER_CHUNK * 3 * 2;  // 200
static constexpr float    SAMPLE_SCALE      = 1000.0f;

static ::BLEService            gService(SERVICE_UUID);
static BLEStringCharacteristic gState(STATE_UUID, BLERead | BLENotify, 96);
static BLEByteCharacteristic   gMode(MODE_UUID, BLERead | BLEWrite);
static BLEStringCharacteristic gVersion(VERSION_UUID, BLERead, 64);
static BLECharacteristic       gRawWindow(RAW_WINDOW_UUID, BLENotify, CHUNK_BYTES);

static uint32_t gWindowSeq      = 0;
static uint32_t gLastPublishMs  = 0;

bool begin() {
  if (!BLE.begin()) {
    return false;
  }
  BLE.setLocalName("VibroSense-Nano");
  BLE.setAdvertisedService(gService);

  gService.addCharacteristic(gState);
  gService.addCharacteristic(gMode);
  gService.addCharacteristic(gVersion);
  gService.addCharacteristic(gRawWindow);
  BLE.addService(gService);

  gMode.writeValue(static_cast<uint8_t>(Mode::INFER));
  gVersion.writeValue("v0.1-scaffold");
  BLE.advertise();
  gLastPublishMs = millis();
  return true;
}

void poll() {
  BLE.poll();
}

Mode mode() {
  return (gMode.value() == 1) ? Mode::CAPTURE : Mode::INFER;
}

bool isCentralConnected() {
  return BLE.connected();
}

uint32_t msSinceLastPublish() {
  return millis() - gLastPublishMs;
}

bool softReset() {
  BLE.stopAdvertise();
  BLE.disconnect();
  BLE.end();
  if (!BLE.begin()) {
    return false;
  }
  BLE.setLocalName("VibroSense-Nano");
  BLE.setAdvertisedService(gService);
  BLE.addService(gService);
  BLE.advertise();
  gLastPublishMs = millis();
  return true;
}

void publishState(const char* label, float confidence, uint32_t ts_ms, uint32_t seq) {
  char buf[96];
  // Field order is stable per ADR-0001 — easy to grep / diff.
  snprintf(buf,
           sizeof(buf),
           "{\"schema_ver\":1,\"ts_ms\":%lu,\"seq\":%lu,\"state\":\"%s\",\"confidence\":%.3f}",
           static_cast<unsigned long>(ts_ms),
           static_cast<unsigned long>(seq),
           label,
           confidence);
  gState.writeValue(buf);
  gLastPublishMs = millis();
}

static inline int16_t scale_sample(float g) {
  float v = roundf(g * SAMPLE_SCALE);
  if (v >  32767.0f) v =  32767.0f;
  if (v < -32768.0f) v = -32768.0f;
  return static_cast<int16_t>(v);
}

void publishRawWindow(const float* ax, const float* ay, const float* az, uint16_t n) {
  if (n == 0) {
    return;
  }
  gWindowSeq++;
  const uint8_t total_chunks =
      static_cast<uint8_t>((n + SAMPLES_PER_CHUNK - 1) / SAMPLES_PER_CHUNK);

  uint8_t buf[CHUNK_BYTES];

  for (uint8_t idx = 0; idx < total_chunks; ++idx) {
    const uint16_t start = static_cast<uint16_t>(idx) * SAMPLES_PER_CHUNK;
    uint16_t samples = SAMPLES_PER_CHUNK;
    if (start + samples > n) {
      samples = n - start;
    }

    // Header — little-endian to match `ml/src/raw_window.py`.
    buf[0] = static_cast<uint8_t>( gWindowSeq        & 0xFF);
    buf[1] = static_cast<uint8_t>((gWindowSeq >>  8) & 0xFF);
    buf[2] = static_cast<uint8_t>((gWindowSeq >> 16) & 0xFF);
    buf[3] = static_cast<uint8_t>((gWindowSeq >> 24) & 0xFF);
    buf[4] = idx;
    buf[5] = total_chunks;
    buf[6] = static_cast<uint8_t>( samples       & 0xFF);
    buf[7] = static_cast<uint8_t>((samples >> 8) & 0xFF);

    // Payload — int16 LE triples interleaved (ax, ay, az, ax, ...).
    int16_t* out = reinterpret_cast<int16_t*>(buf + HEADER_SIZE);
    for (uint16_t i = 0; i < samples; ++i) {
      const uint16_t s = start + i;
      out[i * 3 + 0] = scale_sample(ax[s]);
      out[i * 3 + 1] = scale_sample(ay[s]);
      out[i * 3 + 2] = scale_sample(az[s]);
    }

    const uint16_t frame_len = HEADER_SIZE + samples * 3 * 2;
    gRawWindow.writeValue(buf, frame_len);
  }
  gLastPublishMs = millis();
}

}  // namespace BLEService

namespace StatusLed {

// The Nano 33 BLE Sense RGB LED is active LOW. LOW = on, HIGH = off.
static constexpr uint8_t ON  = LOW;
static constexpr uint8_t OFF = HIGH;

static State    gState     = State::OFF;
static uint32_t gBlinkAtMs = 0;
static bool     gBlinkOn   = false;

static void apply(uint8_t r, uint8_t g, uint8_t b) {
  digitalWrite(LEDR, r);
  digitalWrite(LEDG, g);
  digitalWrite(LEDB, b);
}

void begin() {
  pinMode(LEDR, OUTPUT);
  pinMode(LEDG, OUTPUT);
  pinMode(LEDB, OUTPUT);
  apply(OFF, OFF, OFF);
}

void set(State s) {
  gState = s;
  switch (s) {
    case State::OFF:         apply(OFF, OFF, OFF); break;
    case State::ADVERTISING: apply(OFF, OFF, ON);  break;
    case State::CONNECTED:   apply(OFF, ON,  OFF); break;
    case State::CAPTURE:     apply(ON,  ON,  OFF); break;  // yellow
    case State::ERROR:       gBlinkAtMs = millis(); gBlinkOn = true; apply(ON, OFF, OFF); break;
  }
}

void update() {
  if (gState != State::ERROR) {
    return;
  }
  const uint32_t now = millis();
  if (now - gBlinkAtMs >= 500) {
    gBlinkAtMs = now;
    gBlinkOn   = !gBlinkOn;
    apply(gBlinkOn ? ON : OFF, OFF, OFF);
  }
}

}  // namespace StatusLed
