#include <iomanip>
#include <sstream>

#include "benchmark.h"

static register_method _("ostringstream", [](double value, char* buffer) {
  std::ostringstream oss;
  oss << std::setprecision(17) << value;
  strcpy(buffer, oss.str().c_str());
});
