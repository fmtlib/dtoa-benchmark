cmake_minimum_required(VERSION 3.5.0)

# Joins arguments and places the results in ${result_var}.
function(join result_var)
  set(result )
  foreach (arg ${ARGN})
    set(result "${result}${arg}")
  endforeach ()
  set(${result_var} "${result}" PARENT_SCOPE)
endfunction()

# Set the default build type to release because we want to benchmark
# optimized code.
if (NOT CMAKE_BUILD_TYPE)
  join(doc "Choose the type of build, options are: None(CMAKE_CXX_FLAGS or "
           "CMAKE_C_FLAGS used) Debug Release RelWithDebInfo MinSizeRel.")
  set(CMAKE_BUILD_TYPE Release CACHE STRING ${doc})
endif ()

project(DTOA_BENCHMARK C CXX)

add_executable(
  dtoa-benchmark
  src/main.cpp

  # Tests:
  src/ryutest.cpp
  src/doubleconvtest.cpp
  src/fmttest.cpp
  src/fmttest_full.cpp
  #src/dtoa_puff.cpp
  src/dragonbox_test.cpp
  src/fpconvtest.cpp
  src/gaytest.cpp
  src/grisu2btest.cpp
  #src/milotest.cpp
  src/null.cpp
  src/ostringstream.cpp
  src/sprintf.cpp

  # Libraries:
  src/double-conversion/bignum-dtoa.cc
  src/double-conversion/bignum.cc
  src/double-conversion/cached-powers.cc
  src/double-conversion/diy-fp.cc
  src/double-conversion/double-conversion.cc
  src/double-conversion/fast-dtoa.cc
  src/double-conversion/fixed-dtoa.cc
  src/double-conversion/strtod.cc
  src/dragonbox/dragonbox_to_chars.cpp
  src/fmt/src/format.cc
  src/fpconv/fpconv.c
  src/gay/dtoa.c
  src/gay/g_fmt.c
  src/grisu/grisu2b_59_56.c
)

target_include_directories(dtoa-benchmark PRIVATE src src/fmt/include)
target_compile_features(dtoa-benchmark PRIVATE cxx_std_17)

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
