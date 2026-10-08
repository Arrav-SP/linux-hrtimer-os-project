#!/usr/bin/env python3
"""
Analysis and figures for the final case-study report.

Reads only the raw per-trial CSV files (never the pre-computed summaries):

    data/final_wsl2/<delay>_<load>.csv        main experiment, WSL2
    data/native_<delay>_<load>.csv            main experiment, native Fedora
    final_report/supplementary/data/*.csv     slack / SCHED_FIFO control run

Run from the repository root:

    python final_report/analysis/report_analysis.py

Outputs:
    final_report/figures/*.png
    final_report/analysis/tables/*.csv
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from scipy import stats

FIG_DIR = "final_report/figures"
TAB_DIR = "final_report/analysis/tables"
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(TAB_DIR, exist_ok=True)

DELAYS = ["100us", "1ms", "10ms", "100ms"]
DELAY_LABEL = {"100us": "100 µs", "1ms": "1 ms", "10ms": "10 ms", "100ms": "100 ms"}
DELAY_US = {"100us": 100, "1ms": 1000, "10ms": 10000, "100ms": 100000}
LOADS = ["idle", "moderate", "heavy"]
ENVS = ["native", "wsl2"]
ENV_LABEL = {"native": "Native Fedora (Intel i5-1335U)", "wsl2": "WSL2 (AMD Ryzen 5 8640HS)"}
ENV_PATH = {"wsl2": "data/final_wsl2/{d}_{l}.csv", "native": "data/native_{d}_{l}.csv"}
COLOR = {"idle": "#4c72b0", "moderate": "#dd8452", "heavy": "#55a868"}
VCOLOR = {"default": "#4c72b0", "slack1": "#c44e52", "fifo": "#8172b3"}
VLABEL = {
    "default": "SCHED_OTHER, default slack (50 µs)",
    "slack1": "SCHED_OTHER, slack = 1 ns",
    "fifo": "SCHED_FIFO priority 80",
}
SLACK_US = 50.0
RNG = np.random.default_rng(20261009)

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


# ------------------------------------------------------------------
# Loading and validation
# ------------------------------------------------------------------

def read_errors_us(path, expected_ns=None):
    df = pd.read_csv(path)
    assert len(df) == 500, f"{path}: {len(df)} rows"
    assert (df.trial.values == np.arange(1, 501)).all(), path
    assert (df.actual_ns - df.requested_ns == df.error_ns).all(), path
    if expected_ns is not None:
        assert (df.requested_ns == expected_ns).all(), path
    return df.error_ns.values / 1000.0


X = {}
for env in ENVS:
    for d in DELAYS:
        for l in LOADS:
            X[env, d, l] = read_errors_us(ENV_PATH[env].format(d=d, l=l), DELAY_US[d] * 1000)

SUPP = {}
for v in ["default", "slack1", "fifo"]:
    for d in ["100us", "1ms", "10ms"]:
        for l in ["idle", "heavy"]:
            SUPP[v, d, l] = read_errors_us(
                f"final_report/supplementary/data/{v}_{d}_{l}.csv", DELAY_US[d] * 1000)


def boot_ci(x, fn, n=4000):
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    vals = fn(x[idx], axis=1)
    return np.percentile(vals, [2.5, 97.5])


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def summarise(x):
    med_lo, med_hi = boot_ci(x, np.median)
    p99_lo, p99_hi = boot_ci(x, lambda a, axis: np.percentile(a, 99, axis=axis))
    k = int((x > 1000).sum())
    lo, hi = wilson(k, len(x))
    s = np.sort(x)
    return {
        "n": len(x),
        "min_us": x.min(),
        "p25_us": np.percentile(x, 25),
        "median_us": np.median(x),
        "median_ci_lo": med_lo,
        "median_ci_hi": med_hi,
        "p75_us": np.percentile(x, 75),
        "iqr_us": np.percentile(x, 75) - np.percentile(x, 25),
        "p90_us": np.percentile(x, 90),
        "p95_us": np.percentile(x, 95),
        "p99_us": np.percentile(x, 99),
        "p99_ci_lo": p99_lo,
        "p99_ci_hi": p99_hi,
        "max_us": x.max(),
        "mean_us": x.mean(),
        "sd_us": x.std(),
        "pct_below_50us": 100 * (x < SLACK_US).mean(),
        "n_over_1ms": k,
        "pct_over_1ms": 100 * k / len(x),
        "pct_over_1ms_lo": 100 * lo,
        "pct_over_1ms_hi": 100 * hi,
        "top5_share_of_sum_pct": 100 * s[-5:].sum() / s.sum(),
        "p99_over_median": np.percentile(x, 99) / np.median(x),
    }


rows = []
for (env, d, l), x in X.items():
    rows.append({"env": env, "delay": d, "load": l, **summarise(x)})
MAIN = pd.DataFrame(rows)
MAIN.to_csv(f"{TAB_DIR}/main_summary.csv", index=False, float_format="%.3f")

rows = []
for (v, d, l), x in SUPP.items():
    rows.append({"variant": v, "delay": d, "load": l, **summarise(x)})
SUPPT = pd.DataFrame(rows)
SUPPT.to_csv(f"{TAB_DIR}/supplementary_summary.csv", index=False, float_format="%.3f")

# Cross-check against the summaries committed by the original pipeline.
for env, path in [("wsl2", "data/final_wsl2/analysis/wsl2_summary.csv"),
                  ("native", "data/native_analysis/analysis/native_summary.csv")]:
    old = pd.read_csv(path)
    for _, r in old.iterrows():
        m = MAIN[(MAIN.env == env) & (MAIN.delay == r.delay) & (MAIN.load == r["load"])].iloc[0]
        assert abs(m.median_us - r.median_error_us) < 1e-6
        assert abs(m.p99_us - r.p99_error_us) < 1e-6
        assert abs(m.max_us - r.max_error_us) < 1e-6
        assert abs(m.mean_us - r.mean_error_us) < 1e-6
print("Committed summaries reproduce from raw data: OK")

# Rank-based tests of the load effect (location shift, not tail).
rows = []
for env in ENVS:
    for d in DELAYS:
        kw = stats.kruskal(*[X[env, d, l] for l in LOADS])
        a = stats.mannwhitneyu(X[env, d, "idle"], X[env, d, "moderate"])
        b = stats.mannwhitneyu(X[env, d, "moderate"], X[env, d, "heavy"])
        fe = stats.fisher_exact([
            [(X[env, d, "heavy"] > 1000).sum(), (X[env, d, "heavy"] <= 1000).sum()],
            [(X[env, d, "moderate"] > 1000).sum(), (X[env, d, "moderate"] <= 1000).sum()],
        ])
        rows.append({
            "env": env, "delay": d,
            "kruskal_p": kw.pvalue,
            "P(idle>moderate)": a.statistic / 250000, "mwu_idle_vs_moderate_p": a.pvalue,
            "P(moderate>heavy)": b.statistic / 250000, "mwu_moderate_vs_heavy_p": b.pvalue,
            "fisher_over1ms_heavy_vs_moderate_p": fe.pvalue,
        })
TESTS = pd.DataFrame(rows)
TESTS.to_csv(f"{TAB_DIR}/load_effect_tests.csv", index=False, float_format="%.4g")

# Pooled tail counts.
rows = []
for env in ENVS:
    for l in LOADS:
        allx = np.concatenate([X[env, d, l] for d in DELAYS])
        rows.append({"env": env, "load": l, "n": len(allx),
                     "n_over_1ms": int((allx > 1000).sum()),
                     "pct_over_1ms": 100 * (allx > 1000).mean(),
                     "pct_below_50us": 100 * (allx < 50).mean(),
                     "max_us": allx.max()})
POOL = pd.DataFrame(rows)
POOL.to_csv(f"{TAB_DIR}/pooled_tail.csv", index=False, float_format="%.3f")

print(MAIN[["env", "delay", "load", "min_us", "median_us", "median_ci_lo", "median_ci_hi", "iqr_us",
            "p99_us", "p99_ci_lo", "p99_ci_hi", "max_us", "pct_over_1ms", "pct_below_50us",
            "top5_share_of_sum_pct"]].round(1).to_string())
print(TESTS.to_string())
print(POOL.round(2).to_string())
print(SUPPT[["variant", "delay", "load", "min_us", "median_us", "median_ci_lo", "median_ci_hi", "iqr_us", "p99_us",
             "max_us", "pct_over_1ms", "pct_below_50us"]].round(1).to_string())

# Temporal structure of the largest native tail run.
x = X["native", "100ms", "heavy"]
idx = np.where(x > 1000)[0] + 1
print("native 100ms heavy: trials >1 ms:", idx.tolist())
print("values:", np.round(x[idx - 1] / 1000, 2).tolist(), "ms")


# ------------------------------------------------------------------
# Figure 1: the measured path
# ------------------------------------------------------------------

def fig_path():
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 64)
    ax.axis("off")

    def box(x, y, w, h, text, fc, fs=6.6):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=0.8",
                                    fc=fc, ec="#444444", lw=0.7))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.3)

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#333333"))

    U, K, H = "#e8eef7", "#f7efe2", "#e9f3ea"
    ax.text(0.5, 61.5, "USER SPACE", fontsize=7, color="#4c72b0", fontweight="bold")
    ax.text(0.5, 44.5, "KERNEL", fontsize=7, color="#b07a2a", fontweight="bold")
    ax.text(0.5, 13.5, "HARDWARE / HYPERVISOR", fontsize=7, color="#3d8050", fontweight="bold")
    ax.axhline(47.5, color="#999999", lw=0.6, ls="--")
    ax.axhline(16.5, color="#999999", lw=0.6, ls="--")

    box(1, 51, 17, 8.5, "t_start =\nclock_gettime()", U)
    box(21, 51, 28, 8.5, "clock_nanosleep(\nCLOCK_MONOTONIC, 0, &req, NULL)", U)
    box(81, 51, 18, 8.5, "t_end =\nclock_gettime()", U)
    ax.text(65, 55.2, "error = (t_end − t_start) − requested", ha="center", va="center",
            fontsize=7, style="italic")

    box(1, 31, 24, 11, "common_nsleep_timens()\n→ hrtimer_nanosleep()\nsoft expiry = T\nhard expiry = T + slack   ①", K)
    box(27.5, 31, 21, 11, "do_nanosleep()\nenqueue in rb-tree,\nschedule(): task sleeps", K)
    box(51, 31, 22, 11, "hrtimer_interrupt()\n__hrtimer_run_queues()\n→ hrtimer_wakeup()   ③", K)
    box(75.5, 31, 23.5, 11, "wake_up_process()\nscheduler selects task,\ncontext switch,\nreturn to user   ④", K)

    box(24, 19.5, 28, 7.5, "clockevents_program_event()\nprogrammed for the hard expiry", K)
    box(24, 4.5, 49, 8, "clock-event device (LAPIC timer / Hyper-V synthetic timer)\n"
                        "CPU may be in an idle state; a vCPU may be descheduled   ②", H)

    arrow(18, 55.2, 21, 55.2)
    arrow(33, 51, 15, 42.3)
    arrow(25, 36.5, 27.5, 36.5)
    arrow(38, 31, 38, 27.3)
    arrow(38, 19.5, 38, 12.8)
    arrow(62, 12.8, 62, 31)
    arrow(73, 36.5, 75.5, 36.5)
    arrow(89, 42.3, 90, 51)
    ax.text(63.5, 22, "timer interrupt", fontsize=6.6, ha="left", va="center")

    ax.text(50, 1, "Delay sources:  ① timer slack (policy, up to 50 µs)    ② idle-state exit / vCPU scheduling    "
                   "③ interrupts-off sections    ④ run-queue wait",
            fontsize=6.3, ha="center", va="center", color="#8a2f2f")
    fig.savefig(f"{FIG_DIR}/fig1_timer_path.png")
    plt.close(fig)


# ------------------------------------------------------------------
# Figure 2: ECDFs, both environments
# ------------------------------------------------------------------

def ecdf(ax, x, **kw):
    s = np.sort(x)
    ax.step(s, np.arange(1, len(s) + 1) / len(s), where="post", **kw)


def fig_ecdf():
    fig, axes = plt.subplots(2, 4, figsize=(7.4, 4.3), sharex=True, sharey=True)
    for r, env in enumerate(ENVS):
        for c, d in enumerate(DELAYS):
            ax = axes[r, c]
            ax.axvline(SLACK_US, color="#888888", lw=0.7, ls=":")
            ax.axvline(1000, color="#888888", lw=0.7, ls="--")
            for l in LOADS:
                ecdf(ax, X[env, d, l], color=COLOR[l], lw=1.1, label=l.capitalize())
            ax.set_xscale("log")
            ax.set_xlim(5, 5e4)
            ax.set_ylim(0, 1.005)
            if r == 0:
                ax.set_title(f"Requested {DELAY_LABEL[d]}")
            if r == 1:
                ax.set_xlabel("Timing error (µs)")
            if c == 0:
                ax.set_ylabel(("Native Fedora" if env == "native" else "WSL2") + "\ncumulative fraction")
    axes[0, 0].legend(loc="lower right", frameon=False, handlelength=1.2)
    axes[0, 3].text(SLACK_US * 0.9, 0.30, "50 µs", rotation=90, fontsize=6.5, ha="right", color="#555555")
    axes[0, 3].text(1000 * 0.9, 0.30, "1 ms", rotation=90, fontsize=6.5, ha="right", color="#555555")
    fig.tight_layout(w_pad=0.6, h_pad=0.8)
    fig.savefig(f"{FIG_DIR}/fig2_ecdf_all_conditions.png")
    plt.close(fig)


# ------------------------------------------------------------------
# Figure 3: median with bootstrap CI
# ------------------------------------------------------------------

def fig_median():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
    for ax, env in zip(axes, ENVS):
        for l in LOADS:
            m = MAIN[(MAIN.env == env) & (MAIN.load == l)].set_index("delay").loc[DELAYS]
            xs = [DELAY_US[d] for d in DELAYS]
            ax.errorbar(xs, m.median_us,
                        yerr=[m.median_us - m.median_ci_lo, m.median_ci_hi - m.median_us],
                        color=COLOR[l], marker="o", ms=4, lw=1.2, capsize=2.5, label=l.capitalize())
        ax.axhline(SLACK_US, color="#888888", lw=0.7, ls=":")
        ax.set_xscale("log")
        ax.set_xticks([100, 1000, 10000, 100000])
        ax.set_xticklabels(["100 µs", "1 ms", "10 ms", "100 ms"])
        ax.set_xlabel("Requested delay")
        ax.set_title(ENV_LABEL[env])
        ax.set_ylim(0, 370)
    axes[0].set_ylabel("Median timing error (µs)")
    axes[0].text(110, SLACK_US - 4, "default timer slack (50 µs)", fontsize=6.8, va="top", color="#555555")
    axes[1].legend(title="Load on other CPUs", frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/fig3_median_ci.png")
    plt.close(fig)


# ------------------------------------------------------------------
# Figure 4: tail frequency
# ------------------------------------------------------------------

def fig_tail():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
    w = 0.26
    for ax, env in zip(axes, ENVS):
        for i, l in enumerate(LOADS):
            m = MAIN[(MAIN.env == env) & (MAIN.load == l)].set_index("delay").loc[DELAYS]
            xs = np.arange(4) + (i - 1) * w
            ax.bar(xs, m.pct_over_1ms, w * 0.92, color=COLOR[l], label=l.capitalize(),
                   yerr=[m.pct_over_1ms - m.pct_over_1ms_lo, m.pct_over_1ms_hi - m.pct_over_1ms],
                   error_kw=dict(lw=0.7, capsize=1.8, ecolor="#333333"))
        ax.set_xticks(np.arange(4))
        ax.set_xticklabels([DELAY_LABEL[d] for d in DELAYS])
        ax.set_xlabel("Requested delay")
        ax.set_title(ENV_LABEL[env])
        ax.set_ylim(0, 7)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Wake-ups later than 1 ms (%)")
    axes[0].legend(frameon=False, loc="upper left", title="Load on other CPUs")
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/fig5_tail_over_1ms.png")
    plt.close(fig)


# ------------------------------------------------------------------
# Figure 5: per-trial traces
# ------------------------------------------------------------------

def fig_trace():
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.5), sharey=True)
    for ax, l in zip(axes, LOADS):
        x = X["native", "100ms", l]
        ax.scatter(np.arange(1, 501), x, s=3.5, color=COLOR[l], linewidths=0)
        ax.axhline(SLACK_US, color="#888888", lw=0.7, ls=":")
        ax.axhline(1000, color="#888888", lw=0.7, ls="--")
        ax.set_yscale("log")
        ax.set_ylim(8, 6e4)
        ax.set_xlabel("Trial number")
        ax.set_title(f"{l.capitalize()} (median {np.median(x):.0f} µs, max {x.max() / 1000:.1f} ms)", fontsize=8)
    axes[0].set_ylabel("Timing error (µs)")
    fig.tight_layout(w_pad=0.5)
    fig.savefig(f"{FIG_DIR}/fig6_trace_native_100ms.png")
    plt.close(fig)


# ------------------------------------------------------------------
# Figure 6: slack / SCHED_FIFO control experiment
# ------------------------------------------------------------------

def fig_control():
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.1), sharex=True, sharey=True)
    for r, l in enumerate(["idle", "heavy"]):
        for c, d in enumerate(["100us", "1ms", "10ms"]):
            ax = axes[r, c]
            ax.axvline(1000, color="#888888", lw=0.7, ls="--")
            for v in ["default", "slack1", "fifo"]:
                ecdf(ax, SUPP[v, d, l], color=VCOLOR[v], lw=1.1, label=VLABEL[v])
            ax.set_xscale("log")
            ax.set_xlim(5, 6e3)
            ax.set_ylim(0, 1.005)
            if r == 0:
                ax.set_title(f"Requested {DELAY_LABEL[d]}")
            if r == 1:
                ax.set_xlabel("Timing error (µs)")
            if c == 0:
                ax.set_ylabel(("Idle" if l == "idle" else "Heavy load") + "\ncumulative fraction")
    fig.tight_layout(w_pad=0.6, h_pad=0.8)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.5, -0.05))
    fig.savefig(f"{FIG_DIR}/fig4_slack_fifo_control.png")
    plt.close(fig)


fig_path()
fig_ecdf()
fig_median()
fig_tail()
fig_trace()
fig_control()
print("Figures written to", FIG_DIR)
