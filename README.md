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
     * Generate 1000 random `double` values (excluding `±inf` and `NaN`).
     * Reduce precision to 1–17 decimal digits in the significand.
     * Convert each value to an ASCII string.

   Each digit group is executed 100 times.  
   For each configuration, 10 trials are run and the **minimum** elapsed time
   is recorded.

## Build and Run

```bash
cmake .
make run-benchmark
```

Results are written in CSV format to:

```
result/<cpu>_<os>_<compiler>.csv
```

They are also automatically converted to HTML with the same base name.

## Results

The following results were measured on a **MacBook Pro (Apple M1 Pro)** using:

* Compiler: Apple clang 17.0.0 (clang-1700.0.13.5)
* OS: macOS

| Function          | Time (ns) | Speedup |
|-------------------|----------:|--------:|
| ostringstream     |   874.884 |   1.00× |
| sprintf           |   743.801 |   1.18× |
| double-conversion |    83.519 |  10.48× |
| to_chars          |    43.672 |  20.03× |
| ryu               |    36.865 |  23.73× |
| schubfach         |    24.879 |  35.16× |
| fmt               |    22.338 |  39.17× |
| dragonbox         |    20.641 |  42.39× |
| yy                |    14.335 |  61.03× |
| xjb64             |    10.724 |  81.58× |
| zmij              |    10.087 |  86.73× |
| null              |     0.930 | 940.73× |

**Conversion time (smaller is better):**

<img width="804" height="350" alt="image" src="https://github.com/user-attachments/assets/389d7e77-1ed2-4988-9521-1f6dbffbc77f" />

`ostringstream` and `sprintf` are excluded due to their significantly slower
performance.

<img width="835" height="672" alt="image" src="https://github.com/user-attachments/assets/3d1224d8-1efa-47ee-b5b4-4ed3179bc799" />

### Notes

* `null` performs no conversion and measures loop + call overhead.
* `sprintf` and `ostringstream` do **not** generate shortest representations
  (e.g. `0.1` → `0.10000000000000001`).
* `ryu`, `dragonbox`, and `schubfach` always emit exponential notation
  (e.g. `0.1` → `1E-1`).

Additional benchmark results are available in the
[`result`](https://github.com/fmtlib/dtoa-benchmark/tree/master/result)
directory and viewable online using
[Google Charts](https://developers.google.com/chart/):

* [apple-m1-pro_mac64_clang17.0](https://fmtlib.github.io/dtoa-benchmark/result/apple-m1-pro_mac64_clang17.0.html)

## Methods

| Function | Description |
|----------|------------|
| [double-conversion](https://code.google.com/p/double-conversion/) | Implementation extracted from V8 using `EcmaScriptConverter().ToShortest()` (Grisu3 with bignum fallback). |
| [dragonbox](https://github.com/jk-jeon/dragonbox) | `jkj::dragonbox::to_chars` with full tables. |
| [fmt](https://github.com/fmtlib/fmt) | `fmt::format_to` with compile-time format strings (Dragonbox backend). |
| null | No-op implementation. |
| ostringstream | `std::ostringstream` with `setprecision(17)`. |
| [ryu](https://github.com/ulfjack/ryu) | `d2s_buffered`. |
| [schubfach](https://github.com/vitaut/schubfach) | C++ Schubfach implementation. |
| sprintf | C `sprintf("%.17g")`. |
| [zmij](https://github.com/vitaut/zmij) | `zmij::to_string`. |
| [asteria](https://github.com/lhmouse/asteria) | `rocket::ascii_numput::put_DD`. |

### Notes

`std::to_string` is excluded because it does **not** guarantee round-trip
correctness (until C++26).

## FAQ

### 1. How do I add a new implementation?

Clone an existing implementation file, modify it, and register it in CMake.
Use:

```cpp
REGISTER_TEST(name)
```

Pull requests are welcome.

### 2. Why are fast `dtoa` functions important?

Floating-point formatting is ubiquitous in text output.  
Standard facilities such as `sprintf` and `std::stringstream` are often slow.
This benchmark originated from performance work in
[RapidJSON](https://github.com/miloyip/rapidjson/).

## See Also

* [Faster double-to-string conversion](https://vitaut.net/posts/2025/faster-dtoa/)
