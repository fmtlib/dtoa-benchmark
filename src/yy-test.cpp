#include "test.h"

extern "C" char* yy_double_to_string(double val, char* buf);

void dtoa_yy(double value, char* buffer) {
    *yy_double_to_string(value, buffer) = 0;
}

REGISTER_TEST(yy);
