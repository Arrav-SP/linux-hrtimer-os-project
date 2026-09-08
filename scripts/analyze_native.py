import csv
import glob
import os
import statistics

DATA_DIR = "data"
OUTPUT_DIR = "data/native_analysis/analysis"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def percentile(values, p):
    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)

    if lower == upper:
        return values[lower]

    fraction = position - lower
    return values[lower] + fraction * (values[upper] - values[lower])


results = []

for filename in sorted(glob.glob(os.path.join(DATA_DIR, "native_*.csv"))):

    basename = os.path.basename(filename)
    name = basename.replace(".csv", "")

    parts = name.split("_")
    delay_name = parts[1]
    load = parts[2]

    errors = []

    with open(filename, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            errors.append(int(row["error_ns"]))

    if len(errors) != 500:
        raise ValueError(
            f"{basename}: expected 500 trials, found {len(errors)}"
        )

    requested_ns = int(
        open(filename).readline().strip().split(",")[1]
        if False else 0
    )

    # Read requested delay from first data row
    with open(filename, newline="") as f:
        reader = csv.DictReader(f)
        first_row = next(reader)
        requested_ns = int(first_row["requested_ns"])

    results.append({
        "delay": delay_name,
        "requested_ns": requested_ns,
        "requested_us": requested_ns / 1000,
        "load": load,
        "trials": len(errors),

        "mean_error_ns": statistics.mean(errors),
        "median_error_ns": percentile(errors, 0.50),
        "p90_error_ns": percentile(errors, 0.90),
        "p95_error_ns": percentile(errors, 0.95),
        "p99_error_ns": percentile(errors, 0.99),

        "min_error_ns": min(errors),
        "max_error_ns": max(errors),

        "stddev_error_ns": statistics.pstdev(errors),

        "mean_error_us": statistics.mean(errors) / 1000,
        "median_error_us": percentile(errors, 0.50) / 1000,
        "p99_error_us": percentile(errors, 0.99) / 1000,
        "max_error_us": max(errors) / 1000,
    })


# Sort logically by requested delay then load
delay_order = {
    "100us": 0,
    "1ms": 1,
    "10ms": 2,
    "100ms": 3
}

load_order = {
    "idle": 0,
    "moderate": 1,
    "heavy": 2
}

results.sort(
    key=lambda x: (
        delay_order[x["delay"]],
        load_order[x["load"]]
    )
)


# Write full summary CSV
output_file = os.path.join(
    OUTPUT_DIR,
    "wsl2_summary.csv"
)

fields = list(results[0].keys())

with open(output_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(results)


# Print report-friendly table
print()
print("=" * 110)
print("NATIVE FEDORA HRTIMER EXPERIMENT SUMMARY")
print("=" * 110)

print(
    f"{'Delay':<8}"
    f"{'Load':<10}"
    f"{'Mean(us)':>12}"
    f"{'p50(us)':>12}"
    f"{'p95(us)':>12}"
    f"{'p99(us)':>12}"
    f"{'Max(us)':>12}"
)

print("-" * 110)

for r in results:

    print(
        f"{r['delay']:<8}"
        f"{r['load']:<10}"
        f"{r['mean_error_us']:>12.2f}"
        f"{r['median_error_us']:>12.2f}"
        f"{r['p95_error_ns']/1000:>12.2f}"
        f"{r['p99_error_us']:>12.2f}"
        f"{r['max_error_us']:>12.2f}"
    )

print("=" * 110)

print()
print(f"Full summary written to:")
print(output_file)

print()
print("Total experimental conditions:", len(results))
print("Total observations:", sum(r["trials"] for r in results))
