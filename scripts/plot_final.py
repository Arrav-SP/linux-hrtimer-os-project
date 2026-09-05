#!/usr/bin/env python3

import csv
import glob
import os
import statistics
import matplotlib.pyplot as plt


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIR = "data/final_wsl2"
OUT_DIR = os.path.join(DATA_DIR, "figures")

os.makedirs(OUT_DIR, exist_ok=True)


# Order of delays in the experiment
delay_order = {
    "100us": 0,
    "1ms": 1,
    "10ms": 2,
    "100ms": 3
}

# Requested delay converted to microseconds
delay_us = {
    "100us": 100,
    "1ms": 1000,
    "10ms": 10000,
    "100ms": 100000
}

# Load levels
load_order = [
    "idle",
    "moderate",
    "heavy"
]


# ============================================================
# READ ALL EXPERIMENTAL DATA
# ============================================================

rows = []

for filename in glob.glob(os.path.join(DATA_DIR, "*.csv")):

    basename = os.path.basename(filename)

    # Ignore any CSV that isn't one of the raw experiment files
    if basename == "wsl2_summary.csv":
        continue

    stem = basename[:-4]

    parts = stem.split("_")

    if len(parts) != 2:
        continue

    delay = parts[0]
    load = parts[1]

    errors = []

    with open(filename, newline="") as f:

        reader = csv.DictReader(f)

        for row in reader:
            error_ns = int(row["error_ns"])

            # Convert nanoseconds → microseconds
            errors.append(error_ns / 1000.0)

    if len(errors) != 500:
        raise ValueError(
            f"{basename}: expected 500 trials, "
            f"found {len(errors)}"
        )

    errors.sort()

    n = len(errors)

    # --------------------------------------------------------
    # Percentile function
    # --------------------------------------------------------

    def percentile(p):

        position = p * (n - 1)

        lower = int(position)

        upper = min(
            lower + 1,
            n - 1
        )

        if lower == upper:
            return errors[lower]

        fraction = position - lower

        return (
            errors[lower]
            + fraction
            * (errors[upper] - errors[lower])
        )

    # --------------------------------------------------------
    # Store statistics
    # --------------------------------------------------------

    rows.append({

        "delay": delay,

        "load": load,

        "delay_us": delay_us[delay],

        "errors": errors,

        "mean": statistics.mean(errors),

        "p50": percentile(0.50),

        "p90": percentile(0.90),

        "p95": percentile(0.95),

        "p99": percentile(0.99),

        "min": min(errors),

        "max": max(errors),

        "stdev": statistics.pstdev(errors)

    })


# ============================================================
# SORT RESULTS
# ============================================================

rows.sort(
    key=lambda r: (
        delay_order[r["delay"]],
        load_order.index(r["load"])
    )
)


# ============================================================
# GENERAL PLOT SETTINGS
# ============================================================

plt.rcParams.update({
    "font.size": 11
})


# ============================================================
# FIGURE 1
# MEAN ERROR + STANDARD DEVIATION
# ============================================================

fig, ax = plt.subplots(
    figsize=(9, 5.5)
)

for load in load_order:

    condition_rows = [
        r for r in rows
        if r["load"] == load
    ]

    x = [
        r["delay_us"]
        for r in condition_rows
    ]

    y = [
        r["mean"]
        for r in condition_rows
    ]

    error = [
        r["stdev"]
        for r in condition_rows
    ]

    ax.errorbar(
        x,
        y,
        yerr=error,
        marker="o",
        capsize=4,
        label=load.capitalize()
    )


ax.set_xscale("log")

ax.set_xlabel(
    "Requested delay (µs)"
)

ax.set_ylabel(
    "Timing error (µs)"
)

ax.set_title(
    "Mean timing error with standard-deviation error bars"
)

ax.grid(
    True,
    which="both",
    alpha=0.25
)

ax.legend(
    title="CPU load"
)

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUT_DIR,
        "figure1_mean_error.png"
    ),
    dpi=300
)

plt.close(fig)


# ============================================================
# FIGURE 2
# MEDIAN ERROR
# ============================================================

fig, ax = plt.subplots(
    figsize=(9, 5.5)
)

for load in load_order:

    condition_rows = [
        r for r in rows
        if r["load"] == load
    ]

    x = [
        r["delay_us"]
        for r in condition_rows
    ]

    y = [
        r["p50"]
        for r in condition_rows
    ]

    ax.plot(
        x,
        y,
        marker="o",
        label=load.capitalize()
    )


ax.set_xscale("log")

ax.set_xlabel(
    "Requested delay (µs)"
)

ax.set_ylabel(
    "Median timing error (µs)"
)

ax.set_title(
    "Median timing error across requested delays"
)

ax.grid(
    True,
    which="both",
    alpha=0.25
)

ax.legend(
    title="CPU load"
)

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUT_DIR,
        "figure2_median_error.png"
    ),
    dpi=300
)

plt.close(fig)


# ============================================================
# FIGURE 3
# P99 ERROR
# ============================================================

fig, ax = plt.subplots(
    figsize=(9, 5.5)
)

for load in load_order:

    condition_rows = [
        r for r in rows
        if r["load"] == load
    ]

    x = [
        r["delay_us"]
        for r in condition_rows
    ]

    y = [
        r["p99"]
        for r in condition_rows
    ]

    ax.plot(
        x,
        y,
        marker="o",
        label=load.capitalize()
    )


ax.set_xscale("log")

ax.set_xlabel(
    "Requested delay (µs)"
)

ax.set_ylabel(
    "p99 timing error (µs)"
)

ax.set_title(
    "99th-percentile timing error"
)

ax.grid(
    True,
    which="both",
    alpha=0.25
)

ax.legend(
    title="CPU load"
)

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUT_DIR,
        "figure3_p99_error.png"
    ),
    dpi=300
)

plt.close(fig)


# ============================================================
# FIGURE 4
# MAXIMUM ERROR
# ============================================================

fig, ax = plt.subplots(
    figsize=(9, 5.5)
)

for load in load_order:

    condition_rows = [
        r for r in rows
        if r["load"] == load
    ]

    x = [
        r["delay_us"]
        for r in condition_rows
    ]

    y = [
        r["max"]
        for r in condition_rows
    ]

    ax.plot(
        x,
        y,
        marker="o",
        label=load.capitalize()
    )


ax.set_xscale("log")

ax.set_xlabel(
    "Requested delay (µs)"
)

ax.set_ylabel(
    "Maximum timing error (µs)"
)

ax.set_title(
    "Maximum observed timing error"
)

ax.grid(
    True,
    which="both",
    alpha=0.25
)

ax.legend(
    title="CPU load"
)

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUT_DIR,
        "figure4_max_error.png"
    ),
    dpi=300
)

plt.close(fig)


# ============================================================
# FIGURE 5
# BOXPLOT FOR 1 ms CONDITION
# ============================================================

fig, ax = plt.subplots(
    figsize=(8, 5.5)
)

box_data = []

labels = []

for load in load_order:

    condition = next(
        r for r in rows
        if (
            r["delay"] == "1ms"
            and
            r["load"] == load
        )
    )

    box_data.append(
        condition["errors"]
    )

    labels.append(
        load.capitalize()
    )


ax.boxplot(box_data, tick_labels=labels, showfliers=False)

ax.set_xlabel(
    "CPU load"
)

ax.set_ylabel(
    "Timing error (µs)"
)

ax.set_title(
    "Timing-error distribution for 1 ms requested delay"
)

ax.grid(
    True,
    axis="y",
    alpha=0.25
)

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUT_DIR,
        "figure5_1ms_boxplot.png"
    ),
    dpi=300
)

plt.close(fig)


# ============================================================
# DONE
# ============================================================

print()
print("=" * 60)
print("GRAPH GENERATION COMPLETE")
print("=" * 60)

print()

for filename in sorted(
    glob.glob(
        os.path.join(
            OUT_DIR,
            "*.png"
        )
    )
):

    print(filename)

print()
print("Five report-quality figures created.")
print()
