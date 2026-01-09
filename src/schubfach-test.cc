// {fmt} test with the compact Dragonbox cache (the default).

#include "schubfach/schubfach.h"

#include "benchmark.h"

REGISTER_METHOD("schubfach", [](double x, char* buffer) noexcept {
  schubfach::dtoa(x, buffer);
});
