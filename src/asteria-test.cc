#include "asteria/ascii_numput.hpp"
#include "benchmark.h"

static register_method _("asteria", [](double value, char* buffer) -> char* {
  rocket::ascii_numput p;
  p.put_DD(value);
  strcpy(buffer, p.data());
  return nullptr;
});
