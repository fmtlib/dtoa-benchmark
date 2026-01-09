#include "benchmark.h"

extern "C" char* yy_double_to_string(double val, char* buf);

static register_method _("yy", [](double value, char* buffer) {
  *yy_double_to_string(value, buffer) = 0;
});
