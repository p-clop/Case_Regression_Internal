/* SPDX-License-Identifier: BSD-3-Clause
 * DPDK generic CAS spinlock protects a shared progress record.
 */
#include "../common/bench.h"
#include "../common/dpdk_spinlock.h"

struct record { uint64_t count, checksum; };
struct observation { struct record before, after; };
struct context {
    rte_spinlock_t lock;
    struct record record;
    struct start_gate gate;
    uint32_t iterations, yield_every;
};
struct worker {
    struct context *ctx;
    uint64_t completed, pauses, errors;
    struct observation *observations;
};

static uint64_t checksum(uint64_t count)
{
    return count * UINT64_C(11400714819323198485) ^ UINT64_C(0x5a5aa5a5deadcafe);
}

/* Accessed only while holding the same lock, including the initial read. */
static bool update_record(struct record *record)
{
    if (record->checksum != checksum(record->count))
        return false;
    uint64_t next = record->count + 1;
    record->count = next;
    record->checksum = checksum(next);
#ifdef BENCH_INJECT_CORRUPTION
    if (next == 1)
        record->checksum ^= 1; /* Checker control; all accesses remain locked. */
#endif
    return true;
}

static void *worker(void *argument)
{
    struct worker *state = argument;
    struct context *ctx = state->ctx;
    await_start(&ctx->gate);
    for (uint32_t i = 0; i < ctx->iterations; ++i) {
        rte_spinlock_lock(&ctx->lock);
        if (state->observations)
            state->observations[state->completed].before = ctx->record;
        if (!update_record(&ctx->record)) {
            ++state->errors;
            rte_spinlock_unlock(&ctx->lock);
            break;
        }
        if (state->observations)
            state->observations[state->completed].after = ctx->record;
        ++state->completed;
        /* Encourage a contending thread to encounter the real wait loop. */
        if (ctx->yield_every && (i + 1) % ctx->yield_every == 0)
            sched_yield();
        rte_spinlock_unlock(&ctx->lock);
    }
    state->pauses = bench_pause_count;
    return NULL;
}

/* Worker-private buffers are read only after both pthread_join calls. */
static bool write_trace(const char *path, const struct worker states[2])
{
    FILE *file = fopen(path, "wx");
    if (!file)
        return false;
    bool ok = fputs("{\"schema\":\"b02-record-trace-1\"}\n", file) >= 0;
    for (unsigned worker_id = 0; ok && worker_id < 2; ++worker_id)
        for (uint64_t i = 0; ok && i < states[worker_id].completed; ++i) {
            const struct observation *o = &states[worker_id].observations[i];
            ok = fprintf(file, "[%u,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 "]\n",
                         worker_id, i + 1, o->before.count, o->before.checksum,
                         o->after.count, o->after.checksum) >= 0;
        }
    if (fclose(file) != 0)
        ok = false;
    return ok;
}

int main(int argc, char **argv)
{
    struct context ctx = {.iterations = 100000, .yield_every = 64};
    const char *trace_path = NULL;
    for (int i = 1; i < argc; ++i) {
        if (i + 1 >= argc) { fprintf(stderr, "each option requires a value\n"); return 2; }
        const char *key = argv[i], *value = argv[++i];
        if (!strcmp(key, "--iterations")) ctx.iterations = parse_u32(value, 1, 10000000);
        else if (!strcmp(key, "--yield-every")) ctx.yield_every = parse_u32(value, 0, UINT32_MAX);
        else if (!strcmp(key, "--trace")) trace_path = value;
        else { fprintf(stderr, "unknown option: %s\n", key); return 2; }
    }
    rte_spinlock_init(&ctx.lock);
    /* Quiescent API boundary checks. They do not prove concurrent exclusion. */
    int first = rte_spinlock_trylock(&ctx.lock);
    int held = rte_spinlock_trylock(&ctx.lock);
    rte_spinlock_unlock(&ctx.lock);
    if (!first || held) { puts("{\"status\":\"FAIL\",\"reason\":\"preflight\"}"); return 1; }
    ctx.record = (struct record){0, checksum(0)};
    atomic_init(&ctx.gate.ready, 0);
    atomic_init(&ctx.gate.go, false);
    struct worker states[2] = {{.ctx = &ctx}, {.ctx = &ctx}};
    if (trace_path) {
        for (unsigned i = 0; i < 2; ++i) {
            states[i].observations = calloc(ctx.iterations, sizeof(*states[i].observations));
            if (!states[i].observations) {
                perror("trace allocation");
                free(states[0].observations);
                free(states[1].observations);
                return 2;
            }
        }
    }
    pthread_t threads[2];
    for (unsigned i = 0; i < 2; ++i)
        check_pthread(pthread_create(&threads[i], NULL, worker, &states[i]), "pthread_create");
    release_start(&ctx.gate);
    for (unsigned i = 0; i < 2; ++i)
        check_pthread(pthread_join(threads[i], NULL), "pthread_join");
    if (trace_path && !write_trace(trace_path, states)) {
        perror("write trace (requires a new file)");
        free(states[0].observations);
        free(states[1].observations);
        return 2;
    }
    uint64_t expected = 2 * (uint64_t)ctx.iterations;
    bool ok = states[0].completed == ctx.iterations && states[1].completed == ctx.iterations &&
        !states[0].errors && !states[1].errors && ctx.record.count == expected &&
        ctx.record.checksum == checksum(expected) && atomic_load(&ctx.lock.locked) == 0;
    printf("{\"case\":\"B02_spinlock\",\"status\":\"%s\",\"preflight\":true,"
           "\"iterations_per_worker\":%" PRIu32 ",\"expected_count\":%" PRIu64 ","
           "\"final_count\":%" PRIu64 ",\"checksum\":%" PRIu64 ","
           "\"locked\":%d,"
           "\"completed\":[%" PRIu64 ",%" PRIu64 "],"
           "\"errors\":[%" PRIu64 ",%" PRIu64 "],\"wait_pauses\":[%" PRIu64 ",%" PRIu64 "]}\n",
           ok ? "PASS" : "FAIL", ctx.iterations, expected, ctx.record.count, ctx.record.checksum,
           atomic_load(&ctx.lock.locked),
           states[0].completed, states[1].completed, states[0].errors, states[1].errors,
           states[0].pauses, states[1].pauses);
    free(states[0].observations);
    free(states[1].observations);
    return ok ? 0 : 1;
}
