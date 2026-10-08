/*
 * slackexec: set the calling thread's timer slack, then exec a command.
 * Timer slack is inherited across fork/exec, so the unmodified
 * timer_benchmark can be run with a different slack value.
 *
 * Usage: slackexec <slack_ns> <command> [args...]
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/prctl.h>

int main(int argc, char *argv[])
{
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <slack_ns> <command> [args...]\n", argv[0]);
        return 1;
    }

    if (prctl(PR_SET_TIMERSLACK, strtoul(argv[1], NULL, 10), 0, 0, 0) != 0) {
        perror("prctl(PR_SET_TIMERSLACK)");
        return 1;
    }

    execvp(argv[2], &argv[2]);
    perror("execvp");
    return 1;
}
