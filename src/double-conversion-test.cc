#include "double-conversion/double-conversion.h"

#include "benchmark.h"

static int register_double_conversion = []() {
  using namespace double_conversion;
  methods.push_back(method{
      "double-conversion", [](double value, char* buffer) {
        StringBuilder sb(buffer, 26);
        DoubleToStringConverter::EcmaScriptConverter().ToShortest(value, &sb);
      }});
  return 0;
}();
