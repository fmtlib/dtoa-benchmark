# dtoa benchmark

This project is a complete rewrite of Milo Yip’s
[dtoa-benchmark](https://github.com/miloyip/dtoa-benchmark), featuring an
updated set of algorithms that reflect the current state of the art and a
simplified workflow.

## Introduction

This benchmark evaluates the performance of converting double-precision
IEEE-754 floating-point values (`double`) to ASCII strings. The function
signature is:

```cpp
void dtoa(double value, char* buffer);
```

The resulting string **must** be round-trip convertible: it should parse back
to the original value **exactly** via a correct implementation of `strtod`.

Note: `dtoa` is *not* a standard C or C++ function.

## Procedure

The benchmark consists of two phases:

1. **Correctness verification**  
   All implementations are first validated to ensure round-trip correctness.

2. **Performance measurement**

   The benchmark case is:

   * **RandomDigit**  
     * Generate 100,000 random `double` values (excluding `±inf` and `NaN`).
     * Reduce precision to 1–17 decimal digits in the significand.
     * Convert each value to an ASCII string.

   Each digit group is executed 10 times.  
   For each configuration, 10 trials are run and the **minimum** elapsed time
   is recorded.

## Build and Run

```bash
cmake .
make run-benchmark
```

Results are written in CSV format to:

```
results/<cpu>_<os>_<compiler>_<commit>.csv
```

They are also automatically converted to HTML with the same base name.

## Results

The following results were measured on a **MacBook Pro (Apple M1 Pro)** using:

* Compiler: Apple clang version 21.0.0 (clang-2100.0.123.102)
* OS: macOS

| Method            | Time (ns) |  Speedup |
|-------------------|----------:|---------:|
| zmij              |      6.51 | 112.188x |
| xjb64             |      6.92 | 105.621x |
| yy                |     13.38 |  54.605x |
| dragonbox         |     20.92 |  34.909x |
| fmt               |     22.13 |  33.003x |
| schubfach         |     25.06 |  29.140x |
| uscale            |     28.50 |  25.625x |
| ryu               |     36.92 |  19.782x |
| to_chars          |     41.77 |  17.484x |
| double-conversion |     84.70 |   8.624x |
| sprintf           |    730.38 |   1.000x |
| ostringstream     |    871.91 |   0.838x |

**Time per double (smaller is better)**:
<img width="865" height="405" alt="image" src="https://github.com/user-attachments/assets/6fb860f1-3cd6-4285-89f1-da7f573f3a8b" />

`ostringstream` and `sprintf` omitted; they are an order of magnitude slower than the rest.

**Time vs digit count (log scale)**:
<img width="868" height="661" alt="image" src="https://github.com/user-attachments/assets/c21d9c08-66d7-48f6-ac1e-ce12dce63fba" />

### Notes

* `null` performs no conversion and measures loop + call overhead.
* `sprintf` and `ostringstream` do **not** generate shortest representations
  (e.g. `0.1` → `0.10000000000000001`).
* `ryu`, `dragonbox`, and `schubfach` always emit exponential notation
  (e.g. `0.1` → `1E-1`).

Additional benchmark results are available in the
[`results`](https://github.com/fmtlib/dtoa-benchmark/tree/main/results)
directory and viewable online using
[Google Charts](https://developers.google.com/chart/):

* [apple-m1-pro_macos_clang17.0_e0a03f7](
  https://fmtlib.github.io/dtoa-benchmark/results/apple-m1-pro_macos_clang17.0_f0f753f.html)

## Methods

| Method | Description |
|----------|-------------|
| [asteria](https://github.com/lhmouse/asteria) | `rocket::ascii_numput::put_DD` |
| [double-conversion](https://github.com/google/double-conversion) | `EcmaScriptConverter::ToShortest` which implements Grisu3 with bignum fallback |
| [dragonbox](https://github.com/jk-jeon/dragonbox) | `jkj::dragonbox::to_chars` with full tables |
| [fmt](https://github.com/fmtlib/fmt) | `fmt::format_to` with compile-time format strings (uses Dragonbox). |
| null | no-op implementation |
| [ostringstream](https://en.cppreference.com/w/cpp/io/basic_ostringstream.html) | `std::ostringstream` with `setprecision(17)` |
| [ryu](https://github.com/ulfjack/ryu) | `d2s_buffered` |
| [schubfach](https://github.com/vitaut/schubfach) | C++ Schubfach implementation |
| [sprintf](https://en.cppreference.com/w/c/io/fprintf.html) | C `sprintf("%.17g", value)` |
| [to_chars](https://en.cppreference.com/w/cpp/utility/to_chars.html) | `std::to_chars` |
| [zmij](https://github.com/vitaut/zmij) | `zmij::write`. |

### Notes

`std::to_string` is excluded because it does **not** guarantee round-trip
correctness (until C++26).

## Why is fast `dtoa` important?

Floating-point formatting is ubiquitous in text output. 
Standard facilities such as `sprintf` and `std::stringstream` are often slow.
This benchmark originated from performance work in
[RapidJSON](https://github.com/miloyip/rapidjson/).

## See Also

* [Faster double-to-string conversion](https://vitaut.net/posts/2025/faster-dtoa/)
* [The smallest state-of-the-art double-to-string implementation](
  https://vitaut.net/posts/2025/smallest-dtoa/)
