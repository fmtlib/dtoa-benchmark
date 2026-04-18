#include "zmij/zmij.h"

#include "benchmark.h"

static register_method _("zmij", [](double x, char* buffer) noexcept {
  return zmij::write(buffer, zmij::double_buffer_size, x);
});
