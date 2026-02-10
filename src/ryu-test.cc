#include "ryu/ryu.h"

#include "benchmark.h"

static register_method _("ryu", [](double value, char* buffer) {
  d2s_buffered(value, buffer);
});
