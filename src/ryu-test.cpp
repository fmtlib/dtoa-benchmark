#include "ryu/ryu.h"
#include "test.h"

void dtoa_ryu(double value, char* buffer) { d2s_buffered(value, buffer); }

REGISTER_TEST(ryu);
