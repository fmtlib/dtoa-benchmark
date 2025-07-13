// {fmt} test with the compact Dragonbox cache (the default).

#define FMT_HEADER_ONLY 1
#include "test.h"
#include "fmt/compile.h"

void dtoa_fmt_comp(double value, char* buffer) {
  buffer = fmt::format_to(buffer, FMT_COMPILE("{}"), value);
  *buffer = '\0';
}

REGISTER_TEST(fmt_comp);
