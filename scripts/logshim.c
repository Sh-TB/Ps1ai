// logshim.c - varargs log bridge for libretro cores -> Python callback
#include <stdio.h>
#include <stdarg.h>
#include <stdint.h>

typedef void (*sink_t)(const char* s);
static sink_t sink = 0;

__attribute__((visibility("default")))
void set_sink(sink_t f) { sink = f; }

__attribute__((visibility("default"), format(printf, 2, 3)))
void core_log_shim(unsigned level, const char* fmt, ...) {
    char buf[4096];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (sink) sink(buf);
}
