# WSL2 High-Resolution Timer Experiment

## Objective

Measure the timing error and jitter of Linux POSIX high-resolution timer
sleep operations under different requested delays and CPU-load conditions.

## Environment

Execution environment: WSL2
Logical CPUs: 12
Benchmark CPU: CPU 0

## Timer mechanism

The benchmark uses:

clock_nanosleep(CLOCK_MONOTONIC, ...)

The Linux kernel source was inspected to verify that this path is handled
through the high-resolution timer infrastructure.

## Requested delays

- 100 microseconds
- 1 millisecond
- 10 milliseconds
- 100 milliseconds

## CPU-load conditions

### Idle
0 CPU-load worker threads.

### Moderate
6 CPU-load worker threads pinned to CPUs 1-6.

### Heavy
11 CPU-load worker threads pinned to CPUs 1-11.

The benchmark itself is pinned to CPU 0.

## Trials

500 measurements were collected for every condition.

Total observations:

4 delays × 3 load levels × 500 trials = 6000 measurements.

## Measurement

For every trial:

1. Record start time using CLOCK_MONOTONIC.
2. Request the specified delay using clock_nanosleep().
3. Record end time using CLOCK_MONOTONIC.
4. Calculate actual elapsed time.
5. Calculate timing error.

Timing error:

error = actual elapsed time - requested delay

## Statistics

The experiment calculates:

- Mean
- Median (p50)
- p90
- p95
- p99
- Minimum
- Maximum
- Standard deviation

## Generated figures

- figure1_mean_error.png
- figure2_median_error.png
- figure3_p99_error.png
- figure4_max_error.png
- figure5_1ms_boxplot.png

## Important interpretation

The experiment measures observed userspace wake-up timing, not the
theoretical resolution of the hrtimer subsystem.

Therefore, observed timing error includes effects from:

- timer expiry
- scheduler latency
- CPU contention
- interrupt handling
- virtualization
- userspace execution delay

WSL2 results should therefore not be interpreted as a direct measurement
of bare-metal Linux real-time performance.
