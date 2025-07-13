// {fmt} test with the full Dragonbox cache.

#include "test.h"

#define FMT_HEADER_ONLY 1

#define FMT_BEGIN_NAMESPACE namespace dragonbox_test { namespace fmt {
#define FMT_END_NAMESPACE }}

namespace dragonbox_test {}
using namespace dragonbox_test;

#undef FMT_USE_FULL_CACHE_DRAGONBOX
#define FMT_USE_FULL_CACHE_DRAGONBOX 1

#include "fmt/compile.h"

void dtoa_fmt_full(double value, char* buffer) {
  buffer = dragonbox_test::fmt::format_to(buffer, FMT_COMPILE("{}"), value);
  *buffer = '\0';
}

REGISTER_TEST(fmt_full);
