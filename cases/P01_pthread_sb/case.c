#include <pthread.h>

/* Structural input only: the ordinary shared accesses race in C. */
int x = 0;
int y = 0;
int private_noise = 0;

void *writer(void *arg) {
    (void)arg;
    x = 1;
    int r0 = y;
    private_noise = 7;
    (void)r0;
    return 0;
}

void *reader(void *arg) {
    (void)arg;
    y = 1;
    int r1 = x;
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
