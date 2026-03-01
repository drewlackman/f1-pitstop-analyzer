"""
Compare pit stop performance across multiple races.

Loads two or more race CSVs and produces:
- A grouped bar chart comparing median pit stop per team per race
- A line chart showing each team's median trend across the season
- A printed comparison table

Usage:
    # Compare two specific races
    python src/compare.py --csvs data/pit_2024_bahrain.csv data/pit_2024_saudi_arabia.csv

    # Auto-detect all pit_*.csv files in data/
    python src/compare.py

    # Save to a custom directory
    python src/compare.py --out-dir reports/
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analyze import TEAM_COLOURS, flag_outliers, load_data, team_stats

log = logging.getLogger(__name__)


def _race_label(csv_path: Path) -> str:
    """Derive a short human-readable label from the CSV filename."""
    stem = csv_path.stem  # e.g. "pit_2024_bahrain"
    parts = stem.split("_", 1)
    return parts[1].replace("_", " ").title() if len(parts) > 1 else stem


def load_multiple(csv_paths: list[Path]) -> pd.DataFrame:
    """
    Load and concatenate multiple race CSVs into a single DataFrame.

    A ``race`` column is added to each frame using the filename stem.

    Args:
        csv_paths: List of CSV file paths (output of download_pitstops_openf1.py).

    Returns:
        Concatenated DataFrame with a ``race`` column.
    """
    frames: list[pd.DataFrame] = []
    for p in csv_paths:
        p = Path(p)
        df = load_data(p)
        df = flag_outliers(df)
        df["race"] = _race_label(p)
        frames.append(df)
        log.info("Loaded %d stops from %s", len(df), p.name)

    combined = pd.concat(frames, ignore_index=True)
    log.info("Combined: %d stops across %d races", len(combined), len(csv_paths))
    return combined


def compare_teams(combined: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-team median pit stop for each race.

    Args:
        combined: Output of :func:`load_multiple`.

    Returns:
        Pivot table – rows are teams, columns are race labels.
    """
    # Exclude flagged outliers before aggregating
    clean = combined[~combined["is_outlier"]]
    pivot = (
        clean.groupby(["team", "race"])["pit_duration"]
        .median()
        .unstack(level="race")
    )
    return pivot


def _team_colour(team: str) -> str:
    return TEAM_COLOURS.get(team, "#888888")


def plot_comparison(pivot: pd.DataFrame, out_path: Path) -> None:
    """
    Produce and save a 2-panel comparison figure.

    Panel 1 – Grouped bar chart: median pit stop per team, one bar group per race.
    Panel 2 – Line chart: each team's median across the season (trend).

    Args:
        pivot: Output of :func:`compare_teams` (teams × races).
        out_path: Destination PNG path.
    """
    races = pivot.columns.tolist()
    teams = pivot.index.tolist()
    n_races = len(races)
    n_teams = len(teams)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Multi-Race Pit Stop Comparison", fontsize=13, fontweight="bold")

    # ------------------------------------------------------------------
    # Panel 1 – Grouped bar chart
    # ------------------------------------------------------------------
    x = np.arange(n_teams)
    width = 0.8 / max(n_races, 1)
    offsets = np.linspace(-(n_races - 1) / 2, (n_races - 1) / 2, n_races) * width

    for race, offset in zip(races, offsets):
        vals = [pivot.loc[t, race] if race in pivot.columns else float("nan") for t in teams]
        ax1.bar(
            x + offset,
            vals,
            width=width * 0.9,
            label=race,
            alpha=0.85,
            edgecolor="black",
            linewidth=0.4,
        )

    ax1.set_xticks(x)
    ax1.set_xticklabels(teams, rotation=35, ha="right", fontsize=8)
    ax1.set_ylabel("Median Pit Duration (s)")
    ax1.set_title("Median per Team by Race")
    ax1.legend(fontsize=8)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.4)

    # ------------------------------------------------------------------
    # Panel 2 – Line chart (season trend)
    # ------------------------------------------------------------------
    for team in teams:
        row = [pivot.loc[team, r] if r in pivot.columns else float("nan") for r in races]
        colour = _team_colour(team)
        ax2.plot(
            races,
            row,
            marker="o",
            label=team,
            color=colour,
            linewidth=1.8,
            markersize=6,
        )

    ax2.set_xlabel("Race")
    ax2.set_ylabel("Median Pit Duration (s)")
    ax2.set_title("Season Trend by Team")
    ax2.tick_params(axis="x", rotation=25)
    ax2.legend(fontsize=7, ncol=2, loc="upper right")
    ax2.grid(True, linestyle="--", alpha=0.4)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved comparison chart → %s", out_path)


def print_comparison(pivot: pd.DataFrame) -> None:
    """Print the team-by-race median table to stdout."""
    sep = "─" * max(60, 20 + 12 * len(pivot.columns))
    print(f"\n{sep}")
    print("  Median Pit Stop by Team & Race (seconds, outliers excluded)")
    print(sep)

    races = pivot.columns.tolist()
    header = f"  {'Team':<16}" + "".join(f"{r:>14}" for r in races)
    print(header)
    print("  " + "-" * (len(header) - 2))

    for team in pivot.index:
        row_str = f"  {team:<16}"
        for race in races:
            val = pivot.loc[team, race]
            row_str += f"  {val:>10.3f}  " if not pd.isna(val) else f"  {'n/a':>10}  "
        print(row_str)

    print(sep)


def _auto_detect_csvs(data_dir: Path) -> list[Path]:
    """Return all pit_*.csv files in *data_dir*, sorted by name."""
    csvs = sorted(data_dir.glob("pit_*.csv"))
    return csvs


def main(args: argparse.Namespace | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Compare F1 pit stop performance across multiple races.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--csvs",
        nargs="+",
        default=None,
        metavar="CSV",
        help="Race CSV files to compare. Defaults to all pit_*.csv in --data-dir.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory to auto-detect pit_*.csv files from (used when --csvs is omitted).",
    )
    parser.add_argument("--out-dir", default="data", help="Output directory for plots.")
    parser.add_argument("--no-plot", action="store_true", help="Skip generating comparison charts.")
    parser.add_argument("--verbose", action="store_true")

    if args is None:
        args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.csvs:
        csv_paths = [Path(p) for p in args.csvs]
    else:
        csv_paths = _auto_detect_csvs(Path(args.data_dir))

    if not csv_paths:
        print("No CSV files found. Run 'make download' first or pass --csvs explicitly.")
        return

    if len(csv_paths) == 1:
        print(f"Only one race found ({csv_paths[0].name}). Download more races to enable comparison.")

    combined = load_multiple(csv_paths)
    pivot = compare_teams(combined)

    print_comparison(pivot)

    if not args.no_plot:
        out_path = Path(args.out_dir) / "comparison_teams.png"
        plot_comparison(pivot, out_path)
        print(f"\nSaved comparison chart → {out_path}")


if __name__ == "__main__":
    main()
