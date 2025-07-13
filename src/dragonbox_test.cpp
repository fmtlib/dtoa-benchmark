#include "dragonbox/dragonbox_to_chars.h"
#include "test.h"

void dtoa_dragonbox_comp(double x, char* buffer) {
  jkj::dragonbox::to_chars(x, buffer, jkj::dragonbox::policy::cache::compact);
}

void dtoa_dragonbox_full(double x, char* buffer) {
  jkj::dragonbox::to_chars(x, buffer, jkj::dragonbox::policy::cache::full);
}

REGISTER_TEST(dragonbox_comp);
REGISTER_TEST(dragonbox_full);
