#include "benchmark.h"
#include "xjb/xjb64.h"

REGISTER_METHOD("xjb64", [](double x, char* buffer) { xjb64(x, buffer); });
