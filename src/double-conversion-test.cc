#include "double-conversion/double-conversion.h"

#include "benchmark.h"

static register_method _("double-conversion", [](double value, char* buffer) -> char* {
  using namespace double_conversion;
  StringBuilder sb(buffer, 26);
  DoubleToStringConverter::EcmaScriptConverter().ToShortest(value, &sb);
  return nullptr;
});
