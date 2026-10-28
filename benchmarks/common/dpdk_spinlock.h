/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright(c) 2010-2014 Intel Corporation
 */
/* Mechanically extracted; see scripts/check_sources.py. */
#ifndef BENCH_DPDK_SPINLOCK_H
#define BENCH_DPDK_SPINLOCK_H
#include "platform.h"
typedef struct __rte_lockable {
	volatile RTE_ATOMIC(int) locked; /**< lock status 0 = unlocked, 1 = locked */
} rte_spinlock_t;

/**
 * A static spinlock initializer.
 */
#define RTE_SPINLOCK_INITIALIZER { 0 }

/**
 * Initialize the spinlock to an unlocked state.
 *
 * @param sl
 *   A pointer to the spinlock.
 */
static inline void
rte_spinlock_init(rte_spinlock_t *sl)
{
	sl->locked = 0;
}

/**
 * Take the spinlock.
 *
 * @param sl
 *   A pointer to the spinlock.
 */
static inline void
rte_spinlock_lock(rte_spinlock_t *sl)
	__rte_exclusive_lock_function(sl);

#ifdef RTE_FORCE_INTRINSICS
static inline void
rte_spinlock_lock(rte_spinlock_t *sl)
	__rte_no_thread_safety_analysis
{
	int exp = 0;

	while (!rte_atomic_compare_exchange_strong_explicit(&sl->locked, &exp, 1,
				rte_memory_order_acquire, rte_memory_order_relaxed)) {
		rte_wait_until_equal_32((volatile uint32_t *)(uintptr_t)&sl->locked,
			       0, rte_memory_order_relaxed);
		exp = 0;
	}
}
#endif

/**
 * Release the spinlock.
 *
 * @param sl
 *   A pointer to the spinlock.
 */
static inline void
rte_spinlock_unlock(rte_spinlock_t *sl)
	__rte_unlock_function(sl);

#ifdef RTE_FORCE_INTRINSICS
static inline void
rte_spinlock_unlock(rte_spinlock_t *sl)
	__rte_no_thread_safety_analysis
{
	rte_atomic_store_explicit(&sl->locked, 0, rte_memory_order_release);
}
#endif

/**
 * Try to take the lock.
 *
 * @param sl
 *   A pointer to the spinlock.
 * @return
 *   1 if the lock is successfully taken; 0 otherwise.
 */
__rte_warn_unused_result
static inline int
rte_spinlock_trylock(rte_spinlock_t *sl)
	__rte_exclusive_trylock_function(1, sl);

#ifdef RTE_FORCE_INTRINSICS
static inline int
rte_spinlock_trylock(rte_spinlock_t *sl)
	__rte_no_thread_safety_analysis
{
	int exp = 0;
	return rte_atomic_compare_exchange_strong_explicit(&sl->locked, &exp, 1,
				rte_memory_order_acquire, rte_memory_order_relaxed);
}
#endif


#endif
