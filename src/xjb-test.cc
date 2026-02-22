#include "benchmark.h"
#include "xjb/xjb64.h"

static register_method _("xjb64",
                         [](double x, char* buffer) -> char*{
                            xjb64(x, buffer);
                            return nullptr;
                        });
