#include <pthread.h>
#include <stdatomic.h>

_Atomic int x = 0;
_Atomic int y = 0;

void *writer(void *arg) {
    (void)arg;
    atomic_store_explicit(&x, 1, memory_order_relaxed);
    int r0 = atomic_load_explicit(&y, memory_order_relaxed);
    (void)r0;
    return 0;
}

void *reader(void *arg) {
    (void)arg;
    atomic_store_explicit(&y, 1, memory_order_relaxed);
    int r1 = atomic_load_explicit(&x, memory_order_relaxed);
    (void)r1;
    return 0;
}

int main(void) {
    pthread_t first, second;
    pthread_create(&first, 0, writer, 0);
    pthread_create(&second, 0, reader, 0);
    pthread_join(first, 0);
    pthread_join(second, 0);
    return 0;
}
