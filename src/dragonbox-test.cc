#include "benchmark.h"
#include "dragonbox/dragonbox_to_chars.h"

static register_method _("dragonbox", [](double value, char* buffer) {
  jkj::dragonbox::to_chars(value, buffer, jkj::dragonbox::policy::cache::full);
});
