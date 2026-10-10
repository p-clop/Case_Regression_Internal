#include <pthread.h>

int shared = 0;

static void helper_write(void) { shared = 1; }
static int helper_read(void) { return shared; }

void *writer(void *arg) {
    (void)arg;
    helper_write();
    return 0;
}

void *reader(void *arg) {
    (void)arg;
    int seen = helper_read();
    (void)seen;
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
