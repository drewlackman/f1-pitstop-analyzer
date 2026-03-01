"""
Reconstruct driver stints and detect strategic undercut/overcut moves.

A *stint* is the stretch of laps a driver completes between pit stops.
An *undercut* is when driver A pits 1-3 laps before driver B (a rival),
gets fresh tyres, and exits the pits in a better position.

Usage:
    python src/stints.py
    python src/stints.py --csv data/pit_2024_bahrain.csv --total-laps 57
    python src/stints.py --csv data/pit_2023_italy.csv --total-laps 53 --no-plot
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

from src.analyze import DRIVER_INFO, TEAM_COLOURS, flag_outliers, load_data

log = logging.getLogger(__name__)

# Bahrain GP 2024 is 57 laps; used as fallback when not supplied via CLI
_BAHRAIN_2024_LAPS = 57


def compute_stints(df: pd.DataFrame, total_laps: int | None = None) -> pd.DataFrame:
    """
    Reconstruct each driver's stints from pit stop lap numbers.

    Args:
        df: Pit stop DataFrame (expects ``driver``, ``team``, ``driver_number``,
            and ``lap_number`` columns).
        total_laps: Number of laps in the race. If *None*, the maximum pit lap
            observed in the data is used as a lower bound for the final stint.

    Returns:
        DataFrame with columns: driver, team, driver_number, stint, start_lap,
        end_lap, length (laps).
    """
    if total_laps is None:
        total_laps = int(df["lap_number"].max())
        log.warning(
            "total_laps not provided; using max pit lap (%d) – final stints may be under-counted",
            total_laps,
        )

    records: list[dict] = []
    for driver_num, grp in df.groupby("driver_number"):
        pit_laps = sorted(grp["lap_number"].tolist())
        driver = grp["driver"].iloc[0]
        team = grp["team"].iloc[0]

        boundaries = [0] + pit_laps + [total_laps]
        for i, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            records.append(
                {
                    "driver_number": int(driver_num),
                    "driver": driver,
                    "team": team,
                    "stint": i + 1,
                    "start_lap": start + 1,
                    "end_lap": int(end),
                    "length": int(end - start),
                }
            )

    result = pd.DataFrame(records).sort_values(["driver", "stint"]).reset_index(drop=True)
    log.info(
        "Reconstructed %d stints across %d drivers",
        len(result),
        result["driver"].nunique(),
    )
    return result


def detect_undercuts(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """
    Flag pairs of drivers who stop within *window* laps of each other.

    When driver A pits 1–*window* laps before driver B, A is attempting an
    undercut — using fresh tyres to close the gap during B's in-lap.

    Args:
        df: Pit stop DataFrame with ``driver``, ``team``, and ``lap_number``.
        window: Lap gap within which two stops are considered strategically linked.

    Returns:
        DataFrame of candidate undercut pairs with columns: driver_a, team_a,
        lap_a, driver_b, team_b, lap_b, gap_laps, move_type.
    """
    stops = df[["driver", "team", "lap_number"]].copy()
    records: list[dict] = []

    for _, row_a in stops.iterrows():
        rivals = stops[
            (stops["driver"] != row_a["driver"])
            & (stops["lap_number"] > row_a["lap_number"])
            & (stops["lap_number"] <= row_a["lap_number"] + window)
        ]
        for _, row_b in rivals.iterrows():
            # Deduplicate: only record each pair once
            key = tuple(sorted([row_a["driver"], row_b["driver"]]))
            lap_key = (key, row_a["lap_number"])
            if not any(
                r.get("_key") == lap_key for r in records
            ):
                records.append(
                    {
                        "driver_a": row_a["driver"],
                        "team_a": row_a["team"],
                        "lap_a": int(row_a["lap_number"]),
                        "driver_b": row_b["driver"],
                        "team_b": row_b["team"],
                        "lap_b": int(row_b["lap_number"]),
                        "gap_laps": int(row_b["lap_number"] - row_a["lap_number"]),
                        "move_type": "undercut_attempt",
                        "_key": lap_key,
                    }
                )

    result = pd.DataFrame(records).drop(columns=["_key"], errors="ignore")
    log.info("Detected %d potential undercut/strategic pairs", len(result))
    return result


def _team_colour(team: str) -> str:
    return TEAM_COLOURS.get(team, "#888888")


def plot_stints(stints: pd.DataFrame, title_prefix: str, out_path: Path) -> None:
    """
    Draw a Gantt-style horizontal bar chart showing each driver's stints.

    Args:
        stints: Output of :func:`compute_stints`.
        title_prefix: Race label for the figure title.
        out_path: Destination PNG path.
    """
    # Sort drivers by their first pit lap (earlier pitters at top)
    driver_order = (
        stints.groupby("driver")["start_lap"].min().sort_values().index.tolist()
    )
    driver_y = {drv: i for i, drv in enumerate(driver_order)}

    fig, ax = plt.subplots(figsize=(13, max(5, len(driver_order) * 0.55)))

    for _, row in stints.iterrows():
        y = driver_y[row["driver"]]
        colour = _team_colour(row["team"])
        ax.barh(
            y,
            row["length"],
            left=row["start_lap"] - 1,
            height=0.6,
            color=colour,
            alpha=0.85,
            edgecolor="white",
            linewidth=0.5,
        )
        # Label stint length if wide enough
        if row["length"] >= 5:
            ax.text(
                row["start_lap"] - 1 + row["length"] / 2,
                y,
                str(row["length"]),
                ha="center",
                va="center",
                fontsize=7,
                color="white",
                fontweight="bold",
            )

    ax.set_yticks(range(len(driver_order)))
    ax.set_yticklabels(driver_order, fontsize=9)
    ax.set_xlabel("Lap Number")
    ax.set_title(f"{title_prefix} – Stint Map", fontweight="bold")
    ax.grid(True, axis="x", linestyle="--", alpha=0.4)

    # Legend: one patch per team
    teams_present = stints["team"].unique()
    patches = [
        mpatches.Patch(color=_team_colour(t), label=t) for t in sorted(teams_present)
    ]
    ax.legend(handles=patches, fontsize=7, ncol=2, loc="lower right")

    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved stint map → %s", out_path)


def print_stint_report(stints: pd.DataFrame, undercuts: pd.DataFrame) -> None:
    """Print stint lengths and undercut candidates to stdout."""
    sep = "─" * 60
    print(f"\n{sep}")
    print("  Stint Reconstruction")
    print(sep)
    print(
        f"  {'Driver':<8} {'Team':<14} {'Stint':>5} {'Start':>6} {'End':>6} {'Laps':>5}"
    )
    print("  " + "-" * 46)
    for _, row in stints.iterrows():
        print(
            f"  {row['driver']:<8} {row['team']:<14} {row['stint']:>5} "
            f"{row['start_lap']:>6} {row['end_lap']:>6} {row['length']:>5}"
        )

    if not undercuts.empty:
        print(f"\n{sep}")
        print("  Potential Undercut Attempts  (gap ≤ 3 laps)")
        print(sep)
        print(f"  {'Driver A':<10} {'Lap A':>6}  {'Driver B':<10} {'Lap B':>6}  {'Gap':>4}")
        print("  " + "-" * 44)
        for _, row in undercuts.iterrows():
            print(
                f"  {row['driver_a']:<10} {row['lap_a']:>6}  "
                f"{row['driver_b']:<10} {row['lap_b']:>6}  {row['gap_laps']:>4}"
            )
    else:
        print("\n  No undercut candidates detected.")

    print(sep)


def main(args: argparse.Namespace | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Reconstruct F1 stints and detect undercut moves.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--csv", default="data/pit_2024_bahrain.csv", help="Pit stop CSV")
    parser.add_argument(
        "--total-laps", type=int, default=None, help="Total race laps (improves final stint accuracy)"
    )
    parser.add_argument("--undercut-window", type=int, default=3, help="Lap gap for undercut detection")
    parser.add_argument("--out-dir", default="data", help="Output directory")
    parser.add_argument("--no-plot", action="store_true", help="Skip generating the stint map")
    parser.add_argument("--verbose", action="store_true")

    if args is None:
        args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    csv_path = Path(args.csv)
    df = load_data(csv_path)
    df = flag_outliers(df)
    # Exclude outliers from stint reconstruction
    df_clean = df[~df["is_outlier"]].copy()

    total_laps = args.total_laps or _BAHRAIN_2024_LAPS
    stints = compute_stints(df_clean, total_laps=total_laps)
    undercuts = detect_undercuts(df_clean, window=args.undercut_window)

    stem = csv_path.stem
    parts = stem.split("_", 1)
    title = parts[1].replace("_", " ").title() if len(parts) > 1 else stem

    print_stint_report(stints, undercuts)

    if not args.no_plot:
        out_path = Path(args.out_dir) / f"{stem}_stints.png"
        plot_stints(stints, title, out_path)
        print(f"\nSaved stint map → {out_path}")


if __name__ == "__main__":
    main()
