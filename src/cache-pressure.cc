// Cache pressure test for dtoa implementations.
// Measures how much L1 data cache pollution each dtoa implementation causes.
//
// Method: Pre-load a 16KB working set into L1d cache, call dtoa N times,
// then measure how long it takes to re-read the working set. Longer reload
// means more cache lines were evicted by the dtoa code+data.
//
// Usage: ./cache-pressure [method] [calls_per_round]
// Run under: perf stat -e L1-dcache-loads,L1-dcache-load-misses ...

#include "benchmark.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

// Working set: 16KB = 256 cache lines on a 64-byte line size.
// This fits comfortably in a 32KB L1d with room for stack/locals.
static constexpr int NUM_CACHE_LINES = 256;
static constexpr int INTS_PER_LINE = 8;  // 64 bytes / 8 bytes
static constexpr int WORKING_SET_INTS = NUM_CACHE_LINES * INTS_PER_LINE;

// Aligned to cache line boundary.
alignas(64) static volatile uint64_t working_set[WORKING_SET_INTS];

// Touch every cache line, return checksum.
static uint64_t __attribute__((noinline, optimize("O1")))
load_working_set() {
  uint64_t sum = 0;
  for (int i = 0; i < WORKING_SET_INTS; i += INTS_PER_LINE) {
    sum += working_set[i];
  }
  return sum;
}

// Measure reload time in nanoseconds.
static double measure_reload_ns() {
  auto start = std::chrono::steady_clock::now();
  volatile uint64_t sink = load_working_set();
  (void)sink;
  auto end = std::chrono::steady_clock::now();
  return std::chrono::duration_cast<std::chrono::nanoseconds>(end - start)
      .count();
}

// Test data: 64 random doubles (fits in one 512-byte region).
static constexpr int NUM_TEST_VALUES = 64;
static double test_values[NUM_TEST_VALUES];

static void init_test_values() {
  unsigned seed = 42;
  for (int i = 0; i < NUM_TEST_VALUES; i++) {
    uint64_t bits = 0;
    seed = 214013 * seed + 2531011;
    bits = uint64_t(seed) << 32;
    seed = 214013 * seed + 2531011;
    bits |= seed;
    double d;
    memcpy(&d, &bits, sizeof(d));
    if (isnan(d) || isinf(d)) d = 1.23456789;
    test_values[i] = d;
  }
}

// Call dtoa exactly N times, cycling through test values.
static void __attribute__((noinline))
call_dtoa_n(dtoa_fun dtoa, int n) {
  char buffer[256];
  for (int i = 0; i < n; i++) {
    dtoa(test_values[i % NUM_TEST_VALUES], buffer);
  }
}

int main(int argc, char** argv) {
  const char* filter = argc > 1 ? argv[1] : nullptr;
  int calls_per_round = argc > 2 ? atoi(argv[2]) : 0;

  init_test_values();

  for (int i = 0; i < WORKING_SET_INTS; i++) {
    working_set[i] = i * 0x9e3779b97f4a7c15ULL;
  }

  // Establish baseline: load + immediately reload.
  double baseline_ns = 1e18;
  for (int t = 0; t < 50; t++) {
    load_working_set();
    double ns = measure_reload_ns();
    if (ns < baseline_ns) baseline_ns = ns;
  }

  printf("Working set: %d KB (%d cache lines), Baseline reload: %.0f ns\n",
         (int)(NUM_CACHE_LINES * 64 / 1024), NUM_CACHE_LINES, baseline_ns);
  printf("\n");

  std::sort(methods.begin(), methods.end(),
            [](const method& a, const method& b) { return a.name < b.name; });

  // If a specific call count was given, just run that.
  // Otherwise, sweep from 1 to 64 calls to show the eviction curve.
  std::vector<int> call_counts;
  if (calls_per_round > 0) {
    call_counts = {calls_per_round};
  } else {
    call_counts = {1, 2, 4, 8, 16, 32, 64};
  }

  // Header.
  printf("%-16s", "Method");
  for (int n : call_counts) {
    char hdr[32];
    snprintf(hdr, sizeof(hdr), "%d call%s", n, n > 1 ? "s" : "");
    printf(" %10s", hdr);
  }
  printf("\n");

  printf("%-16s", "------");
  for (size_t i = 0; i < call_counts.size(); i++) {
    printf(" %10s", "----------");
  }
  printf("\n");

  for (const auto& m : methods) {
    if (m.name == "null" || m.name == "ostringstream" || m.name == "sprintf")
      continue;
    if (filter && m.name != filter) continue;

    printf("%-16s", m.name.c_str());

    for (int n : call_counts) {
      // Take median of many trials for stability.
      constexpr int NUM_TRIALS = 200;
      double trials[NUM_TRIALS];

      for (int t = 0; t < NUM_TRIALS; t++) {
        load_working_set();           // Prime L1 with working set.
        call_dtoa_n(m.dtoa, n);       // Pollute with dtoa.
        trials[t] = measure_reload_ns();
      }

      std::sort(trials, trials + NUM_TRIALS);
      double median_ns = trials[NUM_TRIALS / 2];
      double penalty_ns = median_ns - baseline_ns;

      printf(" %9.0fns", penalty_ns);
    }
    printf("\n");
  }

  printf("\nPenalty = median reload time after N dtoa calls minus baseline (%.0f ns)\n",
         baseline_ns);
  printf("Higher = more L1 cache eviction = worse for co-resident hot paths\n");

  return 0;
}
