#include <charconv>
#include <format>

#include "test.h"

void dtoa_to_chars(double value, char* buffer) {
  *std::to_chars(buffer, buffer + 24, value).ptr = '\0';
}

REGISTER_TEST(to_chars);

void dtoa_format(double value, char* buffer) {
  *std::format_to(buffer, "{}", value) = '\0';
}

REGISTER_TEST(format);
