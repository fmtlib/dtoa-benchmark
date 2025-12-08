#include "zmij/zmij.h"

#include "test.h"

void dtoa_zmij(double x, char* buffer) noexcept {
  zmij::dtoa(x, buffer);
}

REGISTER_TEST(zmij);
