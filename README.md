# f1-pitstop-analyzer

A Python toolkit for analyzing Formula 1 pit stop timing data sourced from the [OpenF1 API](https://openf1.org/).

## Features

| Script | What it does |
|---|---|
| `download_pitstops_openf1.py` | Fetch pit stop data for any race/year from OpenF1 |
| `analyze.py` | Per-driver & per-team stats, outlier detection, 2×2 matplotlib plot |
| `stints.py` | Reconstruct driver stints, Gantt chart, detect undercut attempts |
| `compare.py` | Side-by-side team comparison across multiple races, season trend line |
| `report.py` | Interactive self-contained HTML report (Plotly, hover/zoom) |

**51 unit tests** — no network required (API calls mocked).

## Requirements

- Python 3.10+

```bash
pip install -r requirements.txt
# or
pip install -e ".[dev]"   # after cloning, installs entry-point commands too
```

## Quick Start

### 1. Download

```bash
# Default: 2024 Bahrain GP (Race)
make download

# Any race
make download YEAR=2023 COUNTRY=Italy
make download YEAR=2024 COUNTRY="Saudi Arabia" SESSION=Race
```

Or directly:

```bash
python src/download_pitstops_openf1.py --year 2024 --country Bahrain
```

CSVs are saved to `data/pit_<year>_<country>.csv`.

---

### 2. Analyze a race

```bash
make analyze                                  # default CSV
make analyze CSV=data/pit_2023_italy.csv

# With stats exported to JSON
python src/analyze.py --csv data/pit_2024_bahrain.csv --format json
```

**Outputs:**
- Console table: total stops, outliers flagged, fastest/slowest/mean/median/std, per-driver and per-team breakdown
- `data/<stem>_analysis.png` — 2×2 matplotlib figure (scatter, box plot, team bar chart, histogram + KDE)
- `data/<stem>_drivers.csv` / `_teams.csv` — when `--format csv`
- `data/<stem>_drivers.json` / `_teams.json` — when `--format json`

---

### 3. Stint analysis

```bash
make stints                                   # default CSV, 57-lap race
python src/stints.py --csv data/pit_2024_bahrain.csv --total-laps 57
```

**Outputs:**
- Console table: each driver's stints (start, end, length in laps)
- Potential undercut attempts (drivers who pitted within 3 laps of each other)
- `data/<stem>_stints.png` — Gantt-style horizontal bar chart, coloured by team

---

### 4. Interactive HTML report

```bash
make report
python src/report.py --csv data/pit_2024_bahrain.csv
```

Saves a fully self-contained `data/<stem>_report.html` — open in any browser for hoverable, zoomable versions of all four analysis panels.

---

### 5. Multi-race comparison

```bash
# Auto-detect all pit_*.csv files in data/
make compare

# Specify files explicitly
python src/compare.py --csvs data/pit_2024_bahrain.csv data/pit_2024_saudi_arabia.csv
```

**Outputs:**
- Console table: median pit stop per team for each race
- `data/comparison_teams.png` — grouped bar chart + season trend line chart

---

## Running Tests

```bash
make test
# or
python -m pytest tests/ -v
```

All 51 tests pass with no network calls required.

## Project Structure

```
f1-pitstop-analyzer/
├── .github/
│   └── workflows/
│       └── ci.yml               # Runs tests on Python 3.10 / 3.11 / 3.12
├── src/
│   ├── __init__.py
│   ├── analyze.py               # Core analysis, stats, matplotlib visualization
│   ├── compare.py               # Multi-race comparison
│   ├── download_pitstops_openf1.py
│   ├── report.py                # Interactive Plotly HTML report
│   └── stints.py                # Stint reconstruction + undercut detection
├── tests/
│   ├── conftest.py              # Shared pytest fixtures
│   ├── test_analyze.py
│   ├── test_compare.py
│   ├── test_download.py
│   └── test_stints.py
├── data/
│   └── pit_2024_bahrain.csv     # Example downloaded data
├── Makefile                     # Developer workflow shortcuts
├── pyproject.toml               # Package metadata + entry points
└── requirements.txt
```

## CLI Reference

### `analyze.py`
| Flag | Default | Description |
|---|---|---|
| `--csv` | `data/pit_2024_bahrain.csv` | Input CSV |
| `--out-dir` | `data` | Output directory |
| `--format` | _(none)_ | Export stats: `csv` or `json` |
| `--no-plot` | false | Skip PNG output |
| `--verbose` | false | Debug logging |

### `stints.py`
| Flag | Default | Description |
|---|---|---|
| `--csv` | `data/pit_2024_bahrain.csv` | Input CSV |
| `--total-laps` | 57 | Race distance (improves final stint accuracy) |
| `--undercut-window` | 3 | Lap gap to flag as undercut candidate |
| `--out-dir` | `data` | Output directory |
| `--no-plot` | false | Skip Gantt chart |

### `compare.py`
| Flag | Default | Description |
|---|---|---|
| `--csvs` | _(all `pit_*.csv` in `--data-dir`)_ | Race CSV files |
| `--data-dir` | `data` | Auto-detection directory |
| `--out-dir` | `data` | Output directory |
| `--no-plot` | false | Skip comparison chart |

### `report.py`
| Flag | Default | Description |
|---|---|---|
| `--csv` | `data/pit_2024_bahrain.csv` | Input CSV |
| `--out-dir` | `data` | Output directory |

## Data Source

Pit stop data is fetched from the [OpenF1 REST API](https://openf1.org/) — free, real-time and historical F1 data.

## License

MIT © drewlackman
