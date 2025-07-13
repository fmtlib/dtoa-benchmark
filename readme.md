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
2. Build: `make`
3. Run benchmark: `./dtoa-benchmark`
4. The results in CSV format will be written to the file `result/<cpu>_<os>_<compiler>.csv`.
5. Run GNU `make` in `dtoa-benchmark/result` to generate results in HTML.

## Results

The following are results measured on a MacBook Pro (2.8 GHz Quad-Core Intel Core i7), where `dtoa()` is compiled by clang 12.0.0 (clang-1200.0.32.2) and run on macOS. The speedup is based on `sprintf()`.

Function      | Time (ns)  | Speedup 
--------------|-----------:|-------:
ostringstream |	1,187.735|	0.75x
sprint        |	887.735  |	1.00x
fpconv        |	119.024  |	7.46x
grisu2        |	101.082  |	8.78x
doubleconv    |	84.359   |	10.52x
milo          |	64.100   |	13.85x
ryu           |	43.541   |	20.39x
fmt           |	40.712   |	21.81x
null          |	1.200    |	739.78x

![unknown_mac64_clang12.0_randomdigit_time](https://user-images.githubusercontent.com/576385/97088504-13931600-15e6-11eb-9746-1639c0ce7fbe.png)

![unknown_mac64_clang12.0_randomdigit_timedigit](https://user-images.githubusercontent.com/576385/97088514-358c9880-15e6-11eb-8b35-0011de065101.png)

Note that the `null` implementation does nothing. It measures the overheads of looping and function call.

Some results of various configurations are located at `dtoa-benchmark/result`. They can be accessed online, with interactivity provided by [Google Charts](https://developers.google.com/chart/):

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
milo          | [miloyip](https://github.com/miloyip)'s Grisu2 C++ header-only implementation.
[fmt](https://github.com/fmtlib/fmt) | `fmt::format_to` with format string compilation.
null          | Do nothing.

Notes:

1. `std::to_string()` is not tested as it does not fulfill the roundtrip requirement (until C++26).

2. Grisu2 is chosen because it can generate better human-readable number and >99.9% of results are in shortest. Grisu3 needs another `dtoa()` implementation for not meeting the shortest requirement.

## FAQ

1. How to add an implementation?
   
   You may clone an existing implementation file. And then modify it and add to the CMake config. Note that it will automatically register to the benchmark by macro `REGISTER_TEST(name)`.

   Making pull request of new implementations is welcome.

2. Why not converting `double` to `std::string`?

   It may introduce heap allocation, which is a big overhead. User can easily wrap these low-level functions to return `std::string`, if needed.

3. Why fast `dtoa()` functions is needed?

   They are a very common operations in writing data in text format. The standard way of `sprintf()`, `std::stringstream`, often provides poor performance. The author of this benchmark would optimize the `sprintf` implementation in [RapidJSON](https://github.com/miloyip/rapidjson/), thus he creates this project.

## References

[1] Loitsch, Florian. ["Printing floating-point numbers quickly and accurately with integers."](http://florian.loitsch.com/publications/dtoa-pldi2010.pdf) ACM Sigplan Notices 45.6 (2010): 233-243.

## Related Benchmarks and Discussions

* [Printing Floating-Point Numbers](http://www.ryanjuckett.com/programming/printing-floating-point-numbers/)
