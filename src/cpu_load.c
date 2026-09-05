#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>

static volatile sig_atomic_t stop = 0;

void handle_sigint(int sig)
{
    (void)sig;
    stop = 1;
}

void *cpu_worker(void *arg)
{
    (void)arg;

    volatile uint64_t x = 123456789;

    while (!stop) {
        x = x * 1103515245ULL + 12345ULL;
        x ^= x >> 13;
        x *= 2654435761ULL;
    }

    return NULL;
}

int main(int argc, char *argv[])
{
    if (argc != 3) {
        fprintf(stderr,
                "Usage: %s <workers> <seconds>\n"
                "Example: %s 2 30\n",
                argv[0], argv[0]);
        return 1;
    }

    int workers = atoi(argv[1]);
    int seconds = atoi(argv[2]);

    if (workers <= 0 || seconds <= 0) {
        fprintf(stderr, "Workers and seconds must be positive.\n");
        return 1;
    }

    long cpus = sysconf(_SC_NPROCESSORS_ONLN);

    printf("Logical CPUs available: %ld\n", cpus);
    printf("CPU load workers: %d\n", workers);
    printf("Duration: %d seconds\n", seconds);
    printf("Starting CPU load...\n");

    signal(SIGINT, handle_sigint);

    pthread_t *threads = malloc(workers * sizeof(pthread_t));

    if (threads == NULL) {
        perror("malloc");
        return 1;
    }

    for (int i = 0; i < workers; i++) {
        if (pthread_create(&threads[i], NULL, cpu_worker, NULL) != 0) {
            perror("pthread_create");
            stop = 1;

            for (int j = 0; j < i; j++) {
                pthread_join(threads[j], NULL);
            }

            free(threads);
            return 1;
        }
    }

    sleep(seconds);

    stop = 1;

    for (int i = 0; i < workers; i++) {
        pthread_join(threads[i], NULL);
    }

    free(threads);

    printf("CPU load finished.\n");

    return 0;
}
