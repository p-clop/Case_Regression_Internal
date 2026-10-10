#include <pthread.h>

struct State { int data; int flag; };
struct State state = {0, 0};

void *writer(void *arg) {
    (void)arg;
    state.data = 1;
    state.flag = 1;
    return 0;
}

void *reader(void *arg) {
    (void)arg;
    int seen_flag = state.flag;
    int seen_data = state.data;
    (void)seen_flag;
    (void)seen_data;
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
