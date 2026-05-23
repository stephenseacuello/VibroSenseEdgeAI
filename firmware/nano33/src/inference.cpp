// TFLite Micro inference for VibroSense Edge AI.
//
// Loads the INT8 model in ../model/model.h, sets up a static tensor arena, and
// runs one inference per IMU window. Returns class label + dequantized
// confidence to the main sketch.
//
// When `vibrosense_model_tflite_len == 0` (placeholder model.h), `begin()`
// short-circuits and `run()` returns HEALTHY @ 0.0 so the firmware still
// flashes and advertises BLE before a real model has been trained.
//
// Library dependency: install one of
//   arduino-cli lib install --git-url https://github.com/tensorflow/tflite-micro-arduino-examples
//   arduino-cli lib install "Chirale_TensorFlowLite"
// Either provides the standard TFLite Micro headers we include below.

#include "inference.h"
#include "../model/model.h"

#include <math.h>
#include <stdint.h>

#include <TensorFlowLite.h>
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/system_setup.h"
#include "tensorflow/lite/schema/schema_generated.h"

namespace Inference {

static const char* LABELS[] = {
    "HEALTHY",
    "IMBALANCE",
    "LOOSENESS",
    "BEARING_FAULT",
};
static constexpr uint8_t N_CLASSES = sizeof(LABELS) / sizeof(LABELS[0]);

// Arena size: characterized at Wk 5 via the build report on `v0.5`. 32 KB is
// the working budget per PROJECT_PLAN.md §4.2 — adjust if AllocateTensors fails.
constexpr int kTensorArenaSize = 32 * 1024;
alignas(16) static uint8_t s_arena[kTensorArenaSize];

static const tflite::Model*      s_model       = nullptr;
static tflite::MicroInterpreter* s_interpreter = nullptr;
static TfLiteTensor*             s_input       = nullptr;
static TfLiteTensor*             s_output      = nullptr;
static bool                      s_ready       = false;

static inline int8_t clamp_int8(int v) {
  if (v < -128) return -128;
  if (v >  127) return  127;
  return static_cast<int8_t>(v);
}

bool begin() {
  if (vibrosense_model_tflite_len == 0) {
    // Placeholder model.h — flash the firmware, train a real model, then
    // regenerate model.h with `make export` and re-flash to enable inference.
    return true;
  }

  s_model = tflite::GetModel(vibrosense_model_tflite);
  if (s_model->version() != TFLITE_SCHEMA_VERSION) {
    return false;
  }

  // Narrow op resolver — only the ops emitted by the 1D-CNN spec
  // (PROJECT_PLAN.md §10.3). Saves tens of KB of flash vs AllOpsResolver.
  // If the architecture changes, add the new op via `.Add*()` and bump the
  // template parameter to match.
  static tflite::MicroMutableOpResolver<7> resolver;
  resolver.AddConv2D();          // Keras Conv1D → TFLite CONV_2D (height = 1)
  resolver.AddMaxPool2D();       // Keras MaxPool1D
  resolver.AddMean();            // GlobalAveragePooling1D
  resolver.AddFullyConnected();  // Dense
  resolver.AddRelu();
  resolver.AddSoftmax();
  resolver.AddReshape();         // emitted for input flattening / GAP output

  static tflite::MicroInterpreter interpreter(s_model, resolver, s_arena, kTensorArenaSize);
  s_interpreter = &interpreter;

  if (s_interpreter->AllocateTensors() != kTfLiteOk) {
    return false;
  }

  s_input  = s_interpreter->input(0);
  s_output = s_interpreter->output(0);

  // Sanity-check tensor shapes against the 1D-CNN spec.
  // Expect input: (1, WINDOW_SIZE, 3) int8; output: (1, N_CLASSES) int8.
  if (s_input == nullptr || s_output == nullptr) {
    return false;
  }
  if (s_input->type != kTfLiteInt8 || s_output->type != kTfLiteInt8) {
    return false;
  }

  s_ready = true;
  return true;
}

Result run(const float* ax, const float* ay, const float* az, uint16_t n) {
  if (!s_ready) {
    // No model loaded — graceful fallback so the BLE / capture path still works.
    return Result{LABELS[0], 0.0f, 0};
  }

  const float in_scale = s_input->params.scale;
  const int   in_zp    = s_input->params.zero_point;
  if (in_scale <= 0.0f) {
    return Result{LABELS[0], 0.0f, 0};
  }

  // The model input is laid out (1, n, 3) with ax/ay/az interleaved per sample.
  // Quantize float g-values into the int8 input tensor.
  int8_t* dst = s_input->data.int8;
  for (uint16_t i = 0; i < n; ++i) {
    const float fax = ax[i] / in_scale + static_cast<float>(in_zp);
    const float fay = ay[i] / in_scale + static_cast<float>(in_zp);
    const float faz = az[i] / in_scale + static_cast<float>(in_zp);
    dst[i * 3 + 0] = clamp_int8(static_cast<int>(roundf(fax)));
    dst[i * 3 + 1] = clamp_int8(static_cast<int>(roundf(fay)));
    dst[i * 3 + 2] = clamp_int8(static_cast<int>(roundf(faz)));
  }

  if (s_interpreter->Invoke() != kTfLiteOk) {
    return Result{LABELS[0], 0.0f, 0};
  }

  // Argmax over the int8 output, then dequantize the winning logit to a
  // [0, 1] confidence. For softmax outputs the dequantized value is already
  // a probability — we clamp to [0, 1] in case of rounding artifacts.
  uint8_t best   = 0;
  int8_t  best_q = s_output->data.int8[0];
  for (uint8_t i = 1; i < N_CLASSES; ++i) {
    if (s_output->data.int8[i] > best_q) {
      best_q = s_output->data.int8[i];
      best = i;
    }
  }

  const float out_scale = s_output->params.scale;
  const int   out_zp    = s_output->params.zero_point;
  float confidence = (static_cast<float>(best_q) - static_cast<float>(out_zp)) * out_scale;
  if (confidence < 0.0f) confidence = 0.0f;
  if (confidence > 1.0f) confidence = 1.0f;

  return Result{LABELS[best], confidence, best};
}

}  // namespace Inference
