// {fmt} test with the compact Dragonbox cache (the default).

#define FMT_HEADER_ONLY 1
#include "fmt/compile.h"
#include "test.h"

void dtoa_fmt(double value, char* buffer) {
  buffer = fmt::format_to(buffer, FMT_COMPILE("{}"), value);
  *buffer = '\0';
}

REGISTER_TEST(fmt);
