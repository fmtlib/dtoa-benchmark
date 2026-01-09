#include "ryu/ryu.h"

#include "benchmark.h"

REGISTER_METHOD("ryu", [](double value, char* buffer) {
  d2s_buffered(value, buffer);
});
