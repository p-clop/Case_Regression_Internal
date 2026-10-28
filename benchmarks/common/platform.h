/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef BENCH_PLATFORM_H
#define BENCH_PLATFORM_H
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define RTE_ENABLE_STDATOMIC 1
#define RTE_USE_C11_MEM_MODEL 1
#define RTE_FORCE_INTRINSICS 1
#include "../vendor/dpdk/rte_stdatomic.h"

#define __rte_always_inline inline __attribute__((always_inline))
#define __rte_no_thread_safety_analysis
#define __rte_exclusive_lock_function(x)
#define __rte_unlock_function(x)
#define __rte_exclusive_trylock_function(ok, x)
#define __rte_warn_unused_result __attribute__((warn_unused_result))
#define RTE_SET_USED(x) (void)(x)
#define likely(x) __builtin_expect(!!(x), 1)
#define unlikely(x) __builtin_expect(!!(x), 0)
#define rte_atomic_thread_fence(order) __rte_atomic_thread_fence(order)
typedef uint64_t unaligned_uint64_t __attribute__((aligned(1), may_alias));
typedef struct { uint64_t val[2]; } rte_int128_t;

/* Local observation only: adds no inter-thread synchronization. */
static _Thread_local uint64_t bench_pause_count;
static inline void rte_pause(void)
{
    ++bench_pause_count;
#if defined(__x86_64__) || defined(__i386__)
    __asm__ __volatile__("pause");
#elif defined(__aarch64__)
    __asm__ __volatile__("yield");
#else
    atomic_signal_fence(memory_order_relaxed);
#endif
}
_Static_assert(sizeof(int) == sizeof(uint32_t), "DPDK lock requires 32-bit int");
#include "dpdk_wait.h"
#endif
