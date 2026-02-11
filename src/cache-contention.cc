// L1 cache contention test for dtoa implementations.
//
// Simulates a hot-path workload (order book, market data) that competes
// for L1 data cache with the dtoa tables. Measures how dtoa throughput
// degrades as the competing working set grows.
//
// Pin to an isolated core for clean results:
//   taskset -c 18 ./cache-contention
//
// On a 32KB L1d, dragonbox (424B tables) should hold up much longer
// than uscale (11.5KB tables) or ryu (10.9KB tables) as pressure grows.

#include "benchmark.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <string>
#include <vector>

struct method {
  std::string name;
  dtoa_fun dtoa;
};

static std::vector<method> methods;

register_method::register_method(const char* name, dtoa_fun dtoa) {
  methods.push_back(method{name, dtoa});
}

// Detect L1 data cache size at runtime.
static int get_l1d_size_kb() {
#ifdef _SC_LEVEL1_DCACHE_SIZE
  long size = sysconf(_SC_LEVEL1_DCACHE_SIZE);
  if (size > 0) return static_cast<int>(size / 1024);
#endif
  return 32;  // Fallback: 32KB is the most common L1d size.
}

// Max competitor size: 2x L1d (past L1d to observe the cliff).
static constexpr int MAX_COMPETITOR_KB = 128;
static constexpr int MAX_COMPETITOR_LINES = MAX_COMPETITOR_KB * 1024 / 64;

// Competitor working set, cache-line aligned.
alignas(64) static volatile uint64_t
    competitor[MAX_COMPETITOR_LINES * 8];  // 8 uint64 per line

// Touch N cache lines of competitor data. Simulates order book access.
static void __attribute__((noinline))
touch_competitor(int num_lines) {
  uint64_t sum = 0;
  for (int i = 0; i < num_lines * 8; i += 8) {
    sum += competitor[i];
    competitor[i] = sum;  // Write too, so lines are dirty (realistic).
  }
}

// Test data: uniform distribution across 1-17 significant digits.
// 4 values per digit count = 68 values. This avoids the bias toward
// 17-digit outputs that raw random bit patterns produce.
static constexpr int MAX_DIGITS = 17;
static constexpr int VALUES_PER_DIGIT = 4;
static constexpr int NUM_TEST_VALUES = MAX_DIGITS * VALUES_PER_DIGIT;
static double test_values[NUM_TEST_VALUES];

static void init_test_values() {
  unsigned seed = 42;
  int idx = 0;
  for (int digit = 1; digit <= MAX_DIGITS; digit++) {
    for (int j = 0; j < VALUES_PER_DIGIT; j++) {
      double d;
      do {
        uint64_t bits = 0;
        seed = 214013 * seed + 2531011;
        bits = uint64_t(seed) << 32;
        seed = 214013 * seed + 2531011;
        bits |= seed;
        memcpy(&d, &bits, sizeof(d));
      } while (isnan(d) || isinf(d));
      // Reduce to the desired number of significant digits.
      char buf[32];
      snprintf(buf, sizeof(buf), "%.*g", digit, d);
      test_values[idx++] = strtod(buf, nullptr);
    }
  }
}

// Measure dtoa throughput while competing for L1 with a working set of
// `competitor_lines` cache lines. Returns nanoseconds per dtoa call.
static double __attribute__((noinline))
measure_contended(dtoa_fun dtoa, int competitor_lines, int rounds) {
  char buffer[256];
  constexpr int CALLS_PER_ROUND = 16;  // Small batch between competitor touches.

  // Warm up: bring competitor and dtoa tables into cache.
  for (int w = 0; w < 3; w++) {
    touch_competitor(competitor_lines);
    for (int i = 0; i < CALLS_PER_ROUND; i++)
      dtoa(test_values[i], buffer);
  }

  auto start = std::chrono::steady_clock::now();
  for (int r = 0; r < rounds; r++) {
    // Simulate: process market data (touch competitor), then format numbers.
    touch_competitor(competitor_lines);
    for (int i = 0; i < CALLS_PER_ROUND; i++) {
      dtoa(test_values[i % NUM_TEST_VALUES], buffer);
    }
  }
  auto end = std::chrono::steady_clock::now();

  double total_ns =
      std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
  return total_ns / (rounds * CALLS_PER_ROUND);
}

int main(int argc, char** argv) {
  const char* filter = argc > 1 ? argv[1] : nullptr;
  int rounds = argc > 2 ? atoi(argv[2]) : 100000;

  init_test_values();

  // Initialize competitor data.
  for (int i = 0; i < MAX_COMPETITOR_LINES * 8; i++) {
    competitor[i] = i * 0x9e3779b97f4a7c15ULL;
  }

  std::sort(methods.begin(), methods.end(),
            [](const method& a, const method& b) { return a.name < b.name; });

  // Compute column width from longest method name.
  int name_width = 6;  // minimum: "------"
  for (const auto& m : methods) {
    int len = static_cast<int>(m.name.size());
    if (len > name_width) name_width = len;
  }
  name_width += 2;  // padding

  // Pressure levels: 4KB steps up to just past L1d size.
  int l1d_kb = get_l1d_size_kb();
  std::vector<int> pressures_kb = {0};
  for (int kb = 4; kb <= l1d_kb + 4; kb += 4)
    pressures_kb.push_back(kb);
  int num_pressures = static_cast<int>(pressures_kb.size());

  // Header.
  printf("L1 cache contention test (%dKB L1d, %d dtoa calls between competitor touches)\n",
         l1d_kb, 16);
  printf("Competitor = simulated hot-path data (order book) competing for L1\n");
  printf("Test data = uniform mix of 1-%d significant digits (%d values)\n\n",
         MAX_DIGITS, NUM_TEST_VALUES);

  printf("%-*s", name_width, "Method");
  for (int i = 0; i < num_pressures; i++) {
    char hdr[16];
    snprintf(hdr, sizeof(hdr), "%dKB", pressures_kb[i]);
    printf(" %7s", hdr);
  }
  printf("  %7s\n", "slowdown");

  printf("%-*s", name_width, "------");
  for (int i = 0; i < num_pressures; i++) {
    printf(" %7s", "-------");
  }
  printf("  %7s\n", "-------");

  for (const auto& m : methods) {
    if (m.name == "null" || m.name == "ostringstream" || m.name == "sprintf")
      continue;
    if (filter && m.name != filter) continue;

    printf("%-*s", name_width, m.name.c_str());
    fflush(stdout);

    double baseline = 0;
    double worst = 0;

    for (int i = 0; i < num_pressures; i++) {
      int lines = pressures_kb[i] * 1024 / 64;
      double ns = measure_contended(m.dtoa, lines, rounds);

      // Take best of 3 runs for stability.
      for (int retry = 0; retry < 2; retry++) {
        double ns2 = measure_contended(m.dtoa, lines, rounds);
        if (ns2 < ns) ns = ns2;
      }

      if (i == 0) baseline = ns;
      if (ns > worst) worst = ns;

      printf(" %6.1fns", ns);
      fflush(stdout);
    }

    double slowdown = (worst / baseline - 1.0) * 100.0;
    printf("  %5.0f%%\n", slowdown);
  }

  printf("\nSlowdown = worst case vs no-contention baseline\n");
  printf("Lower slowdown = more cache-friendly implementation\n");

  return 0;
}
