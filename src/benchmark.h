// A rewrite of Milo Yip's dtoa-benchmark.
// Copyright (c) 2025 - present, Victor Zverovich
// Distributed under the MIT license.

#ifndef BENCHMARK_H_
#define BENCHMARK_H_

#include <string>
#include <vector>

struct method {
  std::string name;
  void (*dtoa)(double, char*);
};

extern std::vector<method> methods;

#define REGISTER_METHOD(name, dtoa)       \
  static int reg = []() {                  \
    methods.push_back(method{name, dtoa}); \
    return 0;                              \
  }()

#endif  // BENCHMARK_H_
