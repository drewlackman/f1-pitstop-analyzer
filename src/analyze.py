"""
Analyze F1 pit stop data downloaded from OpenF1.
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def load_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required = {"pit_duration", "lap_number", "driver_number"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return df


def main():
    csv_path = Path("data/pit_2024_bahrain.csv")
    df = load_data(csv_path)

    print(f"Loaded {len(df)} pit stops")

    # Basic stats
    fastest = df.loc[df["pit_duration"].idxmin()]
    avg_time = df["pit_duration"].mean()

    print(f"Fastest pit stop:")
    print(f"  Driver #{int(fastest['driver_number'])}")
    print(f"  Lap {int(fastest['lap_number'])}")
    print(f"  Time {fastest['pit_duration']:.3f} s")

    print(f"\nAverage pit stop time: {avg_time:.3f} s")

    # Plot pit stop times over laps
    plt.figure(figsize=(8, 5))
    plt.scatter(df["lap_number"], df["pit_duration"], alpha=0.7)
    plt.xlabel("Lap Number")
    plt.ylabel("Pit Stop Duration (s)")
    plt.title("Pit Stop Durations by Lap – Bahrain GP 2024")
    plt.grid(True, linestyle="--", alpha=0.4)

    out_path = Path("data/pitstop_times_bahrain_2024.png")
    plt.savefig(out_path, bbox_inches="tight")
    plt.show()

    print(f"\nSaved plot to {out_path}")


if __name__ == "__main__":
    main()