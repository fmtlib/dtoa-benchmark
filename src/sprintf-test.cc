#include <cstdio>

#include "benchmark.h"

static register_method _("sprintf", [](double value, char* buffer) -> char* {
  return buffer + sprintf(buffer, "%.17g", value);
});
