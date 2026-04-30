#include "ryu/ryu.h"

#include "benchmark.h"

static register_method _("ryu", [](double value, char* buffer) -> char* {
  return buffer + d2s_buffered_n(value, buffer);
});
