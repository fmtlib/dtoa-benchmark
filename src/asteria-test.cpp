#include "asteria/ascii_numput.hpp"
#include "test.h"

void dtoa_asteria(double x, char* buffer) noexcept {
  rocket::ascii_numput p;
  p.put_DD(x);
  strcpy(buffer, p.data());
}

REGISTER_TEST(asteria);
