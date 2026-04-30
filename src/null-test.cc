#include "benchmark.h"

static register_method _("null", [](double, char* buffer) -> char* {
  return buffer;
});
