#include <iomanip>
#include <sstream>
#include <string.h>

#include "benchmark.h"

static register_method _("ostringstream", [](double value, char* buffer) {
  std::ostringstream oss;
  oss << std::setprecision(17) << value;
  std::string s = oss.str();
  memcpy(buffer, s.data(), s.size());
  return buffer + s.size();
});
