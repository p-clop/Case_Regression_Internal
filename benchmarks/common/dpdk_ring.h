/* SPDX-License-Identifier: BSD-3-Clause
 * Minimal, explicitly reduced layout for the unchanged DPDK ring algorithms.
 * This is not ABI compatible with the complete DPDK rte_ring structure.
 */
#ifndef BENCH_DPDK_RING_H
#define BENCH_DPDK_RING_H
#include "platform.h"

enum rte_ring_queue_behavior {
    RTE_RING_QUEUE_FIXED = 0,
    RTE_RING_QUEUE_VARIABLE
};
struct rte_ring_headtail {
    volatile RTE_ATOMIC(uint32_t) head;
    volatile RTE_ATOMIC(uint32_t) tail;
};
struct rte_ring {
    uint32_t size;
    uint32_t mask;
    uint32_t capacity;
    struct rte_ring_headtail prod;
    struct rte_ring_headtail cons;
    /* Keep the following uint64_t element table naturally aligned. */
    uint32_t reserved;
};
_Static_assert(sizeof(struct rte_ring) % _Alignof(uint64_t) == 0,
               "element table must be uint64_t aligned");

/* Both files remain byte-for-byte equal to the pinned upstream revision. */
#include "../vendor/dpdk/rte_ring_elem_pvt.h"
#endif
