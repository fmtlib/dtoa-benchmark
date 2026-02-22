#include "ryu/ryu.h"

#include "benchmark.h"

static register_method _("ryu", [](double value, char* buffer) -> char* {
  d2s_buffered(value, buffer);
  return nullptr;
});
