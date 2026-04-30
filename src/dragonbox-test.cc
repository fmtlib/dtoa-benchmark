#include "benchmark.h"
#include "dragonbox/dragonbox_to_chars.h"

static register_method _("dragonbox", [](double value, char* buffer) -> char* {
  return jkj::dragonbox::to_chars_n(value, buffer,
                                    jkj::dragonbox::policy::cache::full);
});
