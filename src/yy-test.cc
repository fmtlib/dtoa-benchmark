#include "benchmark.h"

extern "C" char* yy_double_to_string(double val, char* buf);

REGISTER_METHOD("yy", [](double value, char* buffer) {
  *yy_double_to_string(value, buffer) = 0;
});
