// A rewrite of Milo Yip's dtoa-benchmark.
// Copyright (c) 2025 - present, Victor Zverovich
// Distributed under the MIT license.

#include "benchmark.h"

#include <benchmark/benchmark.h>
#include <math.h>    // isnan, isinf
#include <stdint.h>  // uint64_t
#include <stdio.h>   // snprintf
#include <string.h>  // memcpy, strcmp, strlen

#include <algorithm>  // std::sort, std::shuffle
#include <cmath>      // std::abs
#include <exception>
#include <fstream>
#include <limits>
#include <optional>
#include <random>  // std::mt19937
#include <string>
#include <string_view>
#include <vector>

#include "double-conversion/double-conversion.h"
#include "fmt/format.h"

namespace {

constexpr int max_digits = std::numeric_limits<double>::max_digits10;
constexpr int num_doubles_per_digit = 100'000;

struct method {
  std::string name;
  dtoa_fun dtoa;
};

std::vector<method> methods;

#ifndef MACHINE
#  define MACHINE "unknown"
#endif

auto os_name() -> const char* {
#if defined(__linux__)
  return "linux";
#elif defined(__APPLE__)
  return "macos";
#elif defined(_WIN32)
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

// Random number generator from the original dtoa-benchmark.
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
    *dtoa(value, buffer) = '\0';

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

auto get_mixed_pool() -> const std::vector<double>& {
  static const std::vector<double> pool = [] {
    std::vector<double> v;
    v.reserve(num_doubles_per_digit * max_digits);
    for (int d = 1; d <= max_digits; ++d) {
      const double* p = get_random_digit_data(d);
      v.insert(v.end(), p, p + num_doubles_per_digit);
    }
    std::shuffle(v.begin(), v.end(), std::mt19937(0));
    return v;
  }();
  return pool;
}

void run_random_digit(benchmark::State& state, dtoa_fun dtoa, int digit) {
  const double* data = get_random_digit_data(digit);
  char buffer[256];
  for (auto _ : state) {
    for (int i = 0; i < num_doubles_per_digit; ++i) {
      char* end = dtoa(data[i], buffer);
      benchmark::DoNotOptimize(end);
      benchmark::ClobberMemory();
    }
  }
  state.counters["Throughput"] = benchmark::Counter(
      double(num_doubles_per_digit), benchmark::Counter::kIsIterationInvariantRate);
  state.counters["Time/double"] = benchmark::Counter(
      double(num_doubles_per_digit), benchmark::Counter::kIsIterationInvariantRate |
                                 benchmark::Counter::kInvert);
}

void run_mixed(benchmark::State& state, dtoa_fun dtoa) {
  const auto& pool = get_mixed_pool();
  char buffer[256];
  for (auto _ : state) {
    for (double x : pool) {
      char* end = dtoa(x, buffer);
      benchmark::DoNotOptimize(end);
      benchmark::ClobberMemory();
    }
  }
  state.counters["Throughput"] = benchmark::Counter(
      double(pool.size()), benchmark::Counter::kIsIterationInvariantRate);
  state.counters["Time/double"] = benchmark::Counter(
      double(pool.size()), benchmark::Counter::kIsIterationInvariantRate |
                               benchmark::Counter::kInvert);
}

void register_all(bool per_digit) {
  for (const auto& m : methods) {
    if (per_digit) {
      for (int d = 1; d <= max_digits; ++d) {
        std::string name = m.name + "/d" + std::to_string(d);
        benchmark::RegisterBenchmark(name.c_str(), run_random_digit, m.dtoa, d);
      }
    }
    benchmark::RegisterBenchmark(m.name.c_str(), run_mixed, m.dtoa);
  }
}

// Formats a counter value with 2 fractional digits, applying SI auto-scaling
// so the mantissa always sits in [1, 1000) (or in [0.01, 1) for tiny values).
auto format_counter(double n) -> std::string {
  static const char* const big[] = {"k", "M", "G", "T", "P", "E", "Z", "Y"};
  static const char* const small[] = {"m", "u", "n", "p", "f", "a", "z", "y"};
  double v = n;
  const char* prefix = "";
  double a = std::abs(v);
  if (a > 999) {
    for (int i = 0; i < 8 && std::abs(v) > 999; ++i) {
      v /= 1000;
      prefix = big[i];
    }
  } else if (a > 0 && a < 0.01) {
    for (int i = 0; i < 8 && std::abs(v) < 1.0; ++i) {
      v *= 1000;
      prefix = small[i];
    }
  }
  return fmt::format("{:.2f}{}", v, prefix);
}

// Console reporter that formats counter cells with 2 fractional digits while
// reusing google benchmark's tabular column layout for everything else.
class pretty_reporter : public benchmark::ConsoleReporter {
 public:
  pretty_reporter() : benchmark::ConsoleReporter(OO_Tabular) {}

 protected:
  void PrintRunData(const Run& report) override {
    Run copy = report;
    std::string cells;
    for (const auto& kv : copy.counters) {
      const auto& c = kv.second;
      const char* unit = "";
      if (c.flags & benchmark::Counter::kIsRate)
        unit = (c.flags & benchmark::Counter::kInvert) ? "s" : "/s";
      auto cell = format_counter(c.value) + unit;
      std::size_t w = std::max<std::size_t>(10, kv.first.length());
      if (!cells.empty()) cells += ' ';
      cells += fmt::format("{:>{}}", cell, w);
    }
    if (!copy.report_label.empty()) {
      if (!cells.empty()) cells += ' ';
      cells += copy.report_label;
    }
    copy.counters.clear();
    copy.report_label = std::move(cells);
    benchmark::ConsoleReporter::PrintRunData(copy);
  }
};

// CSV reporter that buffers benchmark rows in the legacy
// `Type,Method,Digit,Time(ns)` format consumed by generate-html.py. Per-digit
// runs are emitted with their digit count (1..max_digits); the mixed-pool run
// is emitted with digit=0 and is the per-method summary time used by
// generate-html.py for the results table and bar chart. The buffer is flushed
// to disk by main() only after benchmarks finish so an interrupted run never
// leaves an empty CSV file behind.
class csv_reporter : public benchmark::BenchmarkReporter {
 public:
  csv_reporter() : buffer_("Type,Method,Digit,Time(ns)\n") {}
  bool ReportContext(const Context&) override { return true; }
  void ReportRuns(const std::vector<Run>& runs) override {
    for (const auto& r : runs) {
      const std::string& name = r.run_name.function_name;
      auto pos = name.rfind("/d");
      std::string method;
      int digit = 0;
      size_t items_per_iter = 0;
      if (pos == std::string::npos) {
        method = name;
        items_per_iter = num_doubles_per_digit * max_digits;
      } else {
        method = name.substr(0, pos);
        try {
          digit = std::stoi(name.substr(pos + 2));
        } catch (...) {
          continue;
        }
        items_per_iter = num_doubles_per_digit;
      }
      double ns_per_double = r.GetAdjustedRealTime() / items_per_iter;
      buffer_ += fmt::format("randomdigit,{},{},{:f}\n", method, digit,
                             ns_per_double);
    }
  }
  auto buffer() const -> const std::string& { return buffer_; }

 private:
  std::string buffer_;
};

}  // namespace

register_method::register_method(const char* name, dtoa_fun dtoa) {
  methods.push_back(method{name, dtoa});
}

auto main(int argc, char** argv) -> int {
  bool per_digit = true;
  std::string commit_hash;
  std::string csv_out;
  std::string json_out;
  int out = 1;
  for (int i = 1; i < argc; ++i) {
    auto arg = std::string_view(argv[i]);
    if (arg == "--per-digit") {
      per_digit = true;
    } else if (arg == "--no-per-digit") {
      per_digit = false;
    } else if (arg.substr(0, 14) == "--commit-hash=") {
      commit_hash = std::string(arg.substr(14));
    } else if (arg.substr(0, 10) == "--csv-out=") {
      csv_out = std::string(arg.substr(10));
    } else if (arg.substr(0, 11) == "--json-out=") {
      json_out = std::string(arg.substr(11));
    } else {
      argv[out++] = argv[i];
    }
  }
  argc = out;

  std::sort(
      methods.begin(), methods.end(),
      [](const method& lhs, const method& rhs) { return lhs.name < rhs.name; });

  for (const method& m : methods) verify(m);

  // Default CSV output path matches the pre-google-benchmark layout so that
  // generate-html.py keeps working unchanged.
  if (csv_out.empty() && json_out.empty() && per_digit) {
    std::string suffix = commit_hash.empty() ? "" : "_" + commit_hash;
    csv_out = fmt::format("results/{}_{}_{}{}.csv", MACHINE, os_name(),
                          compiler_name(), suffix);
  }

  register_all(per_digit);

  // Google Benchmark requires --benchmark_out=<path> to be set whenever a
  // custom file reporter is supplied, even though the reporter writes to its
  // own stream. Synthesize the flag from --csv-out / --json-out.
  std::vector<char*> extra_argv(argv, argv + argc);
  std::string benchmark_out_arg;
  const std::string& out_path = !json_out.empty() ? json_out : csv_out;
  if (!out_path.empty()) {
    benchmark_out_arg = "--benchmark_out=" + out_path;
    extra_argv.push_back(benchmark_out_arg.data());
  }
  int extra_argc = static_cast<int>(extra_argv.size());
  benchmark::Initialize(&extra_argc, extra_argv.data());
  if (benchmark::ReportUnrecognizedArguments(extra_argc, extra_argv.data()))
    return 1;

  pretty_reporter console;
  std::ofstream json_file;
  std::optional<csv_reporter> csv_rep;
  std::optional<benchmark::JSONReporter> json_rep;
  benchmark::BenchmarkReporter* file_reporter = nullptr;
  if (!json_out.empty()) {
    json_file.open(json_out);
    if (!json_file) {
      fmt::print("error: cannot open '{}' for writing\n", json_out);
      return 1;
    }
    json_rep.emplace();
    json_rep->SetOutputStream(&json_file);
    file_reporter = &*json_rep;
  } else if (!csv_out.empty()) {
    csv_rep.emplace();
    file_reporter = &*csv_rep;
  }

  if (file_reporter)
    benchmark::RunSpecifiedBenchmarks(&console, file_reporter);
  else
    benchmark::RunSpecifiedBenchmarks(&console);
  benchmark::Shutdown();

  // Write the CSV only after benchmarks finish so an interrupted run does
  // not leave an empty file that confuses generate-html.py.
  if (csv_rep) {
    std::ofstream csv_file(csv_out);
    if (!csv_file) {
      fmt::print("error: cannot open '{}' for writing\n", csv_out);
      return 1;
    }
    csv_file << csv_rep->buffer();
  }
  return 0;
}
