#include <iomanip>
#include <sstream>

#include "benchmark.h"

REGISTER_METHOD("ostringstream", [](double value, char* buffer) {
  std::ostringstream oss;
  oss << std::setprecision(17) << value;
  strcpy(buffer, oss.str().c_str());
});
