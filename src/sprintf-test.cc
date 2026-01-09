#include <cstdio>

#include "benchmark.h"

REGISTER_METHOD("sprintf", [](double value, char* buffer) {
  sprintf(buffer, "%.17g", value);
});
