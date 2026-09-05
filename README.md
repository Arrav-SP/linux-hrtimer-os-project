# High-Resolution Timers (hrtimers) in Linux

## OS Project Case Study

This project investigates the behavior of Linux high-resolution timers
(hrtimers) through kernel-source analysis and experimental benchmarking.

The project focuses on the relationship between requested timer delays,
observed userspace wake-up latency, CPU load, and timing jitter.

## Research Question

How precisely can Linux high-resolution POSIX timer facilities meet
requested delays under different delay magnitudes and CPU-load conditions,
and what do the resulting latency and jitter patterns reveal about the
operating-system timer design?

## Project Components

### 1. Kernel Source Analysis

The Linux kernel source was studied, particularly:

- kernel/time/hrtimer.c
- kernel/time/timer.c
- kernel/time/jiffies.c
- kernel/time/timerqueue.c

The analysis focuses on the difference between traditional tick/jiffies
timers and the high-resolution timer infrastructure.

### 2. Userspace Benchmark

The benchmark uses:

clock_nanosleep(CLOCK_MONOTONIC, ...)

The program measures elapsed time using CLOCK_MONOTONIC and calculates:

timing error = actual elapsed time - requested delay

### 3. CPU Load Generator

A custom C program generates controlled CPU load using worker threads.

Three experimental conditions were used:

- Idle: 0 workers
- Moderate: 6 workers
- Heavy: 11 workers

The benchmark was pinned to CPU 0 while load workers were pinned to
other CPUs.

### 4. Experimental Conditions

Requested delays:

- 100 microseconds
- 1 millisecond
- 10 milliseconds
- 100 milliseconds

Each condition contains 500 trials.

Total observations:

4 delays × 3 load levels × 500 trials = 6000 observations.

## Environment

The primary experimental environment is Linux running under WSL2.

Native Linux testing was planned but was not available during the current
experimental phase. Therefore, the reported measurements characterize
timer behavior as observed from Linux userspace under WSL2 rather than
bare-metal real-time Linux.

## Measurements

For each condition the following statistics are calculated:

- Mean timing error
- Median (p50)
- p90
- p95
- p99
- Minimum
- Maximum
- Standard deviation

## Figures

The project automatically generates:

1. Mean timing error with standard-deviation error bars
2. Median timing error
3. 99th-percentile timing error
4. Maximum observed timing error
5. 1-ms timing-error boxplot

## Important Interpretation

The benchmark measures observed userspace wake-up timing.

It does not directly measure the theoretical resolution of the hrtimer
implementation.

Observed timing error can include effects from timer expiration,
interrupt handling, scheduler latency, CPU contention, virtualization,
and userspace execution.

Therefore, the results should not be interpreted as a guarantee of
nanosecond-level application execution accuracy.

## Project Status

Kernel analysis: completed

Userspace benchmark: completed

CPU-load generator: completed

Automated experiment: completed

WSL2 dataset: completed

Statistical analysis: completed

Graph generation: completed

Native Linux comparison: not currently available

Kernel-level timer_list versus hrtimer experiment: planned/optional
extension
