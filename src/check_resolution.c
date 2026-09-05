#include <stdio.h>
#include <time.h>

int main(void)
{
    struct timespec res;

    if (clock_getres(CLOCK_MONOTONIC, &res) != 0) {
        perror("clock_getres");
        return 1;
    }

    printf("CLOCK_MONOTONIC resolution: %ld ns\n",
           res.tv_sec * 1000000000L + res.tv_nsec);

    return 0;
}
