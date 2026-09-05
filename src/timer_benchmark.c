#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include <errno.h>
#include <string.h>
#include <math.h>

static int64_t timespec_to_ns(const struct timespec *ts)
{
    return (int64_t)ts->tv_sec * 1000000000LL + ts->tv_nsec;
}

static void ns_to_timespec(int64_t ns, struct timespec *ts)
{
    ts->tv_sec = ns / 1000000000LL;
    ts->tv_nsec = ns % 1000000000LL;
}

static int compare_int64(const void *a, const void *b)
{
    int64_t x = *(const int64_t *)a;
    int64_t y = *(const int64_t *)b;

    if (x < y)
        return -1;
    if (x > y)
        return 1;
    return 0;
}

static int64_t percentile(int64_t *values, int count, double p)
{
    double position = p * (count - 1);
    int lower = (int)floor(position);
    int upper = (int)ceil(position);

    if (lower == upper)
        return values[lower];

    double fraction = position - lower;

    return (int64_t)(
        values[lower] +
        fraction * (values[upper] - values[lower])
    );
}

int main(int argc, char *argv[])
{
    if (argc != 3) {
        fprintf(stderr,
                "Usage: %s <delay_ns> <trials>\n"
                "Example: %s 1000000 500\n",
                argv[0], argv[0]);
        return 1;
    }

    int64_t requested_ns = atoll(argv[1]);
    int trials = atoi(argv[2]);

    if (requested_ns <= 0 || trials <= 0) {
        fprintf(stderr, "Delay and trials must be positive.\n");
        return 1;
    }

    struct timespec requested;
    ns_to_timespec(requested_ns, &requested);

    /*
     * Store every timing error so that we can calculate
     * percentiles and standard deviation after the experiment.
     */
    int64_t *errors = malloc((size_t)trials * sizeof(int64_t));

    if (errors == NULL) {
        perror("malloc");
        return 1;
    }

    printf("trial,requested_ns,actual_ns,error_ns\n");

    for (int i = 1; i <= trials; i++) {

        struct timespec start, end;

        if (clock_gettime(CLOCK_MONOTONIC, &start) != 0) {
            perror("clock_gettime");
            free(errors);
            return 1;
        }

        int ret = clock_nanosleep(
            CLOCK_MONOTONIC,
            0,
            &requested,
            NULL
        );

        if (ret != 0) {
            fprintf(stderr,
                    "clock_nanosleep failed: %s\n",
                    strerror(ret));
            free(errors);
            return 1;
        }

        if (clock_gettime(CLOCK_MONOTONIC, &end) != 0) {
            perror("clock_gettime");
            free(errors);
            return 1;
        }

        int64_t start_ns = timespec_to_ns(&start);
        int64_t end_ns = timespec_to_ns(&end);

        int64_t actual_ns = end_ns - start_ns;
        int64_t error_ns = actual_ns - requested_ns;

        errors[i - 1] = error_ns;

        printf("%d,%lld,%lld,%lld\n",
               i,
               (long long)requested_ns,
               (long long)actual_ns,
               (long long)error_ns);
    }

    /*
     * Sort the errors for percentile calculations.
     */
    qsort(errors, (size_t)trials, sizeof(int64_t), compare_int64);

    int64_t min = errors[0];
    int64_t max = errors[trials - 1];

    long double sum = 0.0;

    for (int i = 0; i < trials; i++)
        sum += errors[i];

    long double mean = sum / trials;

    long double variance_sum = 0.0;

    for (int i = 0; i < trials; i++) {
        long double difference = errors[i] - mean;
        variance_sum += difference * difference;
    }

    long double standard_deviation =
        sqrtl(variance_sum / trials);

    int64_t p50 = percentile(errors, trials, 0.50);
    int64_t p90 = percentile(errors, trials, 0.90);
    int64_t p95 = percentile(errors, trials, 0.95);
    int64_t p99 = percentile(errors, trials, 0.99);

    fprintf(stderr, "\n");
    fprintf(stderr, "===== TIMER SUMMARY =====\n");
    fprintf(stderr, "Requested delay: %lld ns\n",
            (long long)requested_ns);
    fprintf(stderr, "Trials:          %d\n", trials);
    fprintf(stderr, "Mean error:      %.2Lf ns\n", mean);
    fprintf(stderr, "Median (p50):    %lld ns\n",
            (long long)p50);
    fprintf(stderr, "p90 error:       %lld ns\n",
            (long long)p90);
    fprintf(stderr, "p95 error:       %lld ns\n",
            (long long)p95);
    fprintf(stderr, "p99 error:       %lld ns\n",
            (long long)p99);
    fprintf(stderr, "Minimum error:   %lld ns\n",
            (long long)min);
    fprintf(stderr, "Maximum error:   %lld ns\n",
            (long long)max);
    fprintf(stderr, "Std deviation:   %.2Lf ns\n",
            standard_deviation);
    fprintf(stderr, "=========================\n");

    free(errors);

    return 0;
}