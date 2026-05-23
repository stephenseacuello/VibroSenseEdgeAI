#pragma once
#include <stdint.h>

namespace Inference {

struct Result {
  const char* label;
  float       confidence;
  uint8_t     class_idx;
};

bool   begin();
Result run(const float* ax, const float* ay, const float* az, uint16_t n);

}  // namespace Inference
