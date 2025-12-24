#include "zmij/zmij.h"

#include "test.h"

void dtoa_zmij(double x, char* buffer) noexcept {
  zmij::to_string(x, buffer);
}

REGISTER_TEST(zmij);
