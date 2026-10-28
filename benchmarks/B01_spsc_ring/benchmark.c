/* SPDX-License-Identifier: BSD-3-Clause
 * DPDK SP/SC element-ring benchmark driver. See provenance.md.
 */
#include "../common/bench.h"
#include "../common/dpdk_ring.h"

struct context {
    struct rte_ring *ring;
    struct start_gate gate;
    atomic_bool abort_run;
    uint32_t iterations, batch, yield_every;
    uint64_t produced, consumed, producer_waits, consumer_waits;
    uint64_t enqueue_wraps, dequeue_wraps;
    uint64_t observed, expected;
    uint64_t *received;
    uint32_t received_count;
    int error;
};

/* Two independently checkable fields in one naturally aligned 8-byte element. */
static uint64_t message(uint32_t sequence)
{
    uint32_t checksum = sequence * UINT32_C(2654435761) ^ UINT32_C(0xa5a55a5a);
    return ((uint64_t)sequence << 32) | checksum;
}

static unsigned enqueue(struct rte_ring *r, const uint64_t *data, unsigned n,
                        enum rte_ring_queue_behavior behavior)
{
    return __rte_ring_do_enqueue_elem(r, data, sizeof(*data), n, behavior, 1, NULL);
}

static unsigned dequeue(struct rte_ring *r, uint64_t *data, unsigned n,
                        enum rte_ring_queue_behavior behavior)
{
    return __rte_ring_do_dequeue_elem(r, data, sizeof(*data), n, behavior, 1, NULL);
}

/* Quiescent reset, called only before any worker starts. */
static void reset(struct rte_ring *r, uint32_t initial)
{
    atomic_init(&r->prod.head, initial);
    atomic_init(&r->prod.tail, initial);
    atomic_init(&r->cons.head, initial);
    atomic_init(&r->cons.tail, initial);
}

/* Deterministic API boundary checks, separate from concurrent observations. */
static bool preflight(struct rte_ring *r)
{
    uint64_t value = message(1), out = 0;
    if (dequeue(r, &out, 1, RTE_RING_QUEUE_FIXED) != 0)
        return false;
    for (uint32_t i = 0; i < r->capacity; ++i) {
        value = message(i + 1);
        if (enqueue(r, &value, 1, RTE_RING_QUEUE_FIXED) != 1)
            return false;
    }
    if (enqueue(r, &value, 1, RTE_RING_QUEUE_FIXED) != 0)
        return false;
    for (uint32_t i = 0; i < r->capacity; ++i)
        if (dequeue(r, &out, 1, RTE_RING_QUEUE_FIXED) != 1 || out != message(i + 1))
            return false;
    return dequeue(r, &out, 1, RTE_RING_QUEUE_FIXED) == 0;
}

static void *producer(void *argument)
{
    struct context *ctx = argument;
    struct rte_ring *r = ctx->ring;
    uint64_t data[8];
    uint32_t next = 1;
    await_start(&ctx->gate);
    while (next <= ctx->iterations &&
           !atomic_load_explicit(&ctx->abort_run, memory_order_relaxed)) {
        unsigned n = 1 + (next - 1) % ctx->batch;
        if (n > ctx->iterations - next + 1)
            n = ctx->iterations - next + 1;
        for (unsigned i = 0; i < n; ++i) {
            data[i] = message(next + i);
#ifdef BENCH_INJECT_CORRUPTION
            if (next + i == 1)
                data[i] ^= 1; /* Checker control: not an upstream defect. */
#endif
        }
        uint32_t old = atomic_load_explicit(&r->prod.head, memory_order_relaxed);
        unsigned written = enqueue(r, data, n, RTE_RING_QUEUE_VARIABLE);
        if (!written) {
            ++ctx->producer_waits;
            sched_yield();
            continue;
        }
        if ((old & r->mask) + written > r->size)
            ++ctx->enqueue_wraps;
        next += written;
        ctx->produced += written;
        if (ctx->yield_every && ctx->produced % ctx->yield_every == 0)
            sched_yield();
    }
    return NULL;
}

static void *consumer(void *argument)
{
    struct context *ctx = argument;
    struct rte_ring *r = ctx->ring;
    uint64_t data[8];
    uint32_t next = 1;
    await_start(&ctx->gate);
    while (next <= ctx->iterations) {
        unsigned n = 1 + next % ctx->batch;
        if (n > ctx->iterations - next + 1)
            n = ctx->iterations - next + 1;
        uint32_t old = atomic_load_explicit(&r->cons.head, memory_order_relaxed);
        unsigned read = dequeue(r, data, n, RTE_RING_QUEUE_VARIABLE);
        if (!read) {
            ++ctx->consumer_waits;
            sched_yield();
            continue;
        }
        if ((old & r->mask) + read > r->size)
            ++ctx->dequeue_wraps;
        for (unsigned i = 0; i < read; ++i) {
            /* Consumer-owned evidence; main reads it only after both joins. */
            if (ctx->received)
                ctx->received[ctx->received_count++] = data[i];
            if (data[i] != message(next + i)) {
                ctx->observed = data[i];
                ctx->expected = message(next + i);
                ctx->error = 1;
                atomic_store_explicit(&ctx->abort_run, true, memory_order_relaxed);
                return NULL;
            }
        }
        next += read;
        ctx->consumed += read;
        if (ctx->yield_every && ctx->consumed % ctx->yield_every == 0)
            sched_yield();
    }
    return NULL;
}

/* No file I/O or extra cross-thread synchronization on the message path. */
static bool write_trace(const char *path, const struct context *ctx)
{
    FILE *file = fopen(path, "wx");
    if (!file)
        return false;
    bool ok = fputs("{\"schema\":\"b01-fifo-trace-1\"}\n", file) >= 0;
    for (uint32_t i = 0; ok && i < ctx->received_count; ++i)
        ok = fprintf(file, "%" PRIu64 "\n", ctx->received[i]) >= 0;
    if (fclose(file) != 0)
        ok = false;
    return ok;
}

int main(int argc, char **argv)
{
    uint32_t size = 8, initial = 0;
    const char *trace_path = NULL;
    struct context ctx = {.iterations = 100000, .batch = 5, .yield_every = 64};
    for (int i = 1; i < argc; ++i) {
        if (i + 1 >= argc) {
            fprintf(stderr, "each option requires a value\n");
            return 2;
        }
        const char *key = argv[i], *value = argv[++i];
        if (!strcmp(key, "--iterations")) ctx.iterations = parse_u32(value, 1, 10000000);
        else if (!strcmp(key, "--size")) size = parse_u32(value, 2, 65536);
        else if (!strcmp(key, "--batch")) ctx.batch = parse_u32(value, 1, 8);
        else if (!strcmp(key, "--initial-index")) initial = parse_u32(value, 0, UINT32_MAX);
        else if (!strcmp(key, "--yield-every")) ctx.yield_every = parse_u32(value, 0, UINT32_MAX);
        else if (!strcmp(key, "--trace")) trace_path = value;
        else { fprintf(stderr, "unknown option: %s\n", key); return 2; }
    }
    if ((size & (size - 1)) || ctx.batch >= size) {
        fprintf(stderr, "size must be a power of two and batch <= size - 1\n");
        return 2;
    }
    struct rte_ring *r = calloc(1, sizeof(*r) + (size_t)size * sizeof(uint64_t));
    if (!r) { perror("calloc"); return 2; }
    r->size = size; r->mask = size - 1; r->capacity = size - 1;
    reset(r, initial);
    bool boundary_ok = preflight(r);
    reset(r, initial);
    if (!boundary_ok) {
        puts("{\"status\":\"FAIL\",\"reason\":\"preflight\"}");
        free(r);
        return 1;
    }
    ctx.ring = r;
    if (trace_path) {
        ctx.received = calloc(ctx.iterations, sizeof(*ctx.received));
        if (!ctx.received) { perror("trace allocation"); free(r); return 2; }
    }
    atomic_init(&ctx.abort_run, false);
    atomic_init(&ctx.gate.ready, 0);
    atomic_init(&ctx.gate.go, false);
    pthread_t prod, cons;
    check_pthread(pthread_create(&prod, NULL, producer, &ctx), "pthread_create producer");
    check_pthread(pthread_create(&cons, NULL, consumer, &ctx), "pthread_create consumer");
    release_start(&ctx.gate);
    check_pthread(pthread_join(prod, NULL), "pthread_join producer");
    check_pthread(pthread_join(cons, NULL), "pthread_join consumer");
    if (trace_path && !write_trace(trace_path, &ctx)) {
        perror("write trace (requires a new file)");
        free(ctx.received);
        free(r);
        return 2;
    }
    uint32_t tail = initial + ctx.iterations;
    bool ok = !ctx.error && ctx.produced == ctx.iterations && ctx.consumed == ctx.iterations &&
        atomic_load(&r->prod.head) == tail && atomic_load(&r->prod.tail) == tail &&
        atomic_load(&r->cons.head) == tail && atomic_load(&r->cons.tail) == tail;
    printf("{\"case\":\"B01_spsc_ring\",\"status\":\"%s\","
           "\"iterations\":%" PRIu32 ",\"size\":%" PRIu32 ",\"batch\":%" PRIu32 ","
           "\"initial_index\":%" PRIu32 ",\"final_index\":%" PRIu32 ","
           "\"final_indexes\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],"
           "\"preflight\":true,\"produced\":%" PRIu64 ",\"consumed\":%" PRIu64 ","
           "\"producer_waits\":%" PRIu64 ",\"consumer_waits\":%" PRIu64 ","
           "\"enqueue_copy_wraps\":%" PRIu64 ",\"dequeue_copy_wraps\":%" PRIu64 ","
           "\"observed\":%" PRIu64 ",\"expected\":%" PRIu64 "}\n",
           ok ? "PASS" : "FAIL", ctx.iterations, size, ctx.batch, initial,
           atomic_load(&r->cons.tail), atomic_load(&r->prod.head), atomic_load(&r->prod.tail),
           atomic_load(&r->cons.head), atomic_load(&r->cons.tail), ctx.produced, ctx.consumed,
           ctx.producer_waits, ctx.consumer_waits, ctx.enqueue_wraps, ctx.dequeue_wraps,
           ctx.observed, ctx.expected);
    free(ctx.received);
    free(r);
    return ok ? 0 : 1;
}
