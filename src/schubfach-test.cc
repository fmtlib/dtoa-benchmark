// {fmt} test with the compact Dragonbox cache (the default).

#include "schubfach/schubfach.h"

#include "benchmark.h"

static register_method _("schubfach", [](double x, char* buffer) noexcept {
  schubfach::dtoa(x, buffer);
});
