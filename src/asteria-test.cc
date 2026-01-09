#include "asteria/ascii_numput.hpp"
#include "benchmark.h"

REGISTER_METHOD("asteria", [](double value, char* buffer) {
  rocket::ascii_numput p;
  p.put_DD(value);
  strcpy(buffer, p.data());
});
