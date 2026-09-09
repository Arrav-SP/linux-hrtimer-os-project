# Linux High-Resolution Timers (hrtimers) — OS Research Project

## Overview

This project studies Linux high-resolution timers from two angles:

1. **Kernel architecture:** how Linux represents, queues, expires, and dispatches high-resolution timers.
2. **Application behavior:** how accurately a userspace program resumes after requesting a delay, especially under CPU load.

The project combines Linux kernel-source analysis with controlled experiments on WSL2 and native Fedora Linux.

### Research question

> How does Linux high-resolution timer behavior vary with requested timer interval and CPU load, particularly in terms of latency, jitter, and tail behavior, and what does this reveal about Linux timer architecture and real-time OS design?

A central finding is:

> **High-resolution timer expiry is not the same thing as deterministic userspace execution.**

---

## 1. Current status

### Completed

- Linux hrtimer architecture investigation
- Linux source snapshot in `linux_source/`
- Userspace `clock_nanosleep()` benchmark
- CPU-load generator
- WSL2 experiment
- Native Fedora experiment
- 12 conditions per environment
- 500 trials per condition
- 6,000 observations per environment
- Raw CSV datasets and logs
- Statistical summaries
- WSL2 and native figures
- Fedora hardware/kernel/environment metadata
- Git history documenting project evolution

### Not yet completed

- Fair kernel-level `timer_list` vs `hrtimer` comparison
- Kernel module/instrumentation for that comparison
- Direct separation of timer-expiry latency from scheduler/wakeup latency
- Multiple independent repetitions of each condition
- Native experiment with CPU0's SMT sibling excluded from worker affinity
- Final synchronization of the report with native Fedora results
- Final presentation, if required
- Final LaTeX project, if required by the submission format
- Separate proposal artifact, if required

---

## 2. Repository structure

```text
linux-hrtimer-os-project/
├── README.md
├── MASTER_CONTEXT.md
├── src/
│   ├── timer_benchmark.c
│   ├── cpu_load.c
│   └── check_resolution.c
├── scripts/
│   ├── run_final_experiment.sh
│   ├── run_native_experiment.sh
│   ├── analyze_final.py
│   ├── analyze_native.py
│   └── plot_native.py
├── data/
│   ├── final_wsl2/
│   ├── native_*.csv
│   ├── native_*.txt
│   └── native_analysis/
├── linux_source/
└── report/
```

The repository itself should be treated as the source of truth for the current project state.

---

## 3. Experimental design

### Requested delays

- 100 µs
- 1 ms
- 10 ms
- 100 ms

### CPU-load conditions

- **Idle:** 0 workers
- **Moderate:** 6 CPU-bound workers
- **Heavy:** 11 CPU-bound workers

Each environment uses:

```text
4 delays × 3 load levels × 500 trials = 6,000 observations
```

There are therefore 12,000 observations across the two environments.

---

## 4. Userspace benchmark

The main benchmark is `src/timer_benchmark.c`.

It uses:

```c
clock_gettime(CLOCK_MONOTONIC, ...)
clock_nanosleep(CLOCK_MONOTONIC, ...)
```

The basic measurement is:

```text
timestamp_before
      ↓
clock_nanosleep()
      ↓
timestamp_after
```

The error is:

```text
error = actual elapsed time - requested delay
```

The benchmark does **not** directly timestamp the instant of hrtimer expiry. It measures application-visible elapsed time, so the result includes:

- userspace call overhead
- system-call entry/exit
- hrtimer setup and expiry
- interrupt handling
- task wake-up
- scheduler dispatch
- CPU contention
- return to userspace
- the second `clock_gettime()`
- virtualization effects under WSL2
- hardware/frequency/topology effects on Fedora

---

## 5. CPU-load generator

`src/cpu_load.c` creates CPU-bound worker threads.

The experiment uses:

```text
Benchmark:       CPU 0
Moderate load:   CPUs 1–6
Heavy load:      CPUs 1–11
```

This reduces direct competition on CPU0 but does not completely isolate it.

### Important Fedora topology caveat

The native Fedora machine has 12 logical CPUs on an Intel Core i5-1335U.

CPU0 and CPU1 are sibling hardware threads of the same P-core. Because CPU1 is included in both moderate and heavy worker sets, the benchmark is **not physically isolated** from the workers.

This must be treated as a methodology limitation.

---

## 6. Native Fedora environment

Recorded in:

```text
data/native_analysis/fedora_environment.txt
```

Key facts:

```text
OS:              Fedora 44
Kernel:          7.1.5-200.fc44.x86_64
Architecture:    x86_64
CPU:             Intel Core i5-1335U
Logical CPUs:    12
Physical cores:  10
Sockets:         1
Frequency range: 400 MHz – 4.6 GHz
Governor:        powersave
Kernel mode:     PREEMPT_DYNAMIC
```

Topology:

```text
CPU0 ─┐
      ├─ P-core 0
CPU1 ─┘

CPU2 ─┐
      ├─ P-core 1
CPU3 ─┘

CPU4–11 = E-cores
```

Possible timing-variation sources include sibling-thread contention, P-core/E-core behavior, frequency transitions, idle-state exit latency, cache/memory contention, interrupts, scheduler behavior, and background activity.

These are plausible mechanisms, not individually measured causes of particular outliers.

---

## 7. WSL2 results

All values are timing error in microseconds.

| Delay | Load | Mean | p50 | p95 | p99 | Max observed | Std. dev. |
|---|---|---:|---:|---:|---:|---:|---:|
| 100us | idle | 100.72 | 88.98 | 154.33 | 188.57 | 407.17 | 29.38 |
| 100us | moderate | 93.00 | 89.05 | 124.66 | 157.46 | 815.02 | 40.36 |
| 100us | heavy | 148.74 | 80.26 | 326.47 | 2,301.56 | 4,448.84 | 382.98 |
| 1ms | idle | 166.26 | 132.96 | 262.68 | 610.67 | 3,907.87 | 225.00 |
| 1ms | moderate | 126.17 | 108.90 | 217.78 | 413.62 | 1,180.58 | 78.84 |
| 1ms | heavy | 156.80 | 84.98 | 305.50 | 2,990.28 | 3,364.61 | 394.56 |
| 10ms | idle | 309.88 | 228.81 | 668.97 | 1,261.43 | 1,802.33 | 213.87 |
| 10ms | moderate | 156.03 | 124.06 | 247.10 | 641.16 | 5,030.66 | 268.25 |
| 10ms | heavy | 218.24 | 96.81 | 430.90 | 3,710.83 | 6,699.21 | 608.99 |
| 100ms | idle | 480.56 | 321.55 | 937.35 | 1,941.33 | 3,469.20 | 367.25 |
| 100ms | moderate | 146.55 | 123.16 | 226.04 | 411.40 | 2,516.63 | 140.35 |
| 100ms | heavy | 242.43 | 111.75 | 438.86 | 3,752.24 | 10,831.14 | 735.05 |

Important example:

```text
100 ms + heavy load
p50 = 111.75 µs
p99 = 3,752.24 µs
max = 10,831.14 µs
```

The maximum is a sample maximum, not a universal worst-case guarantee.

---

## 8. Native Fedora results

All values are timing error in microseconds.

| Delay | Load | Mean | p50 | p95 | p99 | Max observed | Std. dev. |
|---|---|---:|---:|---:|---:|---:|---:|
| 100us | idle | 69.30 | 56.29 | 63.66 | 192.07 | 2,892.60 | 156.65 |
| 100us | moderate | 53.35 | 53.75 | 54.54 | 55.15 | 57.30 | 2.79 |
| 100us | heavy | 61.58 | 53.79 | 60.01 | 139.29 | 2,156.31 | 101.01 |
| 1ms | idle | 121.31 | 86.69 | 228.42 | 298.73 | 2,386.84 | 119.50 |
| 1ms | moderate | 57.58 | 55.70 | 57.65 | 69.70 | 997.21 | 43.67 |
| 1ms | heavy | 134.41 | 56.25 | 350.02 | 2,472.00 | 6,184.18 | 441.15 |
| 10ms | idle | 147.04 | 93.03 | 270.08 | 1,164.40 | 2,170.89 | 181.27 |
| 10ms | moderate | 60.82 | 59.85 | 69.95 | 99.16 | 271.56 | 13.61 |
| 10ms | heavy | 193.16 | 61.11 | 689.83 | 1,944.69 | 8,721.30 | 557.49 |
| 100ms | idle | 142.48 | 100.92 | 248.49 | 592.12 | 1,745.45 | 131.25 |
| 100ms | moderate | 64.18 | 59.40 | 63.92 | 159.19 | 833.62 | 53.10 |
| 100ms | heavy | 237.63 | 61.52 | 870.03 | 1,993.82 | 33,323.73 | 1,575.31 |

The strongest native tail example is:

```text
100 ms + heavy load
p50 = 61.52 µs
p99 = 1,993.82 µs
max = 33,323.73 µs
```

Other notable heavy-load tails:

```text
1 ms:  p99 = 2.472 ms, max = 6.184 ms
10 ms: p99 = 1.945 ms, max = 8.721 ms
```

The data show why median and tail statistics must be considered together.

---

## 9. Statistical analysis

The project calculates:

- Mean
- Median / p50
- p90
- p95
- p99
- Minimum
- Maximum
- Population standard deviation

Percentiles use linear interpolation at:

```text
p × (n - 1)
```

Population standard deviation corresponds to Python's:

```python
statistics.pstdev(...)
```

Interpretation:

- **Mean:** average error; sensitive to outliers.
- **Median/p50:** typical observation; less sensitive to extreme samples.
- **p90/p95:** common upper-tail behavior.
- **p99:** rare-delay behavior while being less dominated by one sample than maximum.
- **Maximum:** largest observed sample, not a formal worst-case bound.
- **Standard deviation:** dispersion/jitter within the observed samples.

The raw CSVs and summary files were cross-checked. Each environment has 12 CSVs with 500 trials each, and the reported means, maxima, and standard deviations agree with the raw data.

---

## 10. Linux kernel timer path

The investigated path is:

```text
clock_nanosleep()
        ↓
POSIX timer implementation
        ↓
common_nsleep_timens()
        ↓
hrtimer_nanosleep()
        ↓
hrtimer sleeper setup
        ↓
hrtimer start / queue insertion
        ↓
timerqueue / rb-tree ordering
        ↓
clock-event programming
        ↓
timer interrupt
        ↓
expired hrtimer processing
        ↓
task wake-up
        ↓
scheduler dispatch
        ↓
return to userspace
        ↓
clock_gettime()
```

Relevant source areas include:

```text
linux_source/kernel/time/posix-timers.c
linux_source/kernel/time/hrtimer.c
linux_source/kernel/time/clockevents.c
linux_source/kernel/time/clocksource.c
linux_source/kernel/time/timekeeping.c
linux_source/kernel/time/timer.c
linux_source/kernel/time/jiffies.c
linux_source/lib/timerqueue.c
linux_source/include/linux/timerqueue.h
```

The checked-in source is a Linux 7.3-rc1 snapshot.

### hrtimer organization

The investigation covers:

```text
struct hrtimer
struct hrtimer_clock_base
struct hrtimer_cpu_base
timerqueue
rb-tree ordering
```

The timerqueue is ordered so the earliest timer can be found efficiently.

The complete `include/linux/hrtimer.h` structure definitions are not present in the checked-in source, so exact field layouts are not claimed as repository-verified.

### Clocksource vs clock-event

A clocksource answers:

> What time is it now?

A clock-event device answers:

> When should the CPU receive the next timer event?

This distinction is important because `clock_gettime()` timestamps do not directly reveal the hardware timer-expiry instant.

---

## 11. hrtimers vs traditional timers

Traditional `timer_list` timers use jiffies-based timing and timer-wheel-style management for ordinary timeouts.

Hrtimers provide finer-grained time representation and ordered expiry management through timerqueue/rb-tree structures and programmable clock-event deadlines.

Conceptually:

```text
timer_list
   ↓
jiffies
   ↓
timer-wheel style management

hrtimer
   ↓
high-resolution time
   ↓
ordered timerqueue
   ↓
clock-event deadline
```

Higher timer resolution does not automatically provide deterministic application scheduling.

---

## 12. What the experiments demonstrate

The current evidence supports these conclusions:

1. Hrtimer-backed sleeps can achieve relatively small typical timing errors.
2. Userspace wake-up is not deterministic.
3. Median latency can look good while p99 and maximum latency are much worse.
4. CPU-load effects are not necessarily monotonic in the median.
5. Heavy load generally broadens the upper tail.
6. Native Fedora and WSL2 produce different timing distributions.
7. High-resolution timer expiry is not equivalent to immediate userspace execution.
8. The general-purpose scheduler and CPU/system state remain part of the observed result.

The experiment does **not** establish:

- a hard real-time guarantee
- a universal Linux timing bound
- pure hrtimer expiry accuracy
- that virtualization alone caused a specific outlier
- that native Linux is universally more accurate than WSL2
- that `timer_list` is slower or less accurate than hrtimers

---

## 13. WSL2 vs native Fedora

Native runs generally show lower typical errors than WSL2 in many conditions, but this is not a controlled virtualization-only experiment.

The systems differ in:

- hardware
- kernel version
- CPU topology
- frequency behavior
- governor
- host scheduling
- background activity
- system state
- experiment order

Therefore the defensible conclusion is:

> The native run produced lower typical errors in many conditions than the WSL2 run, while both environments exhibited substantial tail latency.

It would be too strong to conclude that native Linux is universally more accurate than WSL2.

---

## 14. Major missing experiment: timer_list vs hrtimer

The original project direction includes a comparison between jiffies/timer-wheel based `timer_list` timers and hrtimers.

That comparison has **not** been implemented.

There is currently:

- no kernel module for the comparison
- no `timer_list` benchmark
- no kernel callback timestamp comparison
- no timer-wheel vs hrtimer dataset
- no fair mechanism-level latency comparison

Using `usleep()` as a supposed jiffies implementation would not be technically valid.

A proper comparison should instrument both timer mechanisms at kernel level and measure timestamps such as:

```text
timer insertion
    ↓
intended expiry
    ↓
callback entry
    ↓
wake-up
    ↓
userspace return
```

---

## 15. Known documentation/reproduction issues

The repository audit found that some older documentation predates the native experiment.

In particular:

- `report/final_report.md` currently focuses on WSL2 and does not integrate the native Fedora results.
- Older report text says native data are absent even though they now exist.
- Older documentation says the Linux source tree is absent even though `linux_source/` is now present.
- `part3_progress_report.md` predates the native experiment.
- The native runner writes to `data/final_native/`, while the committed native dataset is stored as `data/native_*.csv`.
- The native analyzer still uses the output filename `wsl2_summary.csv`.
- The native runner should be made independent of a hard-coded project path and should fail fast on errors.
- Four legacy `data/*_idle.csv` files contain 100 trials and should not be silently mixed into the current 500-trial analysis.
- The repository currently contains the Markdown report rather than a complete LaTeX source project.
- No presentation artifact is currently present.

These are documentation/reproducibility issues, not evidence that the completed datasets are invalid.

---

## 16. Recommended Part 4 plan

### 1. Synchronize documentation

Update the README, master context, and report so they describe the current repository and native results.

### 2. Repair native reproduction

Make the native runner, analyzer, and plotter agree on:

- project location
- output directory
- filename convention
- summary filename
- error handling

### 3. Improve CPU isolation

Repeat native experiments with CPU1 excluded from the worker set because CPU1 is CPU0's SMT sibling.

### 4. Repeat experiments

Run multiple independent batches to distinguish repeatable effects from one-off system-state events.

### 5. Implement kernel-level comparison

Build a controlled `timer_list` vs `hrtimer` kernel experiment.

### 6. Add tracing

Use tools such as:

```text
ftrace
perf
rtla timerlat
```

where appropriate to separate:

```text
timer expiry
interrupt handling
wake-up latency
scheduler latency
userspace return latency
```

### 7. Record additional environment data

Where possible record:

- clocksource
- clock-event device
- CPU frequency
- idle-state information
- scheduler policy
- kernel configuration
- relevant preemption configuration

---

## 17. Reproducibility

### Build

```bash
mkdir -p build

gcc -O2 -Wall -Wextra -pthread src/timer_benchmark.c     -o build/timer_benchmark -lm

gcc -O2 -Wall -Wextra -pthread src/cpu_load.c     -o build/cpu_load
```

### WSL2

```bash
bash scripts/run_final_experiment.sh
python3 scripts/analyze_final.py
python3 scripts/plot_final.py
```

### Native Fedora

```bash
bash scripts/run_native_experiment.sh
python3 scripts/analyze_native.py
python3 scripts/plot_native.py
```

The completed native dataset can be analyzed without rerunning the experiment. Before claiming fully automated native reproduction, fix the path/output inconsistencies described above.

---

## 18. Data layout

Native raw files:

```text
data/native_100us_idle.csv
data/native_100us_moderate.csv
data/native_100us_heavy.csv
data/native_1ms_idle.csv
data/native_1ms_moderate.csv
data/native_1ms_heavy.csv
data/native_10ms_idle.csv
data/native_10ms_moderate.csv
data/native_10ms_heavy.csv
data/native_100ms_idle.csv
data/native_100ms_moderate.csv
data/native_100ms_heavy.csv
```

Each has 500 trial rows plus a header.

Native summary:

```text
data/native_analysis/analysis/native_summary.csv
```

Native figures:

```text
data/native_analysis/figures/
```

WSL2 summary:

```text
data/final_wsl2/analysis/wsl2_summary.csv
```

---

## 19. Research-paper status

The current report is:

```text
report/final_report.md
```

Its structure includes:

- Abstract
- Introduction
- Background/literature
- Linux timer architecture
- hrtimer implementation analysis
- Hypotheses
- Methodology
- Results
- Discussion
- Limitations
- Future work
- Conclusion
- References
- Appendices

However, the report is stale relative to the repository because it predates the native Fedora experiment.

Before final submission, it should:

1. Integrate the native Fedora results.
2. Update the figures and tables.
3. Correct statements about missing native data/source files.
4. Reconcile the methodology with the actual Fedora CPU topology.
5. Clearly label sample maxima as observed maxima rather than worst-case bounds.
6. Explain that WSL2 vs native is an observational comparison, not a controlled virtualization experiment.
7. Add the kernel-level timer comparison if it becomes part of the final scope.

---

## 20. Research contribution and positioning

The general idea that Linux high-resolution timers provide precise expiry but do not guarantee deterministic userspace execution is not, by itself, a novel claim.

The stronger contribution of this project is the combined characterization across:

- four requested timer intervals
- three CPU-load conditions
- WSL2
- native Fedora
- percentile/tail analysis
- raw experimental data
- Linux kernel-source analysis

The final paper should frame this as an empirical systems characterization and kernel/application timing analysis rather than claiming to have invented the underlying hrtimer mechanisms.

---

## 21. Git history

Important commits:

```text
5d22d14
Initial benchmark, WSL2 experiment, scripts, datasets, and figures

d0ce47c
Add master project context

289cb8d
Add progress reports and Linux source files

1ef77a7
Add native Fedora hrtimer experiment results

736c08a
Record native Fedora experiment environment
```

The native work was added after the original WSL2/reporting stage, which explains why older documents are now out of date.

---

## 22. Security

Never commit:

- GitHub personal access tokens
- passwords
- API keys
- SSH private keys
- other credentials

A credential was accidentally present in shell history during the Fedora workflow. It should be revoked if that has not already been done.

Revoking a token affects authentication; it does not remove already-pushed commits or research data.

---

## 23. Final project map

```text
COMPLETED
├── Linux hrtimer architecture investigation
├── Linux source snapshot
├── clock_nanosleep userspace benchmark
├── CPU-load generator
├── WSL2 experiment
│   └── 6,000 observations
├── Native Fedora experiment
│   └── 6,000 observations
├── Statistical summaries
├── WSL2 figures
├── Native Fedora figures
├── Fedora hardware/kernel metadata
└── Git history

IN PROGRESS
├── Documentation synchronization
├── Native results integration into final paper
└── Native reproduction workflow cleanup

NOT YET DONE
├── Kernel-level timer_list vs hrtimer comparison
├── Kernel module/instrumentation
├── Direct jiffies vs hrtimer measurements
├── Expiry vs scheduler-latency tracing
├── Multiple independent experiment repetitions
├── Better native CPU isolation
├── Final presentation
└── Final LaTeX/proposal artifacts if required

NEXT BEST STEPS
1. Synchronize documentation.
2. Fix native reproduction scripts.
3. Repeat native tests with CPU1 excluded.
4. Repeat conditions across multiple runs.
5. Implement kernel-level timer_list/hrtimer comparison.
6. Add tracing to separate expiry, wake-up, scheduling, and userspace latency.
7. Integrate all validated results into the final paper.
8. Prepare the final presentation.
```

---

## 24. Final takeaway

**Linux high-resolution timers provide fine-grained timer infrastructure, but high-resolution expiry does not guarantee deterministic application-level wake-up.**

The experiments make this visible: typical timing can be close to the requested delay while rare tail events reach the millisecond range or beyond. The kernel architecture explains why: timer expiry is only one stage in a larger chain involving clock events, interrupts, wake-up, scheduling, CPU availability, and userspace execution.
