// Unrounded scaling float-to-string conversion.
// From Russ Cox, "Floating-Point Printing and Parsing Can Be Simple And Fast"
// https://research.swtch.com/fp
// Source: https://github.com/rsc/fpfmt (BSD-3-Clause)

#ifndef USCALE_H
#define USCALE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// uscale_short converts f to its shortest decimal representation,
// writing the result into buffer (null-terminated).
void uscale_short(double f, char* buffer);

#ifdef __cplusplus
}
#endif

#endif // USCALE_H
