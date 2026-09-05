#!/bin/bash

set -u

PROJECT="$HOME/os-hrtimer-project"
BUILD="$PROJECT/build"
DATA="$PROJECT/data/final_wsl2"
LOGS="$PROJECT/data/final_wsl2/logs"

TRIALS=500

mkdir -p "$DATA" "$LOGS"

cleanup() {
    if [ -n "${LOAD_PID:-}" ]; then
        kill "$LOAD_PID" 2>/dev/null || true
        wait "$LOAD_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

echo "=========================================="
echo " FINAL HRTIMER EXPERIMENT - WSL2"
echo "=========================================="
echo "Logical CPUs: $(nproc)"
echo "Trials per condition: $TRIALS"
echo

run_condition() {
    local delay_ns="$1"
    local delay_name="$2"
    local load_name="$3"
    local workers="$4"

    local csv="$DATA/${delay_name}_${load_name}.csv"
    local log="$LOGS/${delay_name}_${load_name}.txt"

    echo
    echo "------------------------------------------"
    echo "Delay:   $delay_name"
    echo "Load:    $load_name"
    echo "Workers: $workers"
    echo "------------------------------------------"

    LOAD_PID=""

    if [ "$workers" -gt 0 ]; then
        echo "Starting CPU load..."

        if [ "$workers" -eq 6 ]; then
            taskset -c 1-6 "$BUILD/cpu_load" 6 90 > /dev/null 2>&1 &
        else
            taskset -c 1-11 "$BUILD/cpu_load" 11 90 > /dev/null 2>&1 &
        fi

        LOAD_PID=$!

        sleep 1
    fi

    echo "Running timer benchmark..."

    taskset -c 0 "$BUILD/timer_benchmark" \
        "$delay_ns" \
        "$TRIALS" \
        > "$csv" \
        2> "$log"

    if [ "$workers" -gt 0 ]; then
        kill "$LOAD_PID" 2>/dev/null || true
        wait "$LOAD_PID" 2>/dev/null || true
        LOAD_PID=""
    fi

    echo "Completed: $csv"

    grep -A 20 "TIMER SUMMARY" "$log" || true
}

echo "Starting experiment at:"
date

echo
echo "===== IDLE CONDITIONS ====="

run_condition 100000  "100us" "idle" 0
run_condition 1000000 "1ms"   "idle" 0
run_condition 10000000 "10ms" "idle" 0
run_condition 100000000 "100ms" "idle" 0

echo
echo "===== MODERATE LOAD CONDITIONS ====="

run_condition 100000  "100us" "moderate" 6
run_condition 1000000 "1ms"   "moderate" 6
run_condition 10000000 "10ms"  "moderate" 6
run_condition 100000000 "100ms" "moderate" 6

echo
echo "===== HEAVY LOAD CONDITIONS ====="

run_condition 100000  "100us" "heavy" 11
run_condition 1000000 "1ms"   "heavy" 11
run_condition 10000000 "10ms"  "heavy" 11
run_condition 100000000 "100ms" "heavy" 11

echo
echo "=========================================="
echo " EXPERIMENT COMPLETE"
echo "=========================================="
echo "Finished at:"
date
echo
echo "CSV files:"
ls -lh "$DATA"/*.csv
echo
echo "Summary files:"
ls -lh "$LOGS"/*.txt
