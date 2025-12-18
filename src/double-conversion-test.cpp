#include "double-conversion/double-conversion.h"

#include "test.h"

using namespace double_conversion;

void dtoa_double_conversion(double value, char* buffer) {
  StringBuilder sb(buffer, 26);
  DoubleToStringConverter::EcmaScriptConverter().ToShortest(value, &sb);
}

static Test test("double-conversion", dtoa_double_conversion);
