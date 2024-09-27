// Copyright (c) 2024, Victor Zverovich
// License: https://github.com/fmtlib/fmt/blob/master/LICENSE

#include "test.h"
#include <charconv>
#include <limits>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <fmt/format.h>

namespace std {
to_chars_result to_chars(char* first, char*, uint32_t value, int = 10) {
  auto end = fmt::detail::format_decimal(
    first, value, fmt::detail::count_digits(value));
  *end = 0;
  return {end};
}
}

// A fixed-point decimal number.
struct decimal {
  int num_bigits = 0;
  // Each bigit is a 9-digit decimal number.
  uint32_t bigits[100];
  static constexpr int bigit_bound = 1000000000;

  // Bigits are organized as follows:
  //   bigits[0] ... bigits[F - 1].bigits[F] ... bigits[N - 1],
  // where F is fraction_start.
  int fraction_start;

  void shift_left(int n) {
    int offset = *bigits >= (bigit_bound >> n) ? 1 : 0;
    uint32_t carry = 0;
    for (int i = num_bigits - 1; i >= 0; --i) {
      uint64_t bigit = bigits[i];
      bigit = (bigit << n) + carry;
      if (bigit >= bigit_bound) {
        carry = bigit / bigit_bound;
        bigit = bigit % bigit_bound;
      } else {
        carry = 0;
      }
      bigits[i + offset] = static_cast<uint32_t>(bigit);
    }
    if (offset != 0) {
      bigits[0] = carry;
      ++num_bigits;
    }
  }

  void shift_right(int n) {
    uint32_t mask = (1 << n) - 1;
    uint32_t borrow = 0;
    int offset = 0;
    if ((*bigits >> n) == 0 && *bigits != 0) {
      offset = 1;
	    --num_bigits;
      --fraction_start;
      borrow = uint64_t(*bigits) * bigit_bound >> n;
    }
    for (int i = 0; i != num_bigits; ++i) {
      uint64_t bigit = bigits[i + offset];
      uint32_t new_borrow = (bigit & mask) * bigit_bound >> n;
      bigits[i] = borrow + (bigit >> n);
      borrow = new_borrow;
    }
    if (borrow != 0) bigits[num_bigits++] = borrow;
  }

  explicit decimal(double d) {
    int exp;
    int num_bits = std::numeric_limits<double>::digits;
    int64_t v = static_cast<int64_t>(frexp(d, &exp) * (1ull << num_bits));
    if (v < 0) v = -v;
    exp -= num_bits;

    if (exp >= 0) {
      if (v >= bigit_bound) {
        uint32_t upper = v / bigit_bound;
        if (upper != 0) bigits[num_bigits++] = upper;
      }
      bigits[num_bigits++] = v % bigit_bound;
      int i = 0;
      int bits_per_iteration = 29; // 2**29 fits in one bigit.
      for (; i <= exp - bits_per_iteration; i += bits_per_iteration)
        shift_left(bits_per_iteration);
      if (i != exp) shift_left(exp - i);
      fraction_start = num_bigits;
    } else {
      fraction_start = 1;
      if (v >= bigit_bound) {
        uint32_t upper = v / bigit_bound;
        if (upper != 0) {
          bigits[num_bigits++] = upper;
          ++fraction_start;
        }
      }
      bigits[num_bigits++] = v % bigit_bound;
      int i = 0;
      int bits_per_iteration = 9; // 10**9 can only be shifted left 9 bits.
      for (; i - bits_per_iteration >= exp; i -= bits_per_iteration)
        shift_right(bits_per_iteration);
      if (i != exp) shift_right(i - exp);
    }
  }
};

void dtoa(char* buf, double val, int precision) {
  decimal d(val);

  int bigit_index = *d.bigits > 0 ? 0 : 1;
  char* ptr = std::to_chars(buf, buf + precision, d.bigits[bigit_index++]).ptr;
  int count = ptr - buf;
  int exp = (d.fraction_start - bigit_index) * 9 + count - 1;
  for (; bigit_index < d.num_bigits && count <= precision; ++bigit_index) {
    char* block = buf + count;
    ptr = std::to_chars(block, block + 9, d.bigits[bigit_index]).ptr;
    int num_digits = ptr - block, num_zeros = 9 - num_digits;
    if (num_digits < 9) {
      memmove(block + num_zeros, block, num_digits);
      memcpy(block, "00000000", num_zeros);
    }
    count += 9;
  }
  auto has_nonzero = [=]() {
    for (int i = precision + 1; i < count; ++i) {
      if (buf[i] != '0') return true;
    }
    for (int i = bigit_index + 1; i < d.num_bigits; ++i) {
      if (d.bigits[i] != 0) return true;
    }
    return false;
  };
  if (count > precision) {
    char digit = buf[precision];
    if (digit > '5' || digit == '5' &&
        ((buf[precision - 1] % 2) == 1 || has_nonzero())) {
      int i = precision - 1;
      for (; i >= 0 && buf[i] == '9'; --i) buf[i] = '0';
      if (i >= 0) {
        ++buf[i];
      } else {
        buf[0] = '1';
        ++exp;
      }
    }
    count = precision;
  }
  bool negative = signbit(val);
  memmove(buf + 2 + (negative ? 1 : 0), buf + 1, count - 1);
  int offset = 1;
  if (negative) {
    buf[1] = buf[0];
    buf[0] = '-';
    ++offset;
  }
  buf[offset] = '.';
  for (count += offset; count <= precision; ++count) buf[count] = '0';
  buf[count++] = 'e';
  if (exp >= 0) buf[count++] = '+';
  *std::to_chars(buf + count, buf + count + 4, exp).ptr = '\0';
}

void dtoa_puff(double value, char* buffer) {
  dtoa(buffer, value, 17);
}

REGISTER_TEST(puff);
