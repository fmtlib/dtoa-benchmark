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

* Compiler: Apple clang 17.0.0 (clang-1700.0.13.5)
* OS: macOS

| Function           | Time (ns) | Speedup |
|--------------------|----------:|--------:|
| ostringstream      | 870.478   | 1.00x   |
| sprintf            | 734.033   | 1.19x   |
| double-conversion  | 82.903    | 10.50x  |
| to_chars           | 42.537    | 20.46x  |
| ryu                | 36.805    | 23.65x  |
| schubfach          | 24.653    | 35.31x  |
| fmt                | 22.201    | 39.21x  |
| dragonbox          | 20.544    | 42.37x  |
| yy                 | 13.963    | 62.34x  |
| xjb64              | 10.500    | 82.90x  |
| zmij               | 8.895     | 97.87x  |
| null               | 0.929     | 936.55x |

**Conversion time (smaller is better):**

<img width="816" height="358" alt="image" src="https://github.com/user-attachments/assets/c6eea19d-f824-4069-bc26-d701a419916e" />

`ostringstream` and `sprintf` are excluded due to their significantly slower
performance.

<img width="857" height="687" alt="image" src="https://github.com/user-attachments/assets/13cb86d3-4d76-4903-a13e-d4845a4388b4" />

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

| Function | Description |
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
