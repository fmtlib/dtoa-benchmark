#include <charconv>

#include "benchmark.h"

REGISTER_METHOD("to_chars", [](double value, char* buffer) {
  *std::to_chars(buffer, buffer + 24, value).ptr = '\0';
});
