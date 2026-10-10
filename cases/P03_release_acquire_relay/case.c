#include <pthread.h>
#include <stdatomic.h>

_Atomic int data = 0;
_Atomic int flag = 0;
_Atomic int relay_flag = 0;

static void publish_data(void) {
    atomic_store_explicit(&data, 1, memory_order_relaxed);
    atomic_store_explicit(&flag, 1, memory_order_release);
}

static void relay_once(void) {
    int seen = atomic_load_explicit(&flag, memory_order_acquire);
    atomic_store_explicit(&relay_flag, seen, memory_order_release);
}

static void observe_data(void) {
    int ready = atomic_load_explicit(&relay_flag, memory_order_acquire);
    int payload = atomic_load_explicit(&data, memory_order_relaxed);
    (void)ready;
    (void)payload;
}

void *writer(void *arg) {
    (void)arg;
    publish_data();
    return 0;
}

void *relay(void *arg) {
    (void)arg;
    relay_once();
    return 0;
}

void *reader(void *arg) {
    (void)arg;
    observe_data();
    return 0;
}

int main(void) {
    pthread_t first, second, third;
    pthread_create(&first, 0, writer, 0);
    pthread_create(&second, 0, relay, 0);
    pthread_create(&third, 0, reader, 0);
    pthread_join(first, 0);
    pthread_join(second, 0);
    pthread_join(third, 0);
    return 0;
}
