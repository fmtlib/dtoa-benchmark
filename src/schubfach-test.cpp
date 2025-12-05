// {fmt} test with the compact Dragonbox cache (the default).

#include "test.h"
#include "schubfach/schubfach.h"

void dtoa_schubfach(double x, char *buffer) noexcept {
  schubfach::dtoa(x, buffer);
}

REGISTER_TEST(schubfach);
