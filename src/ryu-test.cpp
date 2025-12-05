#include "test.h"
#include "ryu/d2s.c"

void dtoa_ryu(double value, char* buffer) {
  d2s_buffered(value, buffer);
}

REGISTER_TEST(ryu);
