#include "dragonbox/dragonbox_to_chars.h"
#include "test.h"

void dtoa_dragonbox(double x, char* buffer) {
  jkj::dragonbox::to_chars(x, buffer, jkj::dragonbox::policy::cache::full);
}

REGISTER_TEST(dragonbox);
