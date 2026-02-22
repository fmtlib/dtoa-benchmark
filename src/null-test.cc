#include "benchmark.h"

static register_method _("null", [](double, char*) -> char* {
    return nullptr;
});
