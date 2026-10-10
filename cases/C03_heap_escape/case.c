#include <pthread.h>
#include <stdlib.h>

void *writer(void *arg) {
    int *p = arg;
    *p = 1;
    return 0;
}

void *reader(void *arg) {
    int *p = arg;
    int seen = *p;
    (void)seen;
    return 0;
}

int main(void) {
    int *heap_value = malloc(sizeof *heap_value);
    if (!heap_value) return 1;
    *heap_value = 0;
    pthread_t first, second;
    pthread_create(&first, 0, writer, heap_value);
    pthread_create(&second, 0, reader, heap_value);
    pthread_join(first, 0);
    pthread_join(second, 0);
    free(heap_value);
    return 0;
}
