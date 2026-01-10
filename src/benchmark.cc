// A rewrite of Milo Yip's dtoa-benchmark.
// Copyright (c) 2025 - present, Victor Zverovich
// Distributed under the MIT license.

#include "benchmark.h"

#include <math.h>    // isnan
#include <stdint.h>  // uint64_t
#include <stdio.h>   // snprintf

#include <algorithm>  // std::sort
#include <chrono>

#include "double-conversion/double-conversion.h"
#include "fmt/format.h"

constexpr int max_digits = std::numeric_limits<double>::max_digits10;
constexpr int num_doubles_per_digit = 100'000;

std::vector<method> methods;

#ifndef MACHINE
#  define MACHINE "unknown"
#endif

auto os_name() -> const char* {
#if defined(__linux__)
  return "linux";
#elif defined(__APPLE__)
  return "macos";
#elif define(_WIN32)
  return "windows";
#endif
  return "unknown";
}

#define DO_STRINGIFY(x) #x
#define STRINGIFY(x) DO_STRINGIFY(x)

auto compiler_name() -> const char* {
#if defined(__clang__)
  return "clang" STRINGIFY(__clang_major__) "." STRINGIFY(__clang_minor__);
#elif defined(__GNUC__)
  return "gcc" STRINGIFY(__GNUC__) "." STRINGIFY(__GNUC_MINOR__);
#elif defined(_MSC_VER)
  return "msvc";
#endif
  return "unknown";
}

struct from_chars_result {
  double value;
  size_t count;
};

auto from_chars(const char* buffer) -> from_chars_result {
  using namespace double_conversion;
  StringToDoubleConverter converter(
      StringToDoubleConverter::ALLOW_TRAILING_JUNK, 0.0, 0.0, NULL, NULL);
  int count = 0;
  double value = converter.StringToDouble(buffer, 1024, &count);
  return {value, size_t(count)};
}

// Random number generator from dtoa-benchmark.
class rng {
 private:
  unsigned seed_;

  auto next() -> unsigned {
    seed_ = 214013 * seed_ + 2531011;
    return seed_;
  }

 public:
  explicit rng(unsigned seed = 0) : seed_(seed) {}

  auto operator()() -> double {
    uint64_t bits = 0;
    bits = uint64_t(next()) << 32;
    bits |= next();  // Must be a separate statement to prevent reordering.
    double d = 0;
    memcpy(&d, &bits, sizeof(d));
    return d;
  }
};

void verify(const method& m) {
  if (m.name == "null") return;

  fmt::print("Verifying {:20} ... ", m.name);

  bool first = true;
  auto verify_value = [&](double value, dtoa_fun dtoa, const char* expected) {
    char buffer[1024] = {};
    dtoa(value, buffer);

    if (expected && strcmp(buffer, expected) != 0) {
      if (first) {
        fmt::print("\n");
        first = false;
      }
      fmt::print("warning: expected {} but got {}\n", expected, buffer);
    }

    size_t len = strlen(buffer);
    auto [roundtrip, count] = from_chars(buffer);
    if (len != count) {
      fmt::print("error: some extra character {} -> '{}'\n", value, buffer);
      throw std::exception();
    }
    if (value != roundtrip) {
      fmt::print("error: roundtrip fail {} -> '{}' -> {}\n", value, buffer,
                 roundtrip);
      throw std::exception();
    }
    return len;
  };

  // Verify boundary and simple cases.
  // This gives benign errors in ostringstream and sprintf:
  // Error: expect 0.1 but actual 0.10000000000000001
  // Error: expect 1.2345 but actual 1.2344999999999999
  struct test_case {
    double value;
    const char* expected;
  };
  const test_case cases[] =  //
      {{0},
       {0.1, "0.1"},
       {0.12, "0.12"},
       {0.123, "0.123"},
       {0.1234, "0.1234"},
       {1.2345, "1.2345"},
       {1.0 / 3.0},
       {2.0 / 3.0},
       {10.0 / 3.0},
       {20.0 / 3.0},
       {std::numeric_limits<double>::min()},
       {std::numeric_limits<double>::max()},
       {std::numeric_limits<double>::denorm_min()}};
  for (auto c : cases) verify_value(c.value, m.dtoa, c.expected);

  rng r;
  size_t total_len = 0;
  size_t max_len = 0;
  constexpr int num_random_cases = 100'000;
  for (int i = 0; i < num_random_cases; ++i) {
    double d = 0;
    do {
      d = r();
    } while (isnan(d) || isinf(d));
    size_t len = verify_value(d, m.dtoa, nullptr);
    total_len += len;
    if (len > max_len) max_len = len;
  }

  double avg_len = double(total_len) / num_random_cases;
  fmt::print("OK. Length Avg = {:2.3f}, Max = {}\n", avg_len, max_len);
}

auto get_random_digit_data(int digit) -> const double* {
  static const std::vector<double> random_digit_data = []() {
    std::vector<double> data;
    data.reserve(num_doubles_per_digit * max_digits);
    rng r;
    for (int digit = 1; digit <= max_digits; ++digit) {
      for (size_t i = 0; i < num_doubles_per_digit; ++i) {
        double d = 0;
        do {
          d = r();
        } while (isnan(d) || isinf(d));

        // Limit the number of digits.
        char buffer[64];
        snprintf(buffer, sizeof(buffer), "%.*g", digit, d);
        data.push_back(from_chars(buffer).value);
      }
    }
    return data;
  }();
  return random_digit_data.data() + (digit - 1) * num_doubles_per_digit;
}

using duration = std::chrono::steady_clock::duration;

struct digit_result {
  double duration_ns = std::numeric_limits<double>::min();
};

struct benchmark_result {
  double min_ns = std::numeric_limits<double>::max();
  double max_ns = std::numeric_limits<double>::min();
  digit_result per_digit[max_digits + 1];
};

auto bench_random_digit(dtoa_fun dtoa, const std::string& name, int num_trials)
    -> benchmark_result {
  int num_iterations_per_digit = num_trials;

  char buffer[256] = {};
  benchmark_result result;
  for (int digit = 1; digit <= max_digits; ++digit) {
    const double* data = get_random_digit_data(digit);

    duration run_duration = duration::max();
    for (int trial = 0; trial < num_trials; ++trial) {
      auto start = std::chrono::steady_clock::now();
      for (int iter = 0; iter < num_iterations_per_digit; ++iter) {
        for (int i = 0; i < num_doubles_per_digit; ++i) dtoa(data[i], buffer);
      }
      auto finish = std::chrono::steady_clock::now();

      // Pick the smallest of trial runs.
      auto d = finish - start;
      if (d < run_duration) run_duration = d;
    }

    double ns =
        std::chrono::duration_cast<std::chrono::nanoseconds>(run_duration)
            .count();
    ns /= num_iterations_per_digit * num_doubles_per_digit;

    result.per_digit[digit].duration_ns = ns;
    if (ns < result.min_ns) result.min_ns = ns;
    if (ns > result.max_ns) result.max_ns = ns;
  }
  return result;
}

auto main(int argc, char** argv) -> int {
  std::string commit_hash;
  if (argc > 1) commit_hash = std::string("_") + argv[1];
  int num_trials = 10;
  if (argc > 2) num_trials = std::stoi(argv[2]);

  std::sort(
      methods.begin(), methods.end(),
      [](const method& lhs, const method& rhs) { return lhs.name < rhs.name; });

  for (const method& m : methods) verify(m);

  std::string filename = fmt::format("results/{}_{}_{}{}.csv", MACHINE,
                                     os_name(), compiler_name(), commit_hash);
  FILE* f = fopen(filename.c_str(), "w");
  fmt::print(f, "Type,Function,Digit,Time(ns)\n");
  for (const method& m : methods) {
    fmt::print("Benchmarking randomdigit {:20} ... ", m.name);
    fflush(stdout);
    benchmark_result result = bench_random_digit(m.dtoa, m.name, num_trials);
    for (int digit = 1; digit <= max_digits; ++digit) {
      fmt::print(f, "randomdigit,{},{},{:f}\n", m.name, digit,
                 result.per_digit[digit].duration_ns);
    }
    fmt::print("[{:8.3f}ns, {:8.3f}ns]\n", result.min_ns, result.max_ns);
  }
  fclose(f);
}
