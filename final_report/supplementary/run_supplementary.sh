#!/bin/bash
# Supplementary control experiment (run as root so that chrt can set SCHED_FIFO).
# Same benchmark source, same pinning and load generator as the main experiment;
# the only things varied are the timer slack and the scheduling policy.
#
# Usage: sudo bash run_supplementary.sh <repo_root> <output_dir>

set -eu

REPO="$1"
OUT="$2"
BUILD="$OUT/build"
TRIALS=500

mkdir -p "$BUILD" "$OUT/data"

gcc -O2 -Wall -Wextra -pthread "$REPO/src/timer_benchmark.c" -o "$BUILD/timer_benchmark" -lm
gcc -O2 -Wall -Wextra -pthread "$REPO/src/cpu_load.c" -o "$BUILD/cpu_load"
gcc -O2 -Wall -Wextra "$REPO/src/check_resolution.c" -o "$BUILD/check_resolution"
gcc -O2 -Wall -Wextra "$REPO/final_report/supplementary/slackexec.c" -o "$BUILD/slackexec"

{
    echo "=== DATE ==="; date
    echo "=== KERNEL ==="; uname -a
    echo "=== OS ==="; grep PRETTY_NAME /etc/os-release
    echo "=== CPU ==="; lscpu | grep -E "Model name|^CPU\(s\)|Thread|Core|Hypervisor"
    echo "=== TOPOLOGY ==="; lscpu -e=CPU,CORE 2>/dev/null || true
    echo "=== CLOCK RESOLUTION ==="; "$BUILD/check_resolution"
    echo "=== DEFAULT TIMER SLACK (ns) ==="; cat /proc/self/timerslack_ns
    echo "=== CLOCKSOURCE ==="; cat /sys/devices/system/clocksource/clocksource0/current_clocksource
    echo "=== CLOCKEVENT (cpu0) ==="; cat /sys/devices/system/clockevents/clockevent0/current_device 2>/dev/null || true
    echo "=== KERNEL CONFIG ==="; zcat /proc/config.gz 2>/dev/null | grep -E "^CONFIG_(HZ|HZ_[0-9]+|NO_HZ[A-Z_]*|HIGH_RES_TIMERS|PREEMPT[A-Z_]*)=" || echo "not available"
    echo "=== GCC ==="; gcc --version | head -1
} > "$OUT/environment.txt" 2>&1

LOAD_PID=""

stop_load() {
    if [ -n "$LOAD_PID" ]; then
        kill "$LOAD_PID" 2>/dev/null || true
        wait "$LOAD_PID" 2>/dev/null || true
        LOAD_PID=""
    fi
}

trap stop_load EXIT INT TERM

run() {
    local variant="$1" delay_ns="$2" delay_name="$3" load="$4"
    local csv="$OUT/data/${variant}_${delay_name}_${load}.csv"
    local log="$OUT/data/${variant}_${delay_name}_${load}.txt"

    if [ "$load" = "heavy" ]; then
        taskset -c 1-11 "$BUILD/cpu_load" 11 90 > /dev/null 2>&1 &
        LOAD_PID=$!
        sleep 1
    fi

    case "$variant" in
        default) taskset -c 0 "$BUILD/timer_benchmark" "$delay_ns" "$TRIALS" > "$csv" 2> "$log" ;;
        slack1)  taskset -c 0 "$BUILD/slackexec" 1 "$BUILD/timer_benchmark" "$delay_ns" "$TRIALS" > "$csv" 2> "$log" ;;
        fifo)    taskset -c 0 chrt -f 80 "$BUILD/timer_benchmark" "$delay_ns" "$TRIALS" > "$csv" 2> "$log" ;;
    esac

    stop_load
    echo "done: $variant $delay_name $load"
}

# Variants are interleaved within each delay/load cell so that slow drift in
# the host state affects all three variants similarly.
for load in idle heavy; do
    for spec in "100000 100us" "1000000 1ms" "10000000 10ms"; do
        set -- $spec
        for variant in default slack1 fifo; do
            run "$variant" "$1" "$2" "$load"
        done
    done
done
