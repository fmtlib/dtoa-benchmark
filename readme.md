# dtoa Benchmark

This is a fork of Milo Yip's [dtoa-benchmark](https://github.com/miloyip/dtoa-benchmark) with the following changes:

* CMake support
* Fixed reporting of results
* [{fmt}](https://github.com/fmtlib/fmt) test
* [Dragonbox](https://github.com/jk-jeon/dragonbox) test
* Removed the use of deprecated `strstream`

Copyright(c) 2014 Milo Yip (miloyip@gmail.com)

## Introduction

This benchmark evaluates the performance of conversion from double precision IEEE-754 floating point (`double`) to ASCII string. The function prototype is:

~~~~~~~~cpp
void dtoa(double value, char* buffer);
~~~~~~~~

The character string result **must** be convertible to the original value **exactly** via some correct implementation of `strtod()`, i.e. roundtrip convertible.

Note that `dtoa()` is *not* a standard function in C and C++.

## Procedure

Firstly the program verifies the correctness of implementations.

Then, one case for benchmark is carried out:

1. **RandomDigit**: Generates 1000 random `double` values, filtered out `+/-inf` and `nan`. Then convert them to limited precision (1 to 17 decimal digits in significand). Finally convert these numbers into ASCII.

Each digit group is run for 100 times. The minimum time duration is measured for 10 trials.

## Build and Run

1. Configure: `cmake .`
2. Build and run benchmark: `make run-benchmark`

The results in CSV format will be written to the file `result/<cpu>_<os>_<compiler>.csv` and automatically converted to HTML with the same base name and the `.html` extension.

## Results

The following are results measured on a MacBook Pro (Apple M1 Pro), where `dtoa()` is compiled by Apple clang 17.0.0 (clang-1700.0.13.5) and run on macOS. The speedup is based on `sprintf()`.

| Function          | Time (ns) | Speedup   |
|-------------------|----------:|----------:|
| ostringstream     | 864.341   | 0.84x     |
| sprintf           | 726.271   | 1.00x     |
| doubleconv        | 81.812    | 8.88x     |
| fpconv            | 60.241    | 12.06x    |
| grisu2            | 56.947    | 12.75x    |
| ryu               | 35.206    | 20.63x    |
| fmt_comp          | 29.547    | 24.58x    |
| dragonbox_comp    | 23.776    | 30.55x    |
| fmt_full          | 22.071    | 32.91x    |
| dragonbox_full    | 18.888    | 38.45x    |
| null              | 0.906     | 801.73x   |

![apple-m1-pro_mac64_clang17.0_randomdigit_time](https://github.com/user-attachments/assets/032ce868-b89f-4984-b7fd-1e8d12a0c0c7)

![apple-m1-pro_mac64_clang17.0_randomdigit_timedigit](https://github.com/user-attachments/assets/05a735c1-d189-4ddd-b3c3-3a20d7396e82)

Notes:
* The `null` implementation does nothing. It measures the overheads of looping and function call.
* `sprintf` and `ostringstream` don't generate the shortest representation, e.g. `0.1` is formatted as `0.10000000000000001`.
* `ryu` and `dragonbox_*` only produce exponential format, e.g. `0.1` is formatted as `1E-1`.

Some results of various configurations are located at [`result`](https://github.com/fmtlib/dtoa-benchmark/tree/master/result). They can be accessed online, with interactivity provided by [Google Charts](https://developers.google.com/chart/):

* [apple-m1-pro_mac64_clang17.0](https://fmtlib.github.io/dtoa-benchmark/result/apple-m1-pro_mac64_clang17.0.html)

## Implementations

Function      | Description
--------------|-----------
ostringstream | `std::ostringstream` in C++ standard library with `setprecision(17)`.
sprintf       | `sprintf()` in C standard library with `"%.17g"` format.
[gay](http://www.netlib.org/fp/) | David M. Gay's `dtoa()` C implementation.
[grisu2](http://florian.loitsch.com/publications/bench.tar.gz?attredirects=0)        | Florian Loitsch's Grisu2 C implementation [1].
[doubleconv](https://code.google.com/p/double-conversion/)    |  C++ implementation extracted from Google's V8 JavaScript Engine with `EcmaScriptConverter().ToShortest()` (based on Grisu3, fall back to slower bignum algorithm when Grisu3 failed to produce shortest implementation).
[fpconv](https://github.com/night-shift/fpconv)        | [night-shift](https://github.com/night-shift)'s  Grisu2 C implementation.
[fmt_comp](https://github.com/fmtlib/fmt) | `fmt::format_to` with format string compilation and compact tables (implements Dragonbox).
[fmt_full](https://github.com/fmtlib/fmt) | `fmt::format_to` with format string compilation and full tables (implements Dragonbox).
[dragonbox_comp](https://github.com/jk-jeon/dragonbox) | `jkj::dragonbox::to_chars` with compact tables.
[dragonbox_full](https://github.com/jk-jeon/dragonbox) | `jkj::dragonbox::to_chars` with full tables.
null          | Do nothing.

Notes:

1. `std::to_string()` is not tested as it does not fulfill the roundtrip requirement (until C++26).

2. Grisu2 is chosen because it can generate better human-readable number and >99.9% of results are in shortest. Grisu3 needs another `dtoa()` implementation for not meeting the shortest requirement.

## FAQ

1. How to add an implementation?
   
   You may clone an existing implementation file. And then modify it and add to the CMake config. Note that it will automatically register to the benchmark by macro `REGISTER_TEST(name)`.

   Making a pull request of new implementations is welcome.

2. Why not converting `double` to `std::string`?

   It may introduce heap allocation, which is a big overhead. User can easily wrap these low-level functions to return `std::string`, if needed.

3. Why fast `dtoa()` functions is needed?

   They are a very common operations in writing data in text format. The standard way of `sprintf()`, `std::stringstream`, often provides poor performance. The author of this benchmark would optimize the `sprintf` implementation in [RapidJSON](https://github.com/miloyip/rapidjson/), thus he creates this project.

## References

[1] Loitsch, Florian. ["Printing floating-point numbers quickly and accurately with integers."](http://florian.loitsch.com/publications/dtoa-pldi2010.pdf) ACM Sigplan Notices 45.6 (2010): 233-243.

## Related Benchmarks and Discussions

* [Printing Floating-Point Numbers](http://www.ryanjuckett.com/programming/printing-floating-point-numbers/)
