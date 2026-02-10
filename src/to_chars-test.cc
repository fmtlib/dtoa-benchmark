#include <charconv>

#include "benchmark.h"

static register_method _("to_chars", [](double value, char* buffer) {
  *std::to_chars(buffer, buffer + 24, value).ptr = '\0';
});
