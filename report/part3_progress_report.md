# Part 3 - Mid-Term Progress Report

## 1. Project Overview

This project investigates Linux high-resolution timers (hrtimers) as a case study in kernel time management. The work connects three levels of analysis: Linux timer architecture, the hrtimer implementation, and timing behavior visible to a userspace application.

The central research question is:

> How does Linux high-resolution timer behavior vary with requested timer interval and CPU load, particularly in terms of latency, jitter, and tail behavior, and what does this reveal about Linux timer architecture and real-time operating-system design?

The completed experiment uses Linux under WSL2. It measures `clock_nanosleep(CLOCK_MONOTONIC, ...)` with `clock_gettime(CLOCK_MONOTONIC, ...)`. The result is an end-to-end userspace wake-up measurement, not an isolated measurement of hardware timer resolution or hrtimer callback latency.

### Research hypotheses

The experiment was designed around four cautious hypotheses:

- **H1, interval effect:** requested timer interval influences observed absolute and relative timing error because the measured result includes timer expiry, wake-up, and scheduling behavior.
- **H2, load effect:** increasing CPU load may increase observed latency and jitter, particularly in the upper tail.
- **H3, tail sensitivity:** CPU load may affect p95, p99, maximum error, and standard deviation more strongly than median error.
- **H4, architectural boundary:** high-resolution timer infrastructure provides fine-grained expiry capability but does not guarantee deterministic userspace wake-up latency.

These hypotheses are deliberately not directional guarantees for every statistic. In particular, a non-monotonic median is a meaningful result rather than evidence that the experiment failed. The analysis distinguishes what the data directly show from possible explanations involving scheduling or virtualization.

## 2. Work Completed

The following project components are complete:

- Linux timer architecture research covering jiffies, timer wheels, clocksources, clock-event devices, and hrtimers.
- Userspace benchmark implementation in `src/timer_benchmark.c`.
- CPU-load generator implementation in `src/cpu_load.c`.
- Automated WSL2 experiment with 12 conditions and 500 trials per condition.
- Collection of 6,000 timing observations in `data/final_wsl2/`.
- Statistical analysis including mean, median, p90, p95, p99, minimum, maximum, and standard deviation.
- Generation of five result figures.
- Preliminary interpretation of typical latency, tail latency, and the effects of virtualization.

The completed results are stored in `data/final_wsl2/analysis/wsl2_summary.csv`. Native Linux measurements and a kernel-level `timer_list` versus `hrtimer` comparison are not yet complete.

## 3. Linux Timer Architecture Investigation

Traditional Linux timing is associated with periodic ticks, `HZ`, and the `jiffies` counter. A tick-based model is efficient for many ordinary timeouts, but its natural time scale is coarse compared with some sub-millisecond requirements. The timer wheel is designed for efficient management of large numbers of general-purpose timers rather than arbitrary high-resolution deadline ordering.

Linux timer architecture separates several responsibilities:

- A **clocksource** provides a way to read the current time.
- A **clock-event device** produces a programmable future timer event.
- An **hrtimer** represents and orders high-resolution timer expiries.
- The scheduler determines when a runnable userspace task actually executes.

This separation explains why timer resolution and application timing are different properties. A timer can be represented and expired at high resolution, while the target process can still experience interrupt, wake-up, scheduling, CPU-contention, or virtualization delay.

The supplied source snapshot identifies itself as Linux version 7.3-rc1 in its top-level Makefile. That version label describes the source used for implementation analysis; it is not evidence that the WSL2 guest ran that exact kernel unless the experiment log records the running kernel version. This distinction matters because timer implementation details and configuration options can change between kernel versions.

The clocksource and timekeeping files clarify another part of the path. `clocksource.c` documents the conversion between a hardware counter frequency and nanoseconds using multiplier and shift values. `timekeeping.c` maintains fast timekeeper state and supplies clock readings through the selected clocksource. Thus, a monotonic timestamp is produced by a timekeeping layer that converts counter observations into time units; it is not produced by the clock-event device that schedules the future interrupt. The benchmark's two `clock_gettime()` calls observe this timekeeping layer at the userspace boundary.

## 4. hrtimer Kernel Implementation Study

The targeted source snapshot is present under `linux_source/` and contains the specified timer files. The source supports the following measured-path model:

`clock_nanosleep -> hrtimer_nanosleep -> ordered hrtimer expiry -> clock-event interrupt -> sleeper wake-up -> schedule() returns -> userspace clock_gettime`

The benchmark does not call the internal functions directly, and the source does not make the final userspace wake-up instantaneous. It explains the timer mechanism being exercised; the experiment measures the end-to-end result after scheduling and userspace effects are included.

In `kernel/time/posix-timers.c`, `common_nsleep_timens()` handles `CLOCK_MONOTONIC` and `CLOCK_BOOTTIME` and calls `hrtimer_nanosleep()`. This is the source-level handoff connecting the benchmark's public API to the hrtimer sleep implementation.

### Verified source excerpts

1. **POSIX sleep path, `kernel/time/posix-timers.c`, `common_nsleep_timens()`:**

	> `return hrtimer_nanosleep(texp, flags & TIMER_ABSTIME ?`
	>
	> `                         HRTIMER_MODE_ABS : HRTIMER_MODE_REL,`

	This connects `clock_nanosleep()` for the monotonic clock family to the hrtimer sleep implementation. The public API is therefore exercising kernel timer infrastructure, but the application does not directly control an internal hrtimer.

2. **Sleeper setup and scheduling, `kernel/time/hrtimer.c`, `hrtimer_nanosleep()` and `do_nanosleep()`:**

	> `hrtimer_sleeper_start_expires(t, mode);`
	>
	> `schedule();`

	and:

	> `hrtimer_set_expires_range_ns(&t.timer, rqtp, current->timer_slack_ns);`

	`hrtimer_nanosleep()` sets the expiry with timer slack; `do_nanosleep()` starts the sleeper and calls `schedule()`. This directly supports treating the benchmark as an hrtimer-backed sleep measurement while also showing why expiry time and userspace resumption are different events.

3. **Ordered insertion, `kernel/time/hrtimer.c`, `enqueue_hrtimer()`:**

	> `The timer is inserted in expiry order.`
	>
	> `Insertion into the red black tree is O(log(n)).`

	The function adds the timer to the active timer queue and updates `expires_next` when it becomes the next expiry. This is the ordering mechanism behind the hrtimer side of the architecture.

4. **Timer interrupt and expiry processing, `kernel/time/hrtimer.c`, `hrtimer_interrupt()`:**

	> `__hrtimer_run_queues(cpu_base, now, flags, HRTIMER_ACTIVE_HARD);`
	>
	> `hrtimer_interrupt_rearm(cpu_base, expires_next);`

	On a high-resolution clock-event interrupt, the code processes due hrtimers and rearms the next event. The same function comments that tracing, long callbacks, or running in a virtual machine can leave the next timer already expired, which is relevant to interpreting WSL2 tail latency without treating the comment as a measurement of this experiment.

5. **Clock-event programming, `kernel/time/clockevents.c`, `clockevents_program_event()`:**

	> `@expires: absolute expiry time (monotonic clock)`
	>
	> `dev->next_event = expires;`

	This is the clock-event side of the clocksource/clock-event distinction: the clocksource supplies time readings, while a clock-event device is programmed for a future expiry. The hrtimer machinery and the event device therefore have different responsibilities.

6. **Ordered timerqueue, `linux_source/lib/timerqueue.c` and `include/linux/timerqueue.h`:**

	> `Manages a simple queue of timers, ordered by expiration time.`
	>
	> `Uses rbtrees for quick list adds and expiration.`

	The timerqueue implementation and header expose an ordered, leftmost-node representation for the earliest timer. This is the data-structure boundary between an hrtimer's expiry and clock-event reprogramming.

7. **Jiffies and the ordinary timer wheel, `kernel/time/jiffies.c` and `kernel/time/timer.c`:**

	> `It has the same coarse resolution as the timer interrupt frequency HZ`

	The jiffies source explicitly describes its resolution as tied to the timer interrupt frequency. The ordinary timer implementation uses level-specific wheel constants such as `LVL_GRAN(n)` and selects buckets with `calc_index()`. This supports an architectural comparison, not a numerical userspace baseline: the completed experiment did not measure equivalent `timer_list` and hrtimer operations.

Together, these excerpts support the chain from the POSIX sleep request through hrtimer ordering and clock-event delivery to task scheduling. They do not establish a universal accuracy bound, because the measured wake-up also depends on scheduler dispatch, CPU placement, virtualization, and other system activity. The source comment in `hrtimer_interrupt()` specifically notes that a timer can already be expired after tracing, long callbacks, or being scheduled away in a virtual machine; that is relevant context for WSL2, not proof of the cause of an individual sample.

The distinction between the clocksource and clock-event device is especially important for this project. Reading the clock answers the question “what time is it now?” and permits the benchmark to calculate elapsed time. Programming the event answers “when should the kernel be notified next?” A clocksource may offer a fine-grained reading while an event is delivered late, and an event may be delivered on time while the awakened task is scheduled late. The single userspace error value combines these stages, so it should not be assigned to one component without instrumentation.

## 5. Experimental Methodology

The experiment varies two factors:

- Requested delay: 100 microseconds, 1 millisecond, 10 milliseconds, and 100 milliseconds.
- CPU load: idle, moderate, and heavy.

The WSL2 environment reported 12 logical CPUs. The benchmark was pinned to CPU 0. Moderate load used six busy-loop workers on CPUs 1-6; heavy load used eleven workers on CPUs 1-11. Each condition contained 500 trials:

`4 delays x 3 load levels x 500 trials = 6,000 observations`

For each trial, the benchmark records a monotonic start timestamp, calls `clock_nanosleep`, records the end timestamp, and computes:

`timing error = actual elapsed time - requested delay`

The benchmark stores raw measurements in nanoseconds. Analysis and figures use microseconds. Percentiles are computed from sorted samples using linear interpolation at position `p(n - 1)`, and standard deviation is population standard deviation.

The load generator creates repeatable CPU contention through busy-loop worker threads. It does not model I/O contention, interrupt storms, priority inversion, kernel locking, or a real-time workload, so the load labels describe this experiment specifically.

The affinity design isolates the benchmark's nominal execution CPU from the worker ranges: CPU 0 runs the benchmark, CPUs 1-6 run the six moderate workers, and CPUs 1-11 run the eleven heavy workers. This reduces direct runnable-task competition on CPU 0 and makes the conditions easier to reproduce. It does not isolate the CPU from kernel housekeeping, interrupts, virtual-machine scheduling, shared caches, frequency transitions, or host-level contention. The design should therefore be understood as controlled placement, not full CPU isolation.

The 500-trial choice balances coverage and experiment duration. It provides enough observations to estimate central statistics and expose rare millisecond-scale events, while keeping each condition short enough to run all 12 cells under comparable conditions. It is not sufficient to establish a high-confidence extreme-value bound. In particular, approximately five observations influence a linearly interpolated p99 in a 500-sample condition, and the maximum is determined by one observation. This is why the experiment is a characterization study rather than a worst-case certification.

The error definition also has a deliberate directional interpretation. For a relative sleep, the requested duration is a lower target in ordinary operation: the process is expected to resume no earlier than the requested interval, although the report does not turn the observed positive minima into a universal API guarantee. Positive error measures lateness after the requested interval; it does not measure the absolute time of the deadline independently from the start timestamp. Using `CLOCK_MONOTONIC` avoids confusing wall-clock correction with elapsed duration, but it does not remove scheduler or virtualization effects.

## 6. Completed Experiment

The completed dataset contains twelve CSV files, one for each delay/load combination. The analysis verified 500 observations per condition and 6,000 observations in total.

The benchmark measures the following end-to-end path:

`clock_nanosleep -> kernel timer infrastructure -> timer expiry -> task wake-up -> scheduler dispatch -> userspace clock_gettime`

This boundary is important. The measurement does not separately identify the instant of hrtimer insertion, virtual or hardware interrupt arrival, callback execution, task wake-up, scheduler dispatch, or Windows host scheduling. It reports what the application experienced after requesting a delay.

The repository also contains generated figures for mean error, median error, p99 error, maximum error, and the 1 ms error distribution. The analysis can be reproduced with:

```bash
python3 scripts/analyze_final.py
python3 scripts/plot_final.py
```

## 7. Results and Preliminary Analysis

All values below are timing error in microseconds.

| Delay | Load | Mean | Median | p90 | p95 | p99 | Maximum | Std. dev. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 100 us | Idle | 100.72 | 88.98 | 134.01 | 154.33 | 188.57 | 407.17 | 29.38 |
| 100 us | Moderate | 93.00 | 89.05 | 110.02 | 124.66 | 157.46 | 815.02 | 40.36 |
| 100 us | Heavy | 148.74 | 80.26 | 101.86 | 326.47 | 2,301.56 | 4,448.84 | 382.98 |
| 1 ms | Idle | 166.26 | 132.96 | 225.69 | 262.68 | 610.67 | 3,907.87 | 225.00 |
| 1 ms | Moderate | 126.17 | 108.90 | 192.84 | 217.78 | 413.62 | 1,180.58 | 78.84 |
| 1 ms | Heavy | 156.80 | 84.98 | 108.75 | 305.50 | 2,990.28 | 3,364.61 | 394.56 |
| 10 ms | Idle | 309.88 | 228.81 | 576.23 | 668.97 | 1,261.43 | 1,802.33 | 213.87 |
| 10 ms | Moderate | 156.03 | 124.06 | 206.13 | 247.10 | 641.16 | 5,030.66 | 268.25 |
| 10 ms | Heavy | 218.24 | 96.81 | 165.95 | 430.90 | 3,710.83 | 6,699.21 | 608.99 |
| 100 ms | Idle | 480.56 | 321.55 | 862.87 | 937.35 | 1,941.33 | 3,469.20 | 367.25 |
| 100 ms | Moderate | 146.55 | 123.16 | 207.04 | 226.04 | 411.40 | 2,516.63 | 140.35 |
| 100 ms | Heavy | 242.43 | 111.75 | 162.44 | 438.86 | 3,752.24 | 10,831.14 | 735.05 |

The main observations are:

- Typical error is generally in the tens or hundreds of microseconds.
- Heavy load produces substantially wider tails in several conditions.
- The 100 ms heavy-load condition has a median error of 111.75 us, but a p99 error of 3,752.24 us and a maximum of 10,831.14 us.
- Mean and median error do not increase monotonically with load. Moderate load is lower than idle in several conditions, and heavy load has the lowest median in all four delay groups.
- Idle mean error rises from 100.72 us at a 100 us request to 480.56 us at a 100 ms request, but this does not prove that hrtimer precision degrades with delay. The measured value includes wake-up and scheduling effects.

The strongest preliminary conclusion is that median behavior and tail behavior describe different risks. A median near 100 us does not rule out occasional millisecond-scale delays.

## 8. Statistical Interpretation and Discussion

### 8.1 What each statistic contributes

The mean is useful for estimating aggregate overhead, but it is pulled upward by rare long sleeps. This is visible in the 100 microsecond heavy condition: the median is 80.26 microseconds, while the mean is 148.74 microseconds and the maximum is 4,448.84 microseconds. The median gives a better description of the typical trial, whereas the mean reflects both typical behavior and the cost of outliers.

The p90 and p95 describe the boundary of the relatively common upper tail. At 10 milliseconds under idle load, p90 is 576.23 microseconds and p95 is 668.97 microseconds, while p99 is 1,261.43 microseconds. At 100 milliseconds under heavy load, p95 is 438.86 microseconds but p99 is 3,752.24 microseconds. The separation between p95 and p99 indicates that the rarest one percent behave differently from the bulk of the sample. Standard deviation makes the same point in another form: it is 735.05 microseconds in the 100 ms heavy condition, compared with 140.35 microseconds under moderate load.

The maximum is important for discovering the scale of rare observed delays, especially when a deadline can be missed by one event. It must not be described as a worst-case guarantee. With 500 trials, the maximum is one sample selected from a finite observation window. Longer runs could reveal larger values, and different host states could produce a different distribution. This is why the report uses “maximum observed error” rather than “worst-case latency.”

### 8.2 Typical latency versus tail latency

The 100 ms heavy-load result is the most useful example. A median of 111.75 microseconds could support a positive statement about typical behavior, but it would conceal a p99 of 3.752 milliseconds and a maximum of 10.831 milliseconds. A control loop whose deadline is several milliseconds might tolerate most trials but still fail intermittently. A hard real-time controller cannot infer safety from the median because its correctness depends on the event that happens at the wrong time, not the event that happens most often.

The same contrast appears at shorter delays. For 1 ms heavy load, the median is 84.98 microseconds and p99 is 2,990.28 microseconds. The p99 error is larger than the requested interval itself. That does not mean the timer infrastructure failed to represent a 1 ms deadline; it means that the application returned substantially late in a small fraction of observations. The benchmark's endpoint includes scheduling and virtualization, so it cannot assign the delay to timer expiry alone.

The figures should be interpreted together. The mean plot shows aggregate magnitude and dispersion; the median plot shows typical behavior; the p99 plot reveals rare delays; the maximum plot shows the largest sampled event; and the 1 ms boxplot summarizes the central distribution but suppresses extreme fliers for readability. No single figure is an adequate real-time characterization.

### 8.3 Hypothesis assessment

**H1 is partly supported but qualified.** Error changes with requested interval, especially in idle conditions, but the pattern is not monotonic across all load levels. The likely measured quantity is fixed wake-up and scheduling overhead combined with interval-specific behavior, not a pure change in hrtimer precision.

**H2 is supported at the sample level.** Heavy load has larger p99 and standard deviation than idle for all four requested intervals. For example, at 10 milliseconds p99 increases from 1,261.43 microseconds idle to 3,710.83 microseconds heavy, and standard deviation increases from 213.87 to 608.99 microseconds. This supports a load-associated tail effect under the tested conditions, but not a universal law for all systems.

**H3 is supported.** Median error does not rise from idle to moderate to heavy. Heavy load has the lowest median in all four groups, and moderate load is lower than idle in several groups. This is an important result rather than an inconvenient exception. It shows why a simplistic “more load equals more latency” interpretation is empirically inadequate.

**H4 is supported by both source and measurements.** The source shows a sleep path that starts an hrtimer and then calls `schedule()`. The measurements show small typical error coexisting with large tails. Together, they support the conclusion that high-resolution expiry capability is necessary for fine-grained timing but is not sufficient for deterministic userspace execution.

### 8.4 Non-monotonic load effects and plausible mechanisms

The benchmark is pinned to CPU 0 while workers are placed on other logical CPUs, so direct competition for the benchmark's nominal CPU is reduced. That design makes the load conditions more controlled, but it does not remove shared resources. Guest scheduling, host scheduling of virtual CPUs, interrupt placement, cache and frequency effects, and interactions between the benchmark's sleep state and the load processes can still change the result. Moderate load could also alter when the virtual machine is scheduled or when CPUs leave idle states. These are plausible mechanisms, not established causes.

The important distinction is between observation and explanation. The dataset establishes that moderate and heavy conditions sometimes have lower central error than idle and that heavy conditions have broader tails. It does not establish whether a particular sample was caused by a host deschedule, a delayed virtual interrupt, a scheduler decision, power management, or another event. Kernel tracing and repeated runs under controlled host states are needed for attribution.

### 8.5 Conceptual distinction: expiry, wake-up, and execution

An hrtimer expiry is a kernel event becoming due. A wake-up makes a task eligible to run. Scheduling chooses a runnable task. Userspace execution begins only after those stages and the return path have completed. The benchmark measures from a userspace timestamp before the sleep to another userspace timestamp after return, so its error is an end-to-end quantity. It is not a direct measure of the delay between the hardware event and the hrtimer callback.

This distinction also explains why “timer resolution” is not an appropriate synonym for “application accuracy.” Resolution describes representability. Accuracy describes observed closeness to a requested time. Jitter describes variation. Tail latency describes the upper part of that variation. The maximum observed latency describes only the largest sample. Keeping these concepts separate prevents the experiment from overclaiming what it measures.

### 8.6 Architectural comparison with jiffies

The jiffies path is organized around a tick-related counter and ordinary timer-wheel buckets. Hrtimers use high-resolution time and ordered expiry management. A timer wheel is efficient for many general-purpose timeouts where coarse granularity and eventual expiry are sufficient. An ordered high-resolution queue is appropriate when the next deadline must be selected more finely. The trade-off includes data-structure work, clock-event reprogramming, interrupt activity, and power cost.

The present data cannot quantify that trade-off because both requested sleeps use the POSIX interface and the experiment does not record kernel callback timestamps for either mechanism. The academically correct claim is architectural: Linux retains both mechanisms because precision, overhead, scalability, and workload requirements differ. Part 4 will provide the direct mechanism-level comparison.

### 8.7 Implications for real-time systems

For soft real-time work, the distributions can help choose a design target, but the target should be based on a percentile appropriate to the application and validated under representative interference. For hard real-time work, percentile behavior is still insufficient without a defensible bound and a configuration that controls preemption, interrupts, priorities, CPU isolation, frequency behavior, and kernel critical sections. A general-purpose WSL2 guest is not such a proof environment.

This is a difference between performance and predictability. A low mean says that the system usually incurs limited additional delay. Predictability asks whether the delay remains within a defensible bound when relevant interference and execution states are considered. A system can have excellent average performance and still be unsuitable for a hard deadline if a rare delay is unacceptable. The separation between p50 and p99 is therefore more important to the real-time motivation than the fact that the mean is often small.

Hrtimers are therefore an enabling layer, not a complete real-time guarantee. They can make a precise expiry representable and scheduleable, but they cannot force immediate userspace dispatch. The result also illustrates why low-priority timer interference deserves attention: timer callbacks, interrupts, and wake-ups consume resources that can affect other tasks, as reflected in the motivation for TimerShield [3].

## 9. Figures and Reproducible Evidence

The existing five figures remain part of the report and use the completed dataset without alteration:

![Figure 1. Mean timing error with standard-deviation error bars.](../data/final_wsl2/figures/figure1_mean_error.png)

Figure 1 compares mean error and population-standard-deviation error bars. Its main value is showing that mean magnitude and variability are not the same quantity; heavy-load error bars are especially wide.

![Figure 2. Median timing error.](../data/final_wsl2/figures/figure2_median_error.png)

Figure 2 shows the non-monotonic median pattern. Heavy load has the lowest median in each interval even though its upper tail is generally worse.

![Figure 3. P99 timing error.](../data/final_wsl2/figures/figure3_p99_error.png)

Figure 3 is the most important figure for deadline analysis because it exposes millisecond-scale delays hidden by the median.

![Figure 4. Maximum observed timing error.](../data/final_wsl2/figures/figure4_max_error.png)

Figure 4 shows the largest sampled error, including the 10,831.14 microsecond heavy-load observation at 100 milliseconds. It is evidence about sample exposure, not a platform bound.

![Figure 5. 1 ms timing-error distribution.](../data/final_wsl2/figures/figure5_1ms_boxplot.png)

Figure 5 shows the central 1 ms distributions. Because the plotting script hides fliers, the table is required to interpret the extremes.

The experiment is reproducible from the retained raw CSV files, the source benchmark, the load generator, and the analysis scripts. Reproduction should record the kernel version, hardware or virtualization configuration, logical CPU count, affinity, CPU governor, and host state. Repeating the same commands without recording those variables would make it difficult to determine whether a distribution change reflects Linux behavior or environmental variation.

This reproducibility requirement is also part of the interpretation: a repeated run is not automatically a replication if the virtual CPU allocation, host load, or power policy changes. The raw observations should remain available alongside summary statistics so later work can inspect skew, outliers, and percentile definitions rather than relying only on rounded means.

## 10. Limitations and Threats to Validity

The WSL2 environment is the largest external-validity limitation. WSL2 measurements include the behavior of a virtualized Linux environment and its Windows host. They should not be presented as native Linux, bare-metal, or PREEMPT_RT measurements. Virtualization is not merely random noise: it can change event delivery and tail behavior, so it is part of the measured system while also limiting generalization.

The host scheduler is particularly important because guest CPU affinity does not imply exclusive access to physical execution resources. A virtual CPU can be descheduled even when the benchmark is pinned to a logical guest CPU, and delayed guest execution can appear as a late userspace wake-up. The experiment did not capture Windows host load or virtual CPU scheduling traces, so these remain possible explanations rather than established causes.

The benchmark is userspace-only. It cannot identify timer insertion cost, clock-event programming delay, virtual interrupt arrival, hrtimer callback duration, task wake-up latency, scheduler dispatch latency, or host descheduling independently. As a result, it is impossible to claim that hrtimer expiry itself caused a particular outlier. Tracing would be needed to split the path into stages.

The two `clock_gettime()` calls, the `clock_nanosleep()` transition, timestamp conversion, and loop overhead are included in the measured interval. Fixed overhead is more visible at 100 microseconds than at 100 milliseconds. The benchmark intentionally measures the complete application-visible operation; subtracting a separately calibrated overhead would add another assumption and still would not isolate timer expiry from scheduler dispatch. The result is therefore observed application delay, not pure timer primitive cost.

The CPU workload is deliberately simple. Busy-loop workers create sustained runnable work, but real systems also experience I/O, interrupts, kernel locks, cache pressure, migrations, priority inversion, and power-management transitions. The experiment therefore characterizes one controlled interference model rather than all load types.

Hardware and configuration diversity is another limitation. One WSL2 configuration cannot establish how the result changes with a different processor, timer source, logical CPU topology, Windows version, kernel configuration, or power policy. Even native Linux results would require records of the selected clocksource, event device, scheduler configuration, CPU governor, idle-state policy, and whether the kernel is preemptible or PREEMPT_RT. The present report makes no claim that its percentile values transfer to those environments.

CPU frequency and idle-state behavior may affect both event delivery and task resumption. The experiment did not hold frequency, package power, or host power policy constant as independent variables. These effects are therefore threats to causal interpretation, not missing measurements that can be silently assumed away. A follow-up should either control them or record them as experimental factors.

There are 500 observations per condition. This is enough to expose meaningful sample differences and rare millisecond-scale events, but p99 is influenced by only about five observations and the maximum by one. A larger number of repeated runs is required before making strong claims about extreme tails. The current data support observed-distribution statements, not worst-case guarantees.

The study also has no inferential model estimating uncertainty across independent runs. The 500 trials within a condition are repeated observations from one execution context, and successive observations may share host or scheduler state. The report therefore emphasizes descriptive statistics rather than treating the table as a population estimate with a narrow confidence interval. Repeated runs, randomized condition order, and confidence intervals or bootstrap summaries would strengthen Part 4.

Finally, the current work has no direct `timer_list` versus hrtimer measurement. A userspace API substitution would not solve that problem because it would not hold the kernel mechanism constant except for the timer implementation. The correct remedy is a kernel-level experiment with explicit timestamp boundaries.

## 11. Research Contribution and Part 4 Plan

The current study establishes four things. First, the tested POSIX sleep path is connected to hrtimer infrastructure in the Linux source. Second, the WSL2 benchmark produces generally small typical timing errors over four requested intervals. Third, heavy load is associated with much larger tail dispersion in this dataset. Fourth, the effect is not monotonic in the median, so typical behavior cannot stand in for tail behavior.

The study suggests that an application-visible timing result is shaped by the interaction of timer infrastructure, scheduling, CPU placement, and virtualization. It does not establish a universal hrtimer accuracy bound, native Linux behavior, hard real-time predictability, or a direct advantage over `timer_list`.

Part 4 should implement a kernel-level experiment comparing `timer_list`/jiffies and hrtimers. It should measure timer interval, callback or expiry latency, jitter, p95, p99, maximum observed latency, and behavior under the same load classes where meaningful. It should state whether timestamps are taken at enqueue, intended expiry, callback entry, task wake-up, or userspace return. It should also report overhead where that can be measured without changing the mechanism's behavior.

The next stage should repeat the userspace experiment on native Linux, record hardware and kernel configuration, increase repeated-run coverage, and use ftrace, perf, or `rtla timerlat` to separate timer expiry from scheduling latency. These additions will address the largest threats to causal interpretation while leaving the completed WSL2 dataset as the baseline.

## 12. Conclusion

The completed evidence supports a careful conclusion: high-resolution timer infrastructure is necessary for fine-grained timer expiry, but it is not sufficient for deterministic high-resolution userspace execution. The Linux source shows a layered path from `clock_nanosleep()` to `hrtimer_nanosleep()`, ordered timer management, clock-event programming, interrupt processing, task wake-up, and scheduling. The benchmark measures the end-to-end result of that path.

The 6,000 observations show why this distinction matters. In the 100 ms heavy condition, the median error is 111.75 microseconds, p99 is 3,752.24 microseconds, and the maximum is 10,831.14 microseconds. Heavy load does not always increase the mean or median, but its tails are substantially broader in several conditions. This is evidence against both simplistic claims that “hrtimers are perfectly precise” and simplistic claims that “more load always increases latency.”

The contribution is a controlled WSL2 characterization of hrtimer-backed userspace timing, with source-grounded interpretation and explicit tail analysis. It is not a native-Linux guarantee and not a direct jiffies benchmark. The kernel-level `timer_list` versus hrtimer experiment is the natural next step.

## 13. References

[1] Thomas Gleixner and Douglas Niehaus, "Hrtimers and Beyond: Transforming the Linux Time Subsystems," *Linux Symposium*, 2006. https://www.kernel.org/doc/ols/2006/ols2006v1-pages-333-346.pdf

[2] Federico Reghenzani, Giuseppe Massari, and William Fornaciari, "The Real-Time Linux Kernel: A Survey on PREEMPT_RT," *ACM Computing Surveys*, vol. 52, no. 1, 2019. https://doi.org/10.1145/3297714

[3] Pratyush Patel, Manohar Vanga, and Björn B. Brandenburg, "TimerShield: Protecting High-Priority Tasks from Low-Priority Timer Interference," *2017 IEEE Real-Time and Embedded Technology and Applications Symposium (RTAS)*, 2017.

[4] Linux kernel documentation, "High-resolution timers." https://docs.kernel.org/timers/highres.html

[5] Linux kernel documentation, "hrtimers." https://docs.kernel.org/timers/hrtimers.html

[6] Linux kernel documentation, "Delay and sleep functions." https://docs.kernel.org/timers/delay_sleep_functions.html

[7] Linux kernel documentation, "Real-time kernel differences." https://docs.kernel.org/core-api/real-time/differences.html

[8] Linux kernel documentation, "rtla timerlat." https://docs.kernel.org/tools/rtla/rtla-timerlat.html

Project evidence: `src/timer_benchmark.c`, `src/cpu_load.c`, `data/final_wsl2/`, `data/final_wsl2/analysis/wsl2_summary.csv`, and `data/final_wsl2/figures/`.
