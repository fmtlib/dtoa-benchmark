# dtoa Benchmark

This is a fork of Milo Yip's [dtoa-benchmark](https://github.com/miloyip/dtoa-benchmark) with the following changes:

* CMake support
* Fixed reporting of results
* Added [{fmt}](https://github.com/fmtlib/fmt)
* Added [Dragonbox](https://github.com/jk-jeon/dragonbox)
* Added [Ryu](https://github.com/ulfjack/ryu)
* Added [Schubfach](https://github.com/vitaut/schubfach)
* Added [Żmij](https://github.com/vitaut/zmij)
* Added [Asteria](https://github.com/lhmouse/asteria)
* Removed the use of deprecated `strstream`
* Disabled Grisu2 implementations since they don't guarantee correctness

Copyright(c) 2014 Milo Yip (miloyip@gmail.com)

## Introduction

This benchmark evaluates the performance of conversion from double precision
IEEE-754 floating point (`double`) to ASCII string. The function prototype is:

```cpp
void dtoa(double value, char* buffer);
```

The character string result **must** be convertible to the original value
**exactly** via some correct implementation of `strtod`, i.e. roundtrip
convertible.

Note that `dtoa` is *not* a standard function in C and C++.

## Procedure

Firstly the program verifies the correctness of implementations.

Then, one case for benchmark is carried out:

1. **RandomDigit**: Generates 1000 random `double` values, filtered out
`+/-inf` and `nan`. Then convert them to limited precision (1 to 17 decimal
digits in significand). Finally convert these numbers into ASCII.

Each digit group is run for 100 times. The minimum time duration is measured
for 10 trials.

## Build and Run

1. Configure: `cmake .`
2. Build and run benchmark: `make run-benchmark`

The results in CSV format will be written to the file
`result/<cpu>_<os>_<compiler>.csv` and automatically converted to HTML with
the same base name and the `.html` extension.

## Results

The following are results measured on a MacBook Pro (Apple M1 Pro), where
`dtoa` is compiled by Apple clang 17.0.0 (clang-1700.0.13.5) and run on macOS.

| Function            | Time (ns) | Speedup |
|---------------------|----------:|--------:|
| ostringstream       | 891.171   | 1.00x   |
| sprintf             | 734.196   | 1.21x   |
| double-conversion   | 84.529    | 10.54x  |
| to_chars            | 42.817    | 20.81x  |
| ryu                 | 36.900    | 24.15x  |
| schubfach           | 24.718    | 36.05x  |
| fmt                 | 22.315    | 39.94x  |
| dragonbox           | 20.646    | 43.16x  |
| yy                  | 14.052    | 63.42x  |
| xjb64               | 10.552    | 84.45x  |
| zmij                | 10.205    | 87.32x  |
| null                | 0.929     | 959.46x |

<img width="782" height="353" alt="image" src="https://github.com/user-attachments/assets/ba5a20c5-6fea-4cc3-91b6-cb2742723b60" />

`ostringstream` and `sprintf` are excluded from the above graph because they are too slow.

<img width="826" height="670" alt="image" src="https://github.com/user-attachments/assets/1982c4f4-4cbf-4b4d-91b0-90e8da52340c" />

Notes:
* The `null` implementation does nothing. It measures the overheads of looping
  and function call.
* `sprintf` and `ostringstream` don't generate the shortest representation,
  e.g. `0.1` is formatted as `0.10000000000000001`.
* `ryu`, `dragonbox` and `schubfach` only produce the output in the exponential
  format, e.g. `0.1` is formatted as `1E-1` or similar.

Some results of various configurations are located at [`result`](
https://github.com/fmtlib/dtoa-benchmark/tree/master/result). They can be
accessed online, with interactivity provided by [Google Charts](
https://developers.google.com/chart/):

* [apple-m1-pro_mac64_clang17.0](
  https://fmtlib.github.io/dtoa-benchmark/result/apple-m1-pro_mac64_clang17.0.html)

## Implementations

Function      | Description
--------------|-----------
[double-conversion](https://code.google.com/p/double-conversion/)    |  C++ implementation extracted from Google's V8 JavaScript Engine with `EcmaScriptConverter().ToShortest()` (based on Grisu3, fall back to slower bignum algorithm when Grisu3 failed to produce shortest implementation).
[dragonbox](https://github.com/jk-jeon/dragonbox) | `jkj::dragonbox::to_chars` with full tables.
[fmt](https://github.com/fmtlib/fmt) | `fmt::format_to` with format string compilation (implements Dragonbox).
null          | Do nothing.
ostringstream | [`std::ostringstream`](https://en.cppreference.com/w/cpp/io/basic_ostringstream.html) from the C++ standard library with `setprecision(17)`.
[ryu](https://github.com/ulfjack/ryu) | Ryu `d2s_buffered`
[schubfach](https://github.com/vitaut/schubfach) | Schubfach implementation in C++
sprintf       | [`sprintf`](https://en.cppreference.com/w/c/io/fprintf.html) from the C standard library with `"%.17g"` format.
[zmij](https://github.com/vitaut/zmij) | `zmij::to_string`
[asteria](https://github.com/lhmouse/asteria) | `rocket::ascii_numput::put_DD` (decimal double)

Notes:

`std::to_string` is not tested as it does not fulfill the roundtrip
requirement (until C++26).

## FAQ

1. How to add an implementation?
   
   You may clone an existing implementation file. And then modify it and add to
   the CMake config. Note that it will automatically register to the benchmark
   by macro `REGISTER_TEST(name)`.

   Making a pull request of new implementations is welcome.

2. Why not converting `double` to `std::string`?

   It may introduce heap allocation, which is a big overhead. User can easily
   wrap these low-level functions to return `std::string`, if needed.

3. Why fast `dtoa` functions is needed?

   They are a very common operations in writing data in text format.
   The standard way of `sprintf`, `std::stringstream`, often provides poor
   performance. The author of this benchmark would optimize the `sprintf`
   implementation in [RapidJSON](https://github.com/miloyip/rapidjson/),
   thus he creates this project.

## Related Benchmarks and Discussions

* [Printing Floating-Point Numbers](http://www.ryanjuckett.com/programming/printing-floating-point-numbers/)
