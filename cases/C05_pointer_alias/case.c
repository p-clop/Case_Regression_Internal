#include <pthread.h>

struct State { int flag; int padding; };
struct State state = {0, 0};

void *writer(void *arg) {
    (void)arg;
    int *p = &state.flag;
    *p = 1;
    return 0;
}

void *reader(void *arg) {
    (void)arg;
    int seen = state.flag;
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
