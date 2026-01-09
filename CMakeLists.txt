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
  src/benchmark.cc

  # Tests:
  #src/asteria-test.cc
  src/double-conversion-test.cc
  src/dragonbox-test.cc
  src/fmt-test.cc
  # Grisu2 variants are disabled since they don't guarantee correctness.
  #src/milo-test.cc
  src/null-test.cc
  src/ostringstream-test.cc
  #src/puff-test.cc
  src/ryu-test.cc
  src/schubfach-test.cc
  src/sprintf-test.cc
  src/to_chars-test.cc
  src/xjb-test.cc
  src/yy-test.cc
  src/zmij-test.cc

  # Libraries:
  src/asteria/ascii_numput.cpp
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
  src/ryu/d2s.c
  src/schubfach/schubfach.cc
  src/xjb/xjb64.cpp
  src/yy/yy_double.c
  src/zmij/zmij.cc
)

target_compile_options(dtoa-benchmark PUBLIC $<$<CXX_COMPILER_ID:MSVC>:/utf-8>)
target_compile_features(dtoa-benchmark PRIVATE cxx_std_20)
target_include_directories(dtoa-benchmark PRIVATE src src/fmt/include)

if (APPLE)
  execute_process(
    COMMAND sysctl -n machdep.cpu.brand_string
    OUTPUT_VARIABLE CPU_NAME
  )
elseif(LINUX)
  execute_process(
    COMMAND lscpu
    OUTPUT_VARIABLE CPU_NAME
  )
  string(REGEX MATCH "Model name: ([^\n]*)\n" CPU_NAME "${CPU_NAME}")
  string(REGEX REPLACE
    "AMD|Intel|CPU|\\(R\\)|\\(TM\\)|@|[^ ]+-Core Processor" ""
    CPU_NAME "${CMAKE_MATCH_1}"
  )
else ()
  set(CPU_NAME "unknown")
endif ()

string(STRIP "${CPU_NAME}" CPU_NAME)
string(REPLACE "  " " " CPU_NAME "${CPU_NAME}")
string(REPLACE " " "-" CPU_NAME "${CPU_NAME}")
string(TOLOWER "${CPU_NAME}" CPU_NAME)
message("CPU_NAME: ${CPU_NAME}")
target_compile_definitions(dtoa-benchmark PRIVATE MACHINE="${CPU_NAME}")

execute_process(COMMAND git rev-parse --short HEAD OUTPUT_VARIABLE COMMIT_HASH)
string(STRIP "${COMMIT_HASH}" COMMIT_HASH)

function(add_benchmark_target name num_trials)
  add_custom_target(
    ${name}
    COMMAND dtoa-benchmark ${COMMIT_HASH} ${num_trials}
    COMMAND cmake -P convert-results.cmake
    # Run in the source directory because we want results to be in the source
    # results directory.
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    DEPENDS dtoa-benchmark
  )
endfunction()

add_benchmark_target(run-benchmark 10)
add_benchmark_target(run-benchmark-fast 3)
