#include "test.h"
#include "xjb/xjb64.cpp"

void dtoa_xjb64(double x, char* buffer) { xjb64(x, buffer); }

REGISTER_TEST(xjb64);
