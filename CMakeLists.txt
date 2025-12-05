cmake_minimum_required(VERSION 3.5.0)

# Set the default build type to Release because we want to benchmark
# optimized code.
if (NOT CMAKE_BUILD_TYPE)
  set(none "None(CMAKE_CXX_FLAGS or CMAKE_C_FLAGS used)")
  set(other "Debug Release RelWithDebInfo MinSizeRel")
  set(CMAKE_BUILD_TYPE Release CACHE STRING
      "Choose the type of build, options are: ${none} ${other}.")
endif ()

project(DTOA_BENCHMARK C CXX)

add_executable(
  dtoa-benchmark
  src/main.cpp

  # Tests:
  src/ryutest.cpp
  src/doubleconvtest.cpp
  src/fmttest.cpp
  #src/dtoa_puff.cpp
  src/dragonbox_test.cpp
  src/null.cpp
  src/ostringstream.cpp
  src/sprintf.cpp
  #src/xjb64_test.cpp
  src/schubfach_test.cpp

  # Libraries:
  src/double-conversion/bignum-dtoa.cc
  src/double-conversion/bignum.cc
  src/double-conversion/cached-powers.cc
  src/double-conversion/diy-fp.cc
  src/double-conversion/double-conversion.cc
  src/double-conversion/fast-dtoa.cc
  src/double-conversion/fixed-dtoa.cc
  src/double-conversion/strtod.cc
  src/dragonbox/dragonbox_to_chars.cpp # 2 Aug 2025: 6c7c925
  src/fmt/src/format.cc # 2 Aug 2025: 35dcc582
  src/schubfach/schubfach.cc

  # Grisu2 variants are disabled since they don't guarantee correctness.
  #src/fpconvtest.cpp
  #src/grisu2btest.cpp
  #src/milotest.cpp
  #src/fpconv/fpconv.c
  #src/grisu/grisu2b_59_56.c
  )

target_include_directories(dtoa-benchmark PRIVATE src src/fmt/include)
target_compile_features(dtoa-benchmark PRIVATE cxx_std_20)

if (APPLE)
  execute_process(
    COMMAND sysctl -n machdep.cpu.brand_string
    OUTPUT_VARIABLE CPU_NAME
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  string(REPLACE " " "-" CPU_NAME "${CPU_NAME}")
  string(TOLOWER "${CPU_NAME}" CPU_NAME)
else ()
  set(CPU_NAME "unknown")
endif ()
target_compile_definitions(dtoa-benchmark PRIVATE MACHINE="${CPU_NAME}")

add_custom_target(
  run-benchmark
  COMMAND dtoa-benchmark
  COMMAND cmake -P convert-results.cmake
  # Run in the source directory because we want results to be in the source
  # result directory.
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  DEPENDS dtoa-benchmark
)
