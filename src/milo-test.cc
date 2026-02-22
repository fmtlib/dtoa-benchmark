#include "benchmark.h"
#include "milo/dtoa_milo.h"

static register_method _("milo", [](double value, char* buffer) -> char* {
    dtoa_milo(value, buffer);
    return nullptr;
});
