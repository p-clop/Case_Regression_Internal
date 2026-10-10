#include <pthread.h>

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
    int local = 0;
    pthread_t first, second;
    pthread_create(&first, 0, writer, &local);
    pthread_create(&second, 0, reader, &local);
    pthread_join(first, 0);
    pthread_join(second, 0);
    return 0;
}
