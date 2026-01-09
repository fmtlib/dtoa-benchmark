#include "zmij/zmij.h"

#include "benchmark.h"

REGISTER_METHOD("zmij", [](double x, char* buffer) noexcept {
  zmij::write(buffer, zmij::double_buffer_size, x);
});
