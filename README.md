# dtoa benchmark

This project is a rewrite of Milo Yip’s
[dtoa-benchmark](https://github.com/miloyip/dtoa-benchmark) with an updated
set of algorithms reflecting the current state of the art and a simplified
workflow.

## Introduction

This benchmark measures the performance of converting double-precision
IEEE-754 floating-point values (`double`) to ASCII strings. Each
implementation exposes a function with the signature:

```cpp
char* dtoa(double value, char* buffer);
```

that writes a textual representation of `value` into `buffer` and returns a
pointer to one past the last written character. The resulting string **must**
round-trip: parsing it back through a correct `strtod` must yield exactly the
original `double`.

Note: `dtoa` is *not* a standard C or C++ function.

## Procedure

The benchmark runs in two phases:

1. **Correctness verification.** Every implementation is validated against a
   set of edge cases and 100,000 random `double` values (excluding `±inf` and
   `NaN`) to confirm round-trip correctness.

2. **Performance measurement.** For each implementation the benchmark runs:

   * 17 *per-digit* sub-benchmarks. Each converts a pool of 100,000 random
     `double` values reduced to a fixed precision of 1–17 significant decimal
     digits. These produce the **time vs. digit count** chart.
   * One *mixed* benchmark over a single shuffled pool containing all 1.7M
     values from the per-digit pools combined. Its mean time per conversion
     is reported as the headline `Time (ns)` in the results table; this is
     the metric to use for an at-a-glance comparison.

   Iteration counts and statistical stabilization are handled by
   [Google Benchmark](https://github.com/google/benchmark).

## Build and Run

```bash
cmake .
make run-benchmark
```

Results are written in [Google Benchmark's JSON format][gb-json] to:

```
results/<cpu>_<os>_<compiler>_<commit>.json
```

and automatically converted to a self-contained HTML report with the same
base name. The JSON `context` block carries CPU/cache info, library
version, and `commit_hash`/`machine`/`os`/`compiler` keys for downstream
analysis.

[gb-json]: https://github.com/google/benchmark/blob/main/docs/user_guide.md#output-formats

## Results

The following results were measured on a **MacBook Pro (Apple M1 Pro)** using:

* Compiler: Apple clang version 21.0.0 (clang-2100.0.123.102)
* OS: macOS

| Method            | Time (ns) |  Speedup |
|-------------------|----------:|---------:|
| zmij              |      6.45 | 115.440x |
| xjb64             |      6.99 | 106.465x |
| yy                |     24.63 |  30.235x |
| dragonbox         |     28.95 |  25.723x |
| fmt               |     36.84 |  20.214x |
| uscale            |     45.86 |  16.239x |
| ryu               |     46.07 |  16.164x |
| to_chars          |     51.35 |  14.503x |
| schubfach         |     53.62 |  13.889x |
| double-conversion |     87.43 |   8.518x |
| sprintf           |    744.72 |   1.000x |
| ostringstream     |    885.30 |   0.841x |

**Time per double (smaller is better)**:
<img width="861" height="401" alt="image" src="https://github.com/user-attachments/assets/3678bc4a-9405-489e-8ce1-ca702829cdaa" />

`ostringstream` and `sprintf` omitted; they are an order of magnitude slower than the rest.

**Time vs digit count (log scale)**:
<img width="857" height="619" alt="image" src="https://github.com/user-attachments/assets/de97d1d7-f035-4086-9666-e3bd4e42b271" />

### Notes

* `null` performs no conversion and measures loop + call overhead.
* `sprintf` and `ostringstream` do **not** generate shortest representations
  (e.g. `0.1` → `0.10000000000000001`).
* `ryu`, `dragonbox`, and `schubfach` always emit exponential notation
  (e.g. `0.1` → `1E-1`).

Additional benchmark results are available in the
[`results`](https://github.com/fmtlib/dtoa-benchmark/tree/main/results)
directory and viewable online:

* [apple-m1-pro_macos_clang21.0_45ff4d4](
  https://fmtlib.github.io/dtoa-benchmark/results/apple-m1-pro_macos_clang21.0_45ff4d4.html)

## Methods

| Method | Description |
|----------|-------------|
| [asteria](https://github.com/lhmouse/asteria) | `rocket::ascii_numput::put_DD` |
| [double-conversion](https://github.com/google/double-conversion) | `EcmaScriptConverter::ToShortest` which implements Grisu3 with bignum fallback |
| [dragonbox](https://github.com/jk-jeon/dragonbox) | `jkj::dragonbox::to_chars_n` with the full cache table |
| [fmt](https://github.com/fmtlib/fmt) | `fmt::format_to` with compile-time format strings (uses Dragonbox) |
| null | no-op implementation; measures benchmark loop overhead |
| [ostringstream](https://en.cppreference.com/w/cpp/io/basic_ostringstream.html) | `std::ostringstream` with `setprecision(17)` |
| [ryu](https://github.com/ulfjack/ryu) | `d2s_buffered` |
| [schubfach](https://github.com/vitaut/schubfach) | C++ Schubfach implementation |
| [sprintf](https://en.cppreference.com/w/c/io/fprintf.html) | C `sprintf("%.17g", value)` |
| [to_chars](https://en.cppreference.com/w/cpp/utility/to_chars.html) | `std::to_chars` |
| [yy](https://github.com/ibireme/yyjson) | `yy_double_to_string` from yyjson |
| [zmij](https://github.com/vitaut/zmij) | `zmij::write` |

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
