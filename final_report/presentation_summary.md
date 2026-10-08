# Presentation summary (10-minute talk)

Companion to `final_report.pdf`. Every number below comes from the raw CSV files via `analysis/report_analysis.py`.

## One-sentence version

Linux timers have 1 ns resolution, but an ordinary process wakes about 54 µs late by design, later still on an idle machine, and occasionally milliseconds late under load; none of that is caused by the timer mechanism.

## Suggested slide plan

| # | Slide | Time | Figure |
|---|---|---|---|
| 1 | Title and question | 0:30 | none |
| 2 | Why "high resolution" is not "high accuracy" | 1:00 | none |
| 3 | What we built and what it measures | 1:30 | Figure 1 (timer path) |
| 4 | Experiment design | 1:00 | Table 1 (load / CPU placement) |
| 5 | Finding 1: the 54 µs floor is timer slack | 1:30 | Figure 3 (medians) |
| 6 | Proof: the control experiment | 1:00 | Figure 4 (slack / FIFO) |
| 7 | Finding 2: idle is worse than loaded | 1:00 | Figure 2 or Figure 6 left panel |
| 8 | Finding 3: heavy load adds a tail, not a shift | 1:00 | Figure 5 and Figure 6 right panel |
| 9 | What we cannot claim | 1:00 | Table 5 |
| 10 | Conclusion and next steps | 0:30 | none |

## Problem and motivation

- Audio, control loops, packet pacing and robotics all depend on a process waking at the time it asked for.
- Linux serves `clock_nanosleep()` with hrtimers: nanosecond expiry times kept in a red-black tree, a one-shot hardware timer programmed for the next expiry.
- `clock_getres()` reports 1 ns. The question is how much of that an application actually gets.

## Research question

When a normal process sleeps through the hrtimer path, how late does it resume, how does that depend on the sleep length and on CPU load elsewhere, and how much of the lateness belongs to the timer mechanism as opposed to the rest of the OS?

## Methodology and implementation

- `timer_benchmark.c`: `clock_gettime` → `clock_nanosleep(CLOCK_MONOTONIC, relative)` → `clock_gettime`; error = elapsed − requested. 500 trials per run, one CSV row per trial.
- `cpu_load.c`: N busy threads. Benchmark pinned to CPU 0; load confined to CPUs 1–6 (moderate) or 1–11 (heavy). The load never runs on the benchmark's CPU.
- 4 delays (100 µs, 1 ms, 10 ms, 100 ms) × 3 loads × 500 trials = 6,000 samples per environment.
- Environments: native Fedora 44, kernel 7.1.5, Intel i5-1335U; WSL2 on AMD Ryzen 5 8640HS.
- Kernel source traced in `linux_source/` (7.3-rc1): `clock_nanosleep` → `common_nsleep_timens` → `hrtimer_nanosleep` → `do_nanosleep` → `hrtimer_interrupt` → `hrtimer_wakeup` → `wake_up_process`.
- Control experiment (WSL2, 9,000 samples): same benchmark with timer slack set to 1 ns, and under `SCHED_FIFO`.
- Analysis: medians with bootstrap CIs, IQR, p99, fraction later than 1 ms; no reliance on mean and standard deviation.

## Strongest findings

1. **The floor is policy.** Native loaded medians are 53.7–61.5 µs. At 100 µs with moderate load: median 53.7 µs, IQR 0.5 µs, maximum 57.3 µs in 500 trials. The kernel line `hrtimer_set_expires_range_ns(..., current->timer_slack_ns)` gives every normal task a 50 µs slack and the hardware timer is programmed for the end of that window.
2. **Tested, not just argued.** Setting slack to 1 ns on WSL2 lowers the heavy-load median from 78.4 → 25.6 µs, 79.6 → 28.9 µs, 96.2 → 43.2 µs. A shift of 51–53 µs each time.
3. **Idle is the worst typical case.** Idle medians grow with sleep length: 56 → 101 µs native, 89 → 322 µs WSL2. Loading the other CPUs brings them back to the floor. Native 1 ms: IQR 80.4 µs idle, 0.8 µs under moderate load.
4. **Heavy load produces a tail and leaves the median alone.** Native median moves by at most 2.1 µs from moderate to heavy, but wake-ups later than 1 ms go from 0 of 2,000 to 47 of 2,000 (2.35 %); WSL2 from 5 to 57 of 2,000 (2.85 %). Largest observed: 33.3 ms native, 10.8 ms WSL2.
5. **Real-time priority does not remove the WSL2 tail.** With `SCHED_FIFO` the heavy-load p99 is still 350–785 µs and the maximum up to 2.9 ms.

## Figures worth showing

- **Figure 1** (timer path with the four delay sources): use it to say exactly what is and is not measured.
- **Figure 3** (medians vs delay): the flat line just above 50 µs and the rising idle line carry findings 1 and 3 in one picture.
- **Figure 4** (control experiment): the curves shift left by 50 µs and keep their shape.
- **Figure 6** (per-trial trace, native 100 ms): two bands when idle, a flat line under moderate load, bursts under heavy load.
- **Figure 5** (percentage later than 1 ms): the tail in one chart.

## Limitations to state up front

- Black-box measurement: two user-space timestamps; no kernel tracing, so the split into slack / idle exit / run-queue wait is inferred.
- One run per condition, fixed order (idle, then moderate, then heavy).
- CPU 1 is the hyper-thread sibling of CPU 0 and is in both load sets.
- The two environments are different machines with different kernels; no claim about the cost of virtualisation.
- 500 samples: p99 rests on five values; maxima are observed maxima, not worst cases.
- Control experiment only on WSL2, one month after the main run.

## Conclusion

High timer resolution is necessary for precise application timing and is a small part of it. What an application sees is decided by slack policy, power management, the scheduler and, under WSL2, the hypervisor. Each trades punctuality for something else: fewer wake-ups, lower power, fairness, isolation.

## Likely viva questions

**What exactly does your benchmark measure?**
Time between two user-space clock reads around a relative `clock_nanosleep`, minus the requested time. It includes system-call entry, slack, interrupt delivery, wake-up, scheduling and return. It does not timestamp the hrtimer expiry inside the kernel.

**Why is the error about 54 µs and so stable?**
Normal tasks have a 50 µs timer slack. The timer is armed with a soft expiry at the requested time and a hard expiry 50 µs later; the hardware event is set for the hard expiry so that nearby timers can share one interrupt. The remaining ~4 µs is the native wake-up path.

**How do you know it is slack and not latency?**
Source code (`hrtimer.c` lines 2474, 851, 2121), the matching magnitude, a 3–6 % population of trials that fire early (below 50 µs) when another interrupt lands in the window, and the control experiment, where removing slack removed 51–53 µs.

**Why is an idle system slower than a loaded one?**
Most likely idle-state exit: an idle CPU sleeps, and the longer the expected sleep the deeper the state and the longer it takes to wake. Load on the sibling hyper-thread keeps the core awake. We did not measure idle-state residency, so this is a hypothesis; frequency scaling and cold caches are alternatives.

**The load never runs on CPU 0. Why does heavy load create a tail?**
Under heavy load CPU 0 is the only CPU without a busy thread, so other system activity lands there and competes with the benchmark. On native Linux 16 of 65 late samples sit at 0.99–1.02 ms, which is what waiting for a 1 kHz scheduler tick would look like. No scheduler trace was taken, so this is an interpretation.

**Is native Linux better than WSL2?**
The native numbers are lower, but the machines differ in CPU, kernel and tick rate. The comparison is observational and the report does not attribute the difference to virtualisation.

**What is the worst-case latency?**
Not measured. The largest value seen was 33.3 ms in 12,000 main-experiment samples. A worst case needs analysis or far longer runs on a real-time kernel.

**Would `SCHED_FIFO` fix it?**
It removes the slack (median drops to about 25 µs on WSL2). It did not remove millisecond delays under WSL2, which points below the guest scheduler. It was not tried on native Linux.

**How is hrtimer different from the timer wheel?**
The timer wheel is indexed by jiffies and optimised for timeouts that are usually cancelled; its granularity is one tick (4 ms at HZ=250). hrtimers keep exact nanosecond expiries in a red-black tree and program a one-shot clock-event device.

**Why not report mean and standard deviation?**
The distributions are heavy-tailed. In the native 100 ms heavy run five samples of 500 carry 42 % of the total error; the mean is 238 µs while the median is 62 µs.

**What would you do next?**
Kernel tracepoints (`hrtimer_expire_entry`, `sched_wakeup`, `sched_switch`) to split the error into stages; the slack control on native hardware; idle states disabled; load sets that exclude the sibling CPU; randomised, repeated runs.

**What did you change in the repository?**
One line in `scripts/analyze_native.py` (wrong output filename). Everything else is new material under `final_report/`.
