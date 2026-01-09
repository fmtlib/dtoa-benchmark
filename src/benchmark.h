// A rewrite of Milo Yip's dtoa-benchmark.
// Copyright (c) 2025 - present, Victor Zverovich
// Distributed under the MIT license.

#ifndef BENCHMARK_H_
#define BENCHMARK_H_

#include <string>
#include <vector>

using dtoa_fun = void (*)(double, char*);

struct method {
  std::string name;
  dtoa_fun dtoa;
};

extern std::vector<method> methods;

struct register_method {
  register_method(const char* name, dtoa_fun dtoa) {
    methods.push_back(method{name, dtoa});
  }
};

#endif  // BENCHMARK_H_
