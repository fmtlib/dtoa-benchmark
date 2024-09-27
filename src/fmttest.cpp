#define FMT_HEADER_ONLY 1
#define FMT_USE_FULL_CACHE_DRAGONBOX 1
#include "test.h"
#include "fmt/compile.h"

void dtoa_fmt(double value, char* buffer) {
  buffer = fmt::format_to(buffer, FMT_COMPILE("{}"), value);
  *buffer = '\0';
}

REGISTER_TEST(fmt);
