// A rewrite of Milo Yip's dtoa-benchmark.
// Copyright (c) 2025 - present, Victor Zverovich
// Distributed under the MIT license.

#ifndef BENCHMARK_H_
#define BENCHMARK_H_

// Returns a pointer to one past the last character written. The result is not
// required to be null-terminated.
using dtoa_fun = auto (*)(double, char*) -> char*;

struct register_method {
  register_method(const char* name, dtoa_fun dtoa);
};

#endif  // BENCHMARK_H_
