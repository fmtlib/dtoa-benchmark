// Unrounded scaling float-to-string conversion.
// From Russ Cox, "Floating-Point Printing and Parsing Can Be Simple And Fast"
// https://research.swtch.com/fp
// Source: https://github.com/rsc/fpfmt commit 6255750 (19 Jan 2026)

#include "uscale/uscale.h"

#include "benchmark.h"

static register_method _("uscale", [](double value, char* buffer) -> char* {
  uscale_short(value, buffer);
  return nullptr;
});
