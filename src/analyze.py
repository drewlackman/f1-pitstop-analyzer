"""
Analyze F1 pit stop data downloaded from OpenF1.

Produces per-race and per-driver statistics plus a multi-panel visualization.

Usage:
    python src/analyze.py
    python src/analyze.py --csv data/pit_2024_bahrain.csv
    python src/analyze.py --csv data/pit_2023_italy.csv --out-dir data/plots
    python src/analyze.py --csv data/pit_2024_bahrain.csv --no-plot
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# F1 2024 driver number → (abbreviation, team) mapping
# ---------------------------------------------------------------------------
DRIVER_INFO: dict[int, tuple[str, str]] = {
    1: ("VER", "Red Bull"),
    11: ("PER", "Red Bull"),
    16: ("LEC", "Ferrari"),
    55: ("SAI", "Ferrari"),
    44: ("HAM", "Mercedes"),
    63: ("RUS", "Mercedes"),
    14: ("ALO", "Aston Martin"),
    18: ("STR", "Aston Martin"),
    4: ("NOR", "McLaren"),
    81: ("PIA", "McLaren"),
    10: ("GAS", "Alpine"),
    31: ("OCO", "Alpine"),
    23: ("ALB", "Williams"),
    2: ("SAR", "Williams"),
    77: ("BOT", "Sauber"),
    24: ("ZHO", "Sauber"),
    22: ("TSU", "RB"),
    3: ("RIC", "RB"),
    20: ("MAG", "Haas"),
    27: ("HUL", "Haas"),
}

# Palette: one colour per team for consistent plotting
TEAM_COLOURS: dict[str, str] = {
    "Red Bull": "#3671C6",
    "Ferrari": "#E8002D",
    "Mercedes": "#27F4D2",
    "McLaren": "#FF8000",
    "Aston Martin": "#229971",
    "Alpine": "#FF87BC",
    "Williams": "#64C4FF",
    "Sauber": "#52E252",
    "RB": "#6692FF",
    "Haas": "#B6BABD",
}

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading and cleaning
# ---------------------------------------------------------------------------

def load_data(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate the pit stop CSV produced by download_pitstops_openf1.py.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        Cleaned DataFrame with added helper columns.

    Raises:
        FileNotFoundError: If the CSV does not exist.
        ValueError: If required columns are missing.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    log.info("Loaded %d rows from %s", len(df), csv_path)

    required = {"pit_duration", "lap_number", "driver_number"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Drop rows where pit_duration is null or non-positive
    before = len(df)
    df = df.dropna(subset=["pit_duration"])
    df = df[df["pit_duration"] > 0]
    dropped = before - len(df)
    if dropped:
        log.warning("Dropped %d rows with invalid pit_duration", dropped)

    df["driver_number"] = df["driver_number"].astype(int)
    df["lap_number"] = df["lap_number"].astype(int)

    # Attach driver abbreviation and team
    df["driver"] = df["driver_number"].map(lambda n: DRIVER_INFO.get(n, (f"#{n}", "Unknown"))[0])
    df["team"] = df["driver_number"].map(lambda n: DRIVER_INFO.get(n, (f"#{n}", "Unknown"))[1])

    return df


def flag_outliers(df: pd.DataFrame, column: str = "pit_duration", iqr_scale: float = 1.5) -> pd.DataFrame:
    """
    Add an ``is_outlier`` boolean column using the IQR fence method.

    Args:
        df: Pit stop DataFrame.
        column: Column to inspect.
        iqr_scale: Multiplier for the IQR fence (default 1.5 = Tukey's rule).

    Returns:
        DataFrame with ``is_outlier`` column added (in-place copy).
    """
    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - iqr_scale * iqr
    upper = q3 + iqr_scale * iqr
    df = df.copy()
    df["is_outlier"] = (df[column] < lower) | (df[column] > upper)
    n_out = df["is_outlier"].sum()
    if n_out:
        log.info("Flagged %d outlier(s) outside [%.1f s, %.1f s]", n_out, lower, upper)
    return df


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def race_summary(df: pd.DataFrame) -> dict[str, float]:
    """Return top-level race pit stop statistics."""
    clean = df[~df["is_outlier"]] if "is_outlier" in df.columns else df
    return {
        "count": len(df),
        "outliers": int(df["is_outlier"].sum()) if "is_outlier" in df.columns else 0,
        "min": df["pit_duration"].min(),
        "max": df["pit_duration"].max(),
        "mean": clean["pit_duration"].mean(),
        "median": clean["pit_duration"].median(),
        "std": clean["pit_duration"].std(),
        "p25": clean["pit_duration"].quantile(0.25),
        "p75": clean["pit_duration"].quantile(0.75),
    }


def driver_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-driver pit stop statistics, sorted by median duration.

    Args:
        df: Pit stop DataFrame (expects ``driver``, ``team``, and ``pit_duration`` columns).

    Returns:
        DataFrame indexed by driver abbreviation.
    """
    g = df.groupby(["driver", "team"])["pit_duration"]
    stats = pd.DataFrame({
        "stops": g.count(),
        "best": g.min(),
        "worst": g.max(),
        "mean": g.mean(),
        "median": g.median(),
        "std": g.std().fillna(0),
    }).reset_index()
    stats = stats.sort_values("median").reset_index(drop=True)
    return stats


def team_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-team pit stop statistics, sorted by median duration.

    Args:
        df: Pit stop DataFrame.

    Returns:
        DataFrame indexed by team name.
    """
    g = df.groupby("team")["pit_duration"]
    stats = pd.DataFrame({
        "stops": g.count(),
        "best": g.min(),
        "mean": g.mean(),
        "median": g.median(),
        "std": g.std().fillna(0),
    }).reset_index()
    stats = stats.sort_values("median").reset_index(drop=True)
    return stats


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

def _team_colour(team: str) -> str:
    return TEAM_COLOURS.get(team, "#888888")


def plot_analysis(df: pd.DataFrame, title_prefix: str, out_path: Path) -> None:
    """
    Produce and save a 2×2 multi-panel analysis figure.

    Panels:
        1. Scatter: pit duration vs lap number, coloured by team, outliers marked.
        2. Box plot: pit duration distribution per driver.
        3. Bar chart: median pit stop per team with error bars (std).
        4. Histogram: overall pit duration distribution with KDE.

    Args:
        df: Cleaned pit stop DataFrame with ``is_outlier``, ``driver``, and ``team`` columns.
        title_prefix: Race/event label used in the figure title.
        out_path: File path (PNG) for saving.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"{title_prefix} – Pit Stop Analysis", fontsize=14, fontweight="bold", y=0.98)

    # ------------------------------------------------------------------
    # Panel 1 – Scatter: duration vs lap, coloured by team
    # ------------------------------------------------------------------
    ax1 = axes[0, 0]
    teams_present = df["team"].unique()
    for team in sorted(teams_present):
        subset = df[df["team"] == team]
        normal = subset[~subset["is_outlier"]]
        outlier = subset[subset["is_outlier"]]
        colour = _team_colour(team)
        ax1.scatter(
            normal["lap_number"], normal["pit_duration"],
            label=team, color=colour, alpha=0.8, s=60, zorder=3,
        )
        if not outlier.empty:
            ax1.scatter(
                outlier["lap_number"], outlier["pit_duration"],
                color=colour, marker="x", s=100, linewidths=2, zorder=4,
            )

    ax1.set_xlabel("Lap Number")
    ax1.set_ylabel("Duration (s)")
    ax1.set_title("Pit Stop Duration by Lap")
    ax1.grid(True, linestyle="--", alpha=0.4)
    ax1.legend(fontsize=6, ncol=2, loc="upper right")

    # ------------------------------------------------------------------
    # Panel 2 – Box plot per driver
    # ------------------------------------------------------------------
    ax2 = axes[0, 1]
    drv_order = (
        df.groupby("driver")["pit_duration"].median()
        .sort_values()
        .index.tolist()
    )
    driver_colours = [
        _team_colour(df[df["driver"] == d]["team"].iloc[0])
        for d in drv_order
    ]
    box_data = [df[df["driver"] == d]["pit_duration"].values for d in drv_order]
    bp = ax2.boxplot(box_data, patch_artist=True, vert=True, widths=0.6)
    for patch, col in zip(bp["boxes"], driver_colours):
        patch.set_facecolor(col)
        patch.set_alpha(0.8)
    ax2.set_xticks(range(1, len(drv_order) + 1))
    ax2.set_xticklabels(drv_order, rotation=45, ha="right", fontsize=8)
    ax2.set_ylabel("Duration (s)")
    ax2.set_title("Per-Driver Distribution")
    ax2.grid(True, axis="y", linestyle="--", alpha=0.4)

    # ------------------------------------------------------------------
    # Panel 3 – Bar chart: median per team with std error bars
    # ------------------------------------------------------------------
    ax3 = axes[1, 0]
    tstats = team_stats(df).sort_values("median")
    colours = [_team_colour(t) for t in tstats["team"]]
    bars = ax3.bar(
        tstats["team"], tstats["median"],
        yerr=tstats["std"], capsize=4,
        color=colours, alpha=0.85, edgecolor="black", linewidth=0.5,
    )
    # Annotate each bar with median value
    for bar, val in zip(bars, tstats["median"]):
        ax3.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.4,
            f"{val:.1f}s",
            ha="center", va="bottom", fontsize=7.5,
        )
    ax3.set_xlabel("Team")
    ax3.set_ylabel("Median Duration (s)")
    ax3.set_title("Median Pit Stop per Team  (error bar = 1 std dev)")
    ax3.set_xticklabels(tstats["team"], rotation=30, ha="right", fontsize=8)
    ax3.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax3.grid(True, axis="y", linestyle="--", alpha=0.4)

    # ------------------------------------------------------------------
    # Panel 4 – Histogram with KDE overlay
    # ------------------------------------------------------------------
    ax4 = axes[1, 1]
    clean = df[~df["is_outlier"]]["pit_duration"]
    ax4.hist(clean, bins=15, color="#4C72B0", alpha=0.7, edgecolor="white", density=True)

    # Simple Gaussian KDE
    x_range = np.linspace(clean.min() - 1, clean.max() + 1, 300)
    mu, sigma = clean.mean(), clean.std()
    kde = np.exp(-0.5 * ((x_range - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
    ax4.plot(x_range, kde, color="#C44E52", linewidth=2, label=f"μ={mu:.2f}s  σ={sigma:.2f}s")
    ax4.axvline(mu, color="#C44E52", linestyle="--", alpha=0.7)
    ax4.set_xlabel("Duration (s)")
    ax4.set_ylabel("Density")
    ax4.set_title("Pit Stop Duration Distribution  (outliers excluded)")
    ax4.legend(fontsize=9)
    ax4.grid(True, linestyle="--", alpha=0.4)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved figure → %s", out_path)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(df: pd.DataFrame, title: str) -> None:
    """Print a formatted text report to stdout."""
    summary = race_summary(df)
    drv = driver_stats(df)
    tm = team_stats(df)

    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)
    print(f"  Total stops : {summary['count']}  ({summary['outliers']} outlier(s) flagged)")
    print(f"  Fastest     : {summary['min']:.3f} s")
    print(f"  Slowest     : {summary['max']:.3f} s")
    print(f"  Mean        : {summary['mean']:.3f} s  (outliers excluded)")
    print(f"  Median      : {summary['median']:.3f} s")
    print(f"  Std dev     : {summary['std']:.3f} s")
    print(f"  IQR         : {summary['p25']:.3f} – {summary['p75']:.3f} s")
    print(sep)

    print("\n  Per-driver (sorted by median):")
    print(f"  {'Driver':<8} {'Team':<14} {'Stops':>5} {'Best':>7} {'Median':>7} {'Mean':>7} {'Std':>6}")
    print("  " + "-" * 56)
    for _, row in drv.iterrows():
        print(
            f"  {row['driver']:<8} {row['team']:<14} {int(row['stops']):>5} "
            f"{row['best']:>7.3f} {row['median']:>7.3f} {row['mean']:>7.3f} {row['std']:>6.3f}"
        )

    print(f"\n  Per-team (sorted by median):")
    print(f"  {'Team':<16} {'Stops':>5} {'Best':>7} {'Median':>7} {'Mean':>7} {'Std':>6}")
    print("  " + "-" * 52)
    for _, row in tm.iterrows():
        print(
            f"  {row['team']:<16} {int(row['stops']):>5} "
            f"{row['best']:>7.3f} {row['median']:>7.3f} {row['mean']:>7.3f} {row['std']:>6.3f}"
        )
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(args: argparse.Namespace | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Analyze F1 pit stop data and generate visualizations.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--csv",
        default="data/pit_2024_bahrain.csv",
        help="Path to the pit stop CSV file.",
    )
    parser.add_argument(
        "--out-dir",
        default="data",
        help="Directory for saving output plots.",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip generating the visualization.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default=None,
        metavar="FORMAT",
        help="Export driver and team stats as 'csv' or 'json' alongside the plot.",
    )

    if args is None:
        args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    csv_path = Path(args.csv)
    df = load_data(csv_path)
    df = flag_outliers(df)

    # Derive a human-readable title from the filename
    stem = csv_path.stem  # e.g. "pit_2024_bahrain"
    parts = stem.split("_", 1)
    title = parts[1].replace("_", " ").title() if len(parts) > 1 else stem

    print_report(df, title)

    if not args.no_plot:
        out_path = Path(args.out_dir) / f"{stem}_analysis.png"
        plot_analysis(df, title, out_path)
        print(f"\nSaved plot → {out_path}")

    if args.format:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        drv = driver_stats(df)
        tm = team_stats(df)
        if args.format == "csv":
            drv_path = out_dir / f"{stem}_drivers.csv"
            tm_path = out_dir / f"{stem}_teams.csv"
            drv.to_csv(drv_path, index=False)
            tm.to_csv(tm_path, index=False)
            print(f"Saved driver stats → {drv_path}")
            print(f"Saved team stats   → {tm_path}")
        elif args.format == "json":
            import json
            drv_path = out_dir / f"{stem}_drivers.json"
            tm_path = out_dir / f"{stem}_teams.json"
            drv_path.write_text(json.dumps(drv.to_dict(orient="records"), indent=2))
            tm_path.write_text(json.dumps(tm.to_dict(orient="records"), indent=2))
            print(f"Saved driver stats → {drv_path}")
            print(f"Saved team stats   → {tm_path}")


if __name__ == "__main__":
    main()
