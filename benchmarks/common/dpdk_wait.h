/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright(c) 2017 Cavium, Inc
 * Copyright(c) 2019 Arm Limited
 */
/* Mechanically extracted; included after platform definitions. */
#ifndef BENCH_DPDK_WAIT_H
#define BENCH_DPDK_WAIT_H
static __rte_always_inline void
rte_wait_until_equal_32(volatile uint32_t *addr, uint32_t expected,
		rte_memory_order memorder)
{
	assert(memorder == rte_memory_order_acquire || memorder == rte_memory_order_relaxed);

	while (rte_atomic_load_explicit((volatile __rte_atomic uint32_t *)addr, memorder)
			!= expected)
		rte_pause();
}
#endif
