#include "zmij/zmij.h"

#include "test.h"

void dtoa_zmij(double x, char* buffer) noexcept {
  zmij::write(buffer, zmij::double_buffer_size, x);
}

REGISTER_TEST(zmij);
