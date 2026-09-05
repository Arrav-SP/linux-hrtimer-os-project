# MASTER_CONTEXT.md

# Linux High-Resolution Timers (hrtimers) --- OS Project Master Context

## 1. Project Identity

**Project topic:** High-Resolution Timers (hrtimers)

**Case-study wording:** \> High-Resolution Timers (hrtimers) --- Case:
Linux introduced hrtimers for precise scheduling in real-time systems.
Focus: Kernel time management. Workflow: Study kernel implementation
(`kernel/time/hrtimer.c`). Write a test program using POSIX high-res
timers. Compare timer precision with jiffies-based timers. Reflect on OS
design trade-offs for real-time constraints.

**Primary project goal:** Study Linux kernel time management, understand
why hrtimers were introduced, inspect the implementation, build a real
userspace timing benchmark, measure precision/jitter under different
workloads, and critically analyze the OS design trade-offs.

**Current execution environment:** WSL2 Ubuntu.

**Important limitation:** A native/bare-metal Linux experiment has NOT
been completed yet. Do not invent native Linux results. The current
experimental dataset is WSL2 data and must be labeled accordingly.

------------------------------------------------------------------------

## 2. Official Project Requirements

The project guidelines require:

### Phase 2 --- Proposal

1--3 page proposal containing: - Background - Research/implementation
question - Methodology

### Phase 3 --- Mid-term progress

-   Progress report
-   At least one completed analysis/simulation

### Phase 4 --- Final report

10--15 page report containing: 1. Abstract 2. Literature
survey/background 3. Methodology 4. Results 5. Discussion/critical
analysis 6. Conclusion 7. References

Also required: - 10-minute presentation - At least two research papers

### Rubric

-   Depth of Analysis / Critical Thinking: 40%
-   Implementation / Simulation: 30%
-   Originality / Problem-Solving: 20%
-   Report & Presentation Quality: 10%

The project should therefore demonstrate real
implementation/measurement, kernel-level understanding, and critical
analysis rather than only explaining what hrtimers are.

------------------------------------------------------------------------

## 3. Research Question

Current research question:

> How precisely can Linux's high-resolution POSIX timer facilities
> (backed by hrtimers) meet requested delays across varying delay
> magnitudes, system load conditions, and execution environments, and
> what do the resulting error and jitter patterns reveal about the OS
> design trade-offs that motivated the hrtimer subsystem?

Because native Linux is currently unavailable, the immediate report
should focus on the completed WSL2 experiment while explicitly treating
native Linux comparison as future work / limitation.

------------------------------------------------------------------------

## 4. Objectives

1.  Measure timing error and jitter of high-resolution POSIX timer
    facilities.
2.  Test multiple requested delay magnitudes.
3.  Test idle, moderate-load, and heavy-load conditions.
4.  Understand how scheduling/load affects observed wake-up latency.
5.  Connect userspace observations to the Linux hrtimer implementation.
6.  Determine whether a technically fair jiffies-vs-hrtimer comparison
    is possible.
7.  Avoid making technically invalid comparisons between unrelated
    userspace APIs.
8.  Analyze the trade-off between timer precision, scheduling latency,
    overhead, and system behavior.

------------------------------------------------------------------------

## 5. Key Conceptual Background

### 5.1 What is an OS timer?

An operating-system timer is a mechanism that allows the OS to arrange
for something to happen at or after a specified time.

Examples: - wake a sleeping process - run a kernel timer callback -
expire a timeout - schedule periodic activity

### 5.2 Jiffies and periodic timer ticks

Traditional Linux timing was strongly connected to periodic timer ticks.

-   `HZ` = number of timer ticks per second.
-   `jiffies` = kernel tick counter.
-   Tick period = approximately `1 / HZ`.

Example: - HZ = 250 - one tick = 4 ms

A tick-based mechanism is therefore naturally coarse compared with
sub-millisecond timing requirements.

### 5.3 Timer wheel

Linux traditionally used a timer-wheel-based mechanism for many ordinary
kernel timers.

The timer wheel is efficient for large numbers of ordinary timeouts, but
its design is not ideal for all high-precision real-time use cases.

A major motivation for hrtimers was to avoid forcing high-resolution
event scheduling through the coarse tick/timer-wheel mechanism.

### 5.4 hrtimers

Linux hrtimers provide a separate high-resolution timer infrastructure.

Important properties: - time is represented with nanosecond-scale
units - timers are maintained in time order - hrtimers use
timerqueue/red-black-tree based ordering - timers are organized per
CPU - hrtimers coexist with the ordinary timer-wheel infrastructure -
high-resolution operation relies on suitable clocksource and clock-event
hardware/infrastructure

### 5.5 Resolution is not the same as accuracy

This distinction is essential.

-   **Resolution:** how finely time can be represented/requested.
-   **Accuracy:** how close the actual event is to the requested time.
-   **Latency:** how long execution is delayed before the task actually
    runs.
-   **Jitter:** variation in latency/error from one observation to
    another.

A timer can support very fine-grained requested times without
guaranteeing that a userspace process will execute exactly at that time.

The scheduler, interrupts, CPU contention, virtualization, host
scheduling, and other system effects can introduce additional delay.

------------------------------------------------------------------------

## 6. Important Architecture Concepts

### Clocksource

Answers approximately: \> "What time is it?"

It provides a way to measure current time.

### Clock-event device

Answers approximately: \> "When should the CPU receive the next timer
event?"

It provides programmable timer events/interrupts.

### hrtimer

Uses these timing facilities to schedule high-resolution timer
expirations.

This distinction should appear in the report because it demonstrates
actual understanding of Linux kernel time architecture.

------------------------------------------------------------------------

## 7. Kernel Source Investigation

Linux source repository cloned for study:

`linux/`

Relevant file:

`kernel/time/hrtimer.c`

Other important files: - `kernel/time/timerqueue.c` -
`kernel/time/jiffies.c` - `kernel/time/timer.c` -
`kernel/time/clockevents.c` - `kernel/time/clocksource.c` -
`kernel/time/tick-common.c` - `kernel/time/tick-sched.c`

Important symbols investigated in `hrtimer.c`: - `hrtimer_setup` -
`enqueue_hrtimer` - `__run_hrtimer` - `hrtimer_interrupt` -
`hrtimer_start_range_ns`

Conceptual hrtimer lifecycle:

1.  Initialize timer
2.  Set expiry time
3.  Insert/enqueue timer into the ordered timer structure
4.  Clock-event mechanism produces timer interrupt/event
5.  hrtimer interrupt handler processes expired timers
6.  Expired callbacks are executed
7.  Timer may be restarted for periodic behavior

Do not claim that userspace directly calls `hrtimer_start()`; the
userspace POSIX APIs go through kernel timer infrastructure that
ultimately uses hrtimers.

------------------------------------------------------------------------

## 8. Userspace Experiment

### Primary API

The benchmark uses:

`clock_nanosleep(CLOCK_MONOTONIC, ...)`

The project investigation verified that modern Linux routes this sleep
path through hrtimer-based kernel code (`hrtimer_nanosleep()` in the
relevant POSIX timer implementation).

This means the benchmark is a reasonable way to study hrtimer-backed
high-resolution sleeping from userspace.

### Measurement clock

The benchmark measures elapsed time using:

`clock_gettime(CLOCK_MONOTONIC, ...)`

This avoids wall-clock adjustments and is appropriate for measuring
elapsed intervals.

### Error definition

For each trial:

`error = actual_elapsed_time - requested_delay`

All raw results are stored in nanoseconds.

For plots and summaries, errors are converted to microseconds.

------------------------------------------------------------------------

## 9. Benchmark Program

File:

`src/timer_benchmark.c`

The program: - accepts requested delay in nanoseconds - accepts number
of trials - measures start/end using `CLOCK_MONOTONIC` - calls
`clock_nanosleep` - calculates actual elapsed time - calculates timing
error - writes CSV output - computes: - mean - median / p50 - p90 -
p95 - p99 - minimum - maximum - standard deviation

Compilation:

``` bash
gcc -O2 -Wall -Wextra -pthread src/timer_benchmark.c -o build/timer_benchmark -lm
```

------------------------------------------------------------------------

## 10. CPU Load Generator

File:

`src/cpu_load.c`

The program: - creates configurable numbers of CPU-intensive worker
threads - runs for a specified duration - uses a dependency-free busy
loop - handles SIGINT - reports available logical CPUs

Compilation:

``` bash
gcc -O2 -Wall -Wextra -pthread src/cpu_load.c -o build/cpu_load
```

The WSL2 environment reports:

`nproc = 12`

Load conditions used:

### Idle

0 load workers

### Moderate

6 load workers

### Heavy

11 load workers

The benchmark was pinned to CPU 0.

Load workers were pinned to: - moderate: CPUs 1--6 - heavy: CPUs 1--11

This leaves the benchmark CPU separate from the load-generator CPUs as
much as possible inside the WSL2 environment.

------------------------------------------------------------------------

## 11. Final WSL2 Experiment Protocol

This is the completed WSL2 dataset.

### Requested delays

-   100 microseconds
-   1 millisecond
-   10 milliseconds
-   100 milliseconds

### Load states

-   Idle
-   Moderate
-   Heavy

### Trials

500 trials per condition.

Total:

`4 delays × 3 load states × 500 trials = 6000 observations`

There are 12 CSV files.

Each CSV contains: - 1 header line - 500 trial lines

Total lines across the 12 CSV files:

6000 observations + 12 headers = 6012 lines.

### Conditions

  Delay    Idle   Moderate   Heavy
  -------- ------ ---------- -------
  100 us   500    500        500
  1 ms     500    500        500
  10 ms    500    500        500
  100 ms   500    500        500

------------------------------------------------------------------------

## 12. WSL2 Results

All errors below are timing error relative to the requested delay.

Units in this table are microseconds.

  Delay    Load           Mean   Median/p50      p95       p99        Max
  -------- ---------- -------- ------------ -------- --------- ----------
  100 us   Idle         100.72        88.98   154.33    188.57     407.17
  100 us   Moderate      93.00        89.05   124.66    157.46     815.02
  100 us   Heavy        148.74        80.26   326.47   2301.56    4448.84
  1 ms     Idle         166.26       132.96   262.68    610.67    3907.87
  1 ms     Moderate     126.17       108.90   217.78    413.62    1180.58
  1 ms     Heavy        156.80        84.98   305.50   2990.28    3364.61
  10 ms    Idle         309.88       228.81   668.97   1261.43    1802.33
  10 ms    Moderate     156.03       124.06   247.10    641.16    5030.66
  10 ms    Heavy        218.24        96.81   430.90   3710.83    6699.21
  100 ms   Idle         480.56       321.55   937.35   1941.33    3469.20
  100 ms   Moderate     146.55       123.16   226.04    411.40    2516.63
  100 ms   Heavy        242.43       111.75   438.86   3752.24   10831.14

### Standard deviations

  Delay    Load         Std. deviation
  -------- ---------- ----------------
  100 us   Idle               29.38 us
  100 us   Moderate           40.36 us
  100 us   Heavy             382.98 us
  1 ms     Idle              225.00 us
  1 ms     Moderate           78.84 us
  1 ms     Heavy             394.56 us
  10 ms    Idle              213.87 us
  10 ms    Moderate          268.25 us
  10 ms    Heavy             608.99 us
  100 ms   Idle              367.25 us
  100 ms   Moderate          140.35 us
  100 ms   Heavy             735.05 us

------------------------------------------------------------------------

## 13. Main Observations From WSL2

### Observation 1 --- Typical timing error is much smaller than the requested delay

Median errors are generally in the tens-to-hundreds of microseconds.

Example: - 1 ms idle median ≈ 132.96 us - 10 ms idle median ≈ 228.81
us - 100 ms idle median ≈ 321.55 us

This shows that the requested delay can be relatively large while the
additional wake-up error remains comparatively small.

### Observation 2 --- Heavy load strongly affects the tail

Heavy CPU load does not always increase the median. However, it often
produces much larger p99 and maximum errors.

The clearest example:

100 ms heavy: - median ≈ 111.75 us - p99 ≈ 3.75 ms - maximum ≈ 10.83 ms

This demonstrates why mean/median alone are insufficient for timing
analysis.

### Observation 3 --- Worst-case behavior is more sensitive than typical behavior

Heavy load can produce occasional long delays even when the median
remains small.

This is an important real-time systems observation: - average behavior
can look good - tail latency can still be problematic

### Observation 4 --- Results are not monotonically ordered by load

Moderate load sometimes has lower mean/median than idle.

This must NOT be hidden or "fixed."

Possible interpretation: - WSL2 scheduling behavior is complex - CPU
placement and virtualization influence measurements - host scheduling
and Linux guest scheduling interact - the busy-loop load is not a
perfect real-time stress model

Therefore, the correct conclusion is not "more load always means more
average error."

The stronger conclusion is: \> Increasing contention is associated with
substantially worse tail behavior in several conditions, while typical
latency does not change monotonically.

### Observation 5 --- Requested delay magnitude matters

Idle mean error rises from roughly: - 100.72 us at 100 us requested -
166.26 us at 1 ms - 309.88 us at 10 ms - 480.56 us at 100 ms

However, this should not be interpreted as hrtimer precision degrading
linearly with delay. The measured quantity includes userspace
wake-up/scheduling effects, not just timer expiry precision.

------------------------------------------------------------------------

## 14. Critical Interpretation

The experiment does NOT prove:

> "hrtimers are accurate to X microseconds."

That would be too strong.

It measures the end-to-end behavior of:

userspace request → kernel timer mechanism → timer expiry →
scheduler/wake-up → userspace resumes → measurement

Therefore, the observed error contains more than timer hardware/software
precision.

A better statement is:

> The WSL2 experiment characterizes the end-to-end wake-up error
> observed by a userspace process using a high-resolution Linux sleep
> facility. The results show relatively small typical errors but
> potentially millisecond-scale tail latency, especially under heavy CPU
> contention.

This distinction is central to the project's critical analysis.

------------------------------------------------------------------------

## 15. Graphs Generated

Directory:

`data/final_wsl2/figures/`

Generated figures:

### Figure 1

`figure1_mean_error.png`

Shows: - mean timing error - standard deviation error bars - requested
delay on logarithmic x-axis - separate lines for idle/moderate/heavy

Purpose: Show central tendency plus variability.

### Figure 2

`figure2_median_error.png`

Shows median timing error across requested delays.

Purpose: Shows typical behavior while avoiding dominance by outliers.

### Figure 3

`figure3_p99_error.png`

Shows p99 timing error.

Purpose: Most important figure for real-time analysis because it exposes
tail behavior.

### Figure 4

`figure4_max_error.png`

Shows maximum observed timing error.

Purpose: Illustrates worst observed sample, but should be interpreted
cautiously because a maximum from 500 trials is sample-dependent.

### Figure 5

`figure5_1ms_boxplot.png`

Shows the 1 ms timing-error distribution under: - idle - moderate -
heavy

Outliers are hidden in the plot for readability.

Purpose: Compare the distribution/spread of timing error across load
levels.

------------------------------------------------------------------------

## 16. How to Discuss the Boxplot

For the 1 ms experiment:

-   Idle median is about 133 us.
-   Moderate median is about 109 us.
-   Heavy median is about 85 us.

The heavy condition has a lower median but a much broader upper tail in
the full data.

Therefore: \> The boxplot demonstrates that typical latency alone can be
misleading. Heavy load can preserve or even reduce the median while
increasing variability and tail risk.

Do not claim the heavy box is "better" simply because its median is
smaller.

------------------------------------------------------------------------

## 17. Jiffies Comparison --- Important Technical Finding

The original project wording suggests:

> Compare timer precision with jiffies-based timers.

The investigation found an important feasibility issue:

There is no simple, technically valid modern userspace API that can be
described as "the jiffies version of `clock_nanosleep()`."

Therefore, do NOT make an invalid comparison such as:

`usleep()` = jiffies

or:

`clock_nanosleep()` = hrtimer while another arbitrary sleep API =
jiffies.

The project should explicitly explain this.

### Current technically sound approach

Treat the jiffies-vs-hrtimer comparison as a kernel-mechanism question
rather than pretending two userspace APIs directly expose the two
mechanisms.

An advanced experiment can compare: - a kernel `timer_list` timer using
`add_timer()` - an hrtimer using `hrtimer_start()`

Both can record timestamps and export measurements.

However, these are not equivalent programmer-facing APIs and should be
presented as a kernel mechanism comparison, not as an apples-to-apples
userspace benchmark.

If the kernel-module experiment is not completed, state that as future
work / limitation rather than inventing results.

------------------------------------------------------------------------

## 18. Kernel-Level Comparison Plan (Future / Optional)

Potential module:

### Timer-list path

Use: `struct timer_list` and: `add_timer()`

### hrtimer path

Use: `struct hrtimer` and: `hrtimer_start()`

Timestamp events with an appropriate kernel time function such as:
`ktime_get()`

Export results safely.

The goal would be to compare: - expiry granularity - observed latency -
data structure behavior - relationship to jiffies/ticks

Important: This is a mechanism-level comparison and should not be
described as a direct comparison of two equivalent userspace APIs.

------------------------------------------------------------------------

## 19. WSL2 Limitation

WSL2 is a virtualized execution environment.

Observed timing is affected by: - Linux guest scheduling - Windows host
scheduling - virtualization - virtual timer behavior - CPU contention -
system background activity

Therefore:

> The WSL2 results are valid measurements of the tested WSL2
> environment, but they should not automatically be generalized to
> bare-metal Linux or treated as definitive evidence of native Linux
> worst-case timing.

If native Linux later becomes available, the same benchmark should be
repeated with the same: - delays - load levels - trial counts - CPU
pinning strategy - statistics

Then compare the distributions.

For the current report, simply report WSL2 honestly and use the
limitation as part of the critical analysis.

------------------------------------------------------------------------

## 20. Literature

### Paper 1 --- Core hrtimer paper

Thomas Gleixner and Douglas Niehaus.

**"Hrtimers and Beyond: Transforming the Linux Time Subsystems."**

Linux Symposium 2006, Vol. 1, pp. 333--346.

Official source:
https://www.kernel.org/doc/ols/2006/ols2006v1-pages-333-346.pdf

Important ideas: - traditional timer subsystem - timer wheel -
jiffies/ticks - high-resolution timer motivation - nanosecond time
representation - ordered timer structure - clocksource/clock-event
architecture - hrtimer/timer-wheel coexistence - timing experiments
using POSIX interfaces - effect of system load on latency

### Paper 2 --- Real-time Linux background

Federico Reghenzani, Giuseppe Massari, William Fornaciari.

**"The Real-Time Linux Kernel: A Survey on PREEMPT_RT."**

ACM Computing Surveys, 52(1), Article 18, 2019.

DOI: https://doi.org/10.1145/3297714

Use this to provide broader real-time Linux context and explain why
predictable latency matters.

### Paper 3 --- Timer interference

Pratyush Patel, Manohar Vanga, Björn B. Brandenburg.

**"TimerShield: Protecting High-Priority Tasks from Low-Priority Timer
Interference."**

RTAS 2017, pp. 3--12.

DOI: https://doi.org/10.1109/RTAS.2017.40

Useful for discussing timer interference and real-time scheduling
concerns.

------------------------------------------------------------------------

## 21. Authoritative Linux Documentation

Use these as primary technical sources when appropriate:

Linux kernel hrtimer documentation:
https://docs.kernel.org/timers/hrtimers.html

High-resolution timers: https://docs.kernel.org/timers/highres.html

Delay/sleep functions:
https://docs.kernel.org/timers/delay_sleep_functions.html

Real-time kernel differences:
https://docs.kernel.org/core-api/real-time/differences.html

rtla timerlat documentation:
https://docs.kernel.org/tools/rtla/rtla-timerlat.html

Do not cite random blogs when the kernel documentation or original paper
is available.

------------------------------------------------------------------------

## 22. Required Evidence Discipline

This project must avoid fabricated evidence.

### Never invent:

-   native Linux measurements
-   kernel module results
-   timing values
-   source-code behavior not verified
-   paper titles/authors/DOIs
-   hardware characteristics
-   HZ values unless measured/verified

### Clearly label:

-   theoretical expectations
-   literature findings
-   WSL2 experimental observations
-   limitations
-   future work

### Important wording

Use: \> "The WSL2 experiment observed..."

Instead of: \> "Linux hrtimers guarantee..."

Use: \> "The results are consistent with the expected effect of
scheduling contention on tail latency..."

Instead of: \> "CPU load always increases timer error."

------------------------------------------------------------------------

## 23. Suggested Final Report Structure

### 1. Abstract

Approximately 150--250 words.

Include: - problem - hrtimer motivation - implementation - experiment -
key WSL2 findings - main conclusion

### 2. Introduction

Explain: - why OS timing matters - limitations of coarse tick-based
timing - motivation for high-resolution timers - project research
question - contributions

### 3. Background / Literature Survey

Cover: - HZ - jiffies - timer wheel - clocksource - clock-event
devices - hrtimers - real-time constraints - relevant research papers

### 4. Linux Kernel Implementation

Discuss: - `kernel/time/hrtimer.c` - initialization - enqueueing -
ordered timer structure - interrupt handling - callback execution -
per-CPU behavior - coexistence with timer wheel

Include carefully selected source snippets/diagrams if appropriate.

### 5. Methodology

Describe: - C benchmark - `clock_nanosleep` - `CLOCK_MONOTONIC` -
measurement process - error formula - load generator - CPU pinning - 4
delays - 3 load levels - 500 trials - WSL2 environment

### 6. Results

Use the generated figures.

Include: - mean - median - p95 - p99 - max - standard deviation

Do not overload the section with every raw observation; provide the
complete dataset in an appendix if desired.

### 7. Discussion / Critical Analysis

This should be one of the strongest sections because the rubric gives
40% to analysis/critical thinking.

Discuss: - typical vs worst-case timing - tail latency - scheduler
effects - CPU contention - virtualization effects - why nanosecond timer
resolution does not mean nanosecond userspace execution - why jiffies
comparison is difficult - timer-wheel vs hrtimer design trade-offs -
efficiency vs precision - complexity vs predictability - timer callbacks
and execution context - real-time implications

### 8. Limitations

Explicitly state: - only WSL2 was available - no native Linux results
yet - WSL2 introduces virtualization/host scheduling effects - 500
trials are useful but still limited for extreme-tail statistical
claims - busy-loop load is a simple stress model - userspace end-to-end
latency is not identical to kernel timer-expiry latency - no completed
kernel-module timer_list-vs-hrtimer results unless actually performed

### 9. Future Work

Possible: - native Linux repetition - kernel-module mechanism
comparison - more trials - longer stress tests - PREEMPT_RT comparison -
CPU frequency/governor experiments - `rtla timerlat` - tracing with
ftrace/perf where appropriate

### 10. Conclusion

Answer the research question directly.

A good conclusion should say that: - hrtimer-backed high-resolution
timing can provide relatively small typical timing error - actual
userspace wake-up is affected by scheduling and environment - tail
latency can become milliseconds under heavy contention - this
demonstrates why high-resolution timer design and real-time scheduling
are related but distinct problems

------------------------------------------------------------------------

## 24. Recommended Report Figures

Use these five:

1.  `figure1_mean_error.png`
2.  `figure2_median_error.png`
3.  `figure3_p99_error.png`
4.  `figure4_max_error.png`
5.  `figure5_1ms_boxplot.png`

Most important: - Figure 2 for typical behavior - Figure 3 for real-time
tail behavior - Figure 5 for distribution differences

------------------------------------------------------------------------

## 25. Recommended Key Result to Highlight

The strongest single result:

### 100 ms request under heavy CPU load

-   Median error ≈ 111.75 us
-   p99 error ≈ 3.75 ms
-   Maximum error ≈ 10.83 ms
-   Standard deviation ≈ 735.05 us

Interpretation: \> Most wake-ups were close to the requested expiration,
but rare scheduling delays reached the millisecond range. This
demonstrates that high-resolution timer support improves the granularity
of timer expiration without eliminating scheduling-induced latency.

Do not call the maximum a guaranteed worst case. It is simply the
largest observation among 500 trials.

------------------------------------------------------------------------

## 26. Suggested Core Thesis

A strong central argument for the paper:

> Linux hrtimers solve an important kernel-level timing-resolution
> problem, but high-resolution timer infrastructure does not by itself
> guarantee deterministic userspace execution. The WSL2 experiment
> demonstrates that typical wake-up error can remain relatively small
> while scheduling contention and virtualization produce substantially
> larger tail latency. This distinction explains why high-resolution
> timer support is necessary for precise real-time-oriented timing, but
> is not sufficient by itself to provide hard real-time guarantees.

This should guide the discussion without overstating the results.

------------------------------------------------------------------------

## 27. Current Project Files

Expected project structure:

``` text
os-hrtimer-project/
├── src/
│   ├── timer_benchmark.c
│   ├── cpu_load.c
│   └── check_resolution.c
├── build/
│   ├── timer_benchmark
│   ├── cpu_load
│   └── check_resolution
├── data/
│   └── final_wsl2/
│       ├── 100us_idle.csv
│       ├── 100us_moderate.csv
│       ├── 100us_heavy.csv
│       ├── 1ms_idle.csv
│       ├── 1ms_moderate.csv
│       ├── 1ms_heavy.csv
│       ├── 10ms_idle.csv
│       ├── 10ms_moderate.csv
│       ├── 10ms_heavy.csv
│       ├── 100ms_idle.csv
│       ├── 100ms_moderate.csv
│       ├── 100ms_heavy.csv
│       ├── analysis/
│       │   └── wsl2_summary.csv
│       ├── figures/
│       │   ├── figure1_mean_error.png
│       │   ├── figure2_median_error.png
│       │   ├── figure3_p99_error.png
│       │   ├── figure4_max_error.png
│       │   └── figure5_1ms_boxplot.png
│       └── logs/
├── scripts/
│   ├── run_final_experiment.sh
│   ├── analyze_final.py
│   └── plot_final.py
└── kernel_module/
```

Also include: - `MASTER_CONTEXT.md`

The Linux kernel source tree was separately cloned for source inspection
and should not necessarily be committed wholesale into the project
repository unless specifically needed.

------------------------------------------------------------------------

## 28. GitHub Strategy

The GitHub repository should contain the project artifacts, not a giant
unnecessary copy of the Linux kernel source.

Recommended repository contents:

``` text
README.md
MASTER_CONTEXT.md
src/
scripts/
data/final_wsl2/
docs/        (optional)
figures/     (optional if not kept under data/)
```

Avoid committing: - compiled binaries if not needed - huge Linux kernel
source tree - temporary logs unless useful - unnecessary VS Code
metadata

A `.gitignore` should exclude build artifacts where appropriate.

------------------------------------------------------------------------

## 29. Claude Instructions

When another AI (Claude) reads this file, it should:

1.  Read `MASTER_CONTEXT.md` completely before generating anything.
2.  Treat the WSL2 dataset as the current actual experimental evidence.
3.  Never invent native Linux results.
4.  Never invent a completed jiffies comparison.
5.  Never equate `usleep()` with jiffies without kernel/source evidence.
6.  Distinguish hrtimer resolution from end-to-end userspace timing
    accuracy.
7.  Use the provided figures and numerical results.
8.  Use the listed papers and official Linux documentation as primary
    references.
9.  Verify citations/DOIs before finalizing the paper.
10. Clearly distinguish:

-   literature claims
-   kernel source facts
-   experimental observations
-   interpretations
-   limitations
-   future work

11. Preserve the project's actual research question.
12. Produce a rigorous academic report suitable for an Operating Systems
    case-study project.
13. Prioritize critical analysis because it is 40% of the rubric.
14. Do not hide non-monotonic results where moderate load performs
    better than idle in some metrics.
15. Explain why this non-monotonic behavior is itself a useful
    observation rather than an error to be removed.
16. Do not describe WSL2 measurements as universal Linux guarantees.
17. If recommending additional experiments, label them as
    proposed/future experiments unless they are actually completed.

------------------------------------------------------------------------

## 30. Suggested Claude Prompt After Reading This File

Use something like:

> Read `MASTER_CONTEXT.md` completely and treat it as the authoritative
> project context. Then inspect the repository files, source code, CSV
> data, analysis output, and generated figures. Do not invent any
> missing results, especially native Linux or jiffies-comparison
> results. Based only on verified evidence, help me turn this into a
> rigorous 10--15 page Operating Systems research/case-study paper.
> Preserve the actual WSL2 experimental findings, explain the Linux
> hrtimer kernel architecture using authoritative sources, and emphasize
> critical analysis of resolution vs accuracy vs scheduling latency,
> tail behavior, virtualization, and timer-system design trade-offs. Use
> proper academic citations and verify all references. Before drafting
> the final paper, identify any factual/citation gaps that need
> verification.

------------------------------------------------------------------------

## 31. Final Status

### Completed

-   Project proposal
-   Kernel source exploration
-   Userspace hrtimer benchmark
-   CPU load generator
-   WSL2 experimental protocol
-   6000-trial WSL2 dataset
-   Statistical analysis
-   Five report-quality graphs
-   Preliminary kernel/source investigation
-   Literature identification

### Not completed

-   Native Linux experiment
-   Kernel-module `timer_list` vs `hrtimer` experiment
-   Direct measured jiffies-vs-hrtimer mechanism comparison

### Current best strategy

Use the WSL2 experiment as the completed experimental contribution, be
transparent about its environment/limitations, and build a strong paper
around: 1. Linux kernel hrtimer architecture 2. real measured timing
behavior 3. tail-latency analysis 4. scheduler/load effects 5. WSL2
virtualization limitations 6. why high-resolution timing does not equal
hard real-time determinism 7. the design trade-offs between the
traditional timer system and hrtimers

Do not fabricate missing experiments merely to make the project look
more complete.
