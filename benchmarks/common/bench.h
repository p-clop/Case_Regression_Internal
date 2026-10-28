/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef BENCH_SUPPORT_H
#define BENCH_SUPPORT_H
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdatomic.h>
#include <string.h>

static inline uint32_t parse_u32(const char *text, uint32_t min, uint32_t max)
{
    char *end;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 0);
    if (errno || !*text || *end || text[0] == '-' || value < min || value > max) {
        fprintf(stderr, "invalid integer: %s (range %" PRIu32 "..%" PRIu32 ")\n",
                text, min, max);
        exit(2);
    }
    return (uint32_t)value;
}

static inline void check_pthread(int code, const char *operation)
{
    if (code) {
        fprintf(stderr, "%s: %s\n", operation, strerror(code));
        exit(2);
    }
}

/* Used once before the measured protocol, never between its operations. */
struct start_gate { atomic_uint ready; atomic_bool go; };
static inline void await_start(struct start_gate *gate)
{
    atomic_fetch_add_explicit(&gate->ready, 1, memory_order_release);
    while (!atomic_load_explicit(&gate->go, memory_order_acquire))
        sched_yield();
}
static inline void release_start(struct start_gate *gate)
{
    while (atomic_load_explicit(&gate->ready, memory_order_acquire) != 2)
        sched_yield();
    atomic_store_explicit(&gate->go, true, memory_order_release);
}
#endif
