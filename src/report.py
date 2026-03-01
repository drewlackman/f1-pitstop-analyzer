"""
Generate a self-contained interactive HTML report using Plotly.

The report contains four interactive panels (same layout as analyze.py but
hoverable/zoomable):
  1. Scatter – duration vs lap, coloured by team
  2. Box plot – per-driver distribution
  3. Bar chart – median per team with error bars
  4. Histogram – duration distribution with KDE

Usage:
    python src/report.py
    python src/report.py --csv data/pit_2024_bahrain.csv
    python src/report.py --csv data/pit_2023_italy.csv --out-dir reports/
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.analyze import TEAM_COLOURS, flag_outliers, load_data, team_stats

log = logging.getLogger(__name__)


def _team_colour(team: str) -> str:
    return TEAM_COLOURS.get(team, "#888888")


def build_report(df: pd.DataFrame, title: str) -> "plotly.graph_objects.Figure":  # noqa: F821
    """
    Build a 2×2 Plotly subplot figure from a (flagged) pit stop DataFrame.

    Args:
        df: Pit stop DataFrame with ``is_outlier``, ``driver``, and ``team`` columns.
        title: Race / event label used in the figure title.

    Returns:
        A Plotly Figure object ready to be written to HTML.
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as exc:
        raise ImportError("plotly is required for report generation: pip install plotly") from exc

    teams_present = sorted(df["team"].unique())
    driver_order = (
        df.groupby("driver")["pit_duration"].median().sort_values().index.tolist()
    )

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[
            "Pit Stop Duration by Lap",
            "Per-Driver Distribution",
            "Median Pit Stop per Team",
            "Duration Distribution",
        ],
        vertical_spacing=0.14,
        horizontal_spacing=0.1,
    )

    # ------------------------------------------------------------------
    # Panel 1 – Scatter
    # ------------------------------------------------------------------
    for team in teams_present:
        colour = _team_colour(team)
        subset = df[df["team"] == team]
        normal = subset[~subset["is_outlier"]]
        outlier = subset[subset["is_outlier"]]

        if not normal.empty:
            fig.add_trace(
                go.Scatter(
                    x=normal["lap_number"],
                    y=normal["pit_duration"],
                    mode="markers",
                    name=team,
                    marker=dict(color=colour, size=8, opacity=0.85),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Lap %{x}<br>"
                        "Duration: %{y:.3f}s<extra></extra>"
                    ),
                    customdata=normal[["driver"]].values,
                    legendgroup=team,
                    showlegend=True,
                ),
                row=1,
                col=1,
            )
        if not outlier.empty:
            fig.add_trace(
                go.Scatter(
                    x=outlier["lap_number"],
                    y=outlier["pit_duration"],
                    mode="markers",
                    name=f"{team} (outlier)",
                    marker=dict(color=colour, size=10, symbol="x", opacity=0.9),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b> ⚠ outlier<br>"
                        "Lap %{x}<br>"
                        "Duration: %{y:.3f}s<extra></extra>"
                    ),
                    customdata=outlier[["driver"]].values,
                    legendgroup=team,
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

    # ------------------------------------------------------------------
    # Panel 2 – Box plot per driver
    # ------------------------------------------------------------------
    for driver in driver_order:
        subset = df[df["driver"] == driver]
        team = subset["team"].iloc[0]
        fig.add_trace(
            go.Box(
                y=subset["pit_duration"],
                name=driver,
                marker_color=_team_colour(team),
                boxmean=True,
                hovertemplate="<b>%{x}</b><br>%{y:.3f}s<extra></extra>",
                legendgroup=team,
                showlegend=False,
            ),
            row=1,
            col=2,
        )

    # ------------------------------------------------------------------
    # Panel 3 – Bar: median per team
    # ------------------------------------------------------------------
    tstats = team_stats(df).sort_values("median")
    fig.add_trace(
        go.Bar(
            x=tstats["team"],
            y=tstats["median"],
            error_y=dict(type="data", array=tstats["std"].tolist(), visible=True),
            marker_color=[_team_colour(t) for t in tstats["team"]],
            hovertemplate="<b>%{x}</b><br>Median: %{y:.3f}s<extra></extra>",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # ------------------------------------------------------------------
    # Panel 4 – Histogram + KDE
    # ------------------------------------------------------------------
    clean = df[~df["is_outlier"]]["pit_duration"]
    fig.add_trace(
        go.Histogram(
            x=clean,
            nbinsx=15,
            histnorm="probability density",
            name="Duration",
            marker_color="#4C72B0",
            opacity=0.7,
            hovertemplate="Bin: %{x:.1f}s<br>Density: %{y:.4f}<extra></extra>",
            showlegend=False,
        ),
        row=2,
        col=2,
    )
    mu, sigma = clean.mean(), clean.std()
    x_kde = np.linspace(clean.min() - 1, clean.max() + 1, 300)
    kde = np.exp(-0.5 * ((x_kde - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
    fig.add_trace(
        go.Scatter(
            x=x_kde,
            y=kde,
            mode="lines",
            name=f"KDE  μ={mu:.2f}s  σ={sigma:.2f}s",
            line=dict(color="#C44E52", width=2),
            hovertemplate="x: %{x:.2f}s<br>Density: %{y:.4f}<extra></extra>",
            showlegend=True,
        ),
        row=2,
        col=2,
    )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    fig.update_layout(
        title=dict(text=f"<b>{title} — Pit Stop Analysis</b>", font=dict(size=16)),
        height=800,
        template="plotly_white",
        legend=dict(
            orientation="v",
            x=1.02,
            y=1,
            font=dict(size=10),
        ),
    )
    fig.update_xaxes(title_text="Lap Number", row=1, col=1)
    fig.update_yaxes(title_text="Duration (s)", row=1, col=1)
    fig.update_yaxes(title_text="Duration (s)", row=1, col=2)
    fig.update_xaxes(title_text="Team", row=2, col=1)
    fig.update_yaxes(title_text="Median Duration (s)", row=2, col=1)
    fig.update_xaxes(title_text="Duration (s)", row=2, col=2)
    fig.update_yaxes(title_text="Density", row=2, col=2)

    return fig


def main(args: argparse.Namespace | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Generate an interactive HTML pit stop report using Plotly.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--csv", default="data/pit_2024_bahrain.csv", help="Pit stop CSV")
    parser.add_argument("--out-dir", default="data", help="Output directory for the HTML report")
    parser.add_argument("--verbose", action="store_true")

    if args is None:
        args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    csv_path = Path(args.csv)
    df = load_data(csv_path)
    df = flag_outliers(df)

    stem = csv_path.stem
    parts = stem.split("_", 1)
    title = parts[1].replace("_", " ").title() if len(parts) > 1 else stem

    fig = build_report(df, title)

    out_path = Path(args.out_dir) / f"{stem}_report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path), include_plotlyjs="cdn")
    log.info("Saved HTML report → %s", out_path)
    print(f"Saved report → {out_path}")


if __name__ == "__main__":
    main()
