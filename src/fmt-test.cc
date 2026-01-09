#define FMT_HEADER_ONLY 1
#include "benchmark.h"
#include "fmt/compile.h"

REGISTER_METHOD("fmt", [](double value, char* buffer) {
  buffer = fmt::format_to(buffer, FMT_COMPILE("{}"), value);
  *buffer = '\0';
});
