// {fmt} test with the compact Dragonbox cache (the default).

#include "schubfach/schubfach.h"

#include "test.h"

void dtoa_schubfach(double x, char* buffer) noexcept {
  schubfach::dtoa(x, buffer);
}

REGISTER_TEST(schubfach);
