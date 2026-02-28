# f1-pitstop-analyzer

A Python tool that analyzes Formula 1 pit stop timing data to evaluate driver and team performance, consistency, and operational efficiency.

## Features

- **Download** pit stop data from the [OpenF1 API](https://openf1.org/) for any race and year
- **Rich statistics** – fastest, slowest, mean, median, std dev, IQR, per-driver and per-team breakdowns
- **Outlier detection** using the IQR (Tukey) fence method
- **Multi-panel visualization** – scatter plot, per-driver box plot, team bar chart, and duration histogram
- **CLI interface** – fully parameterizable; no need to edit source files
- **24 unit tests** covering all analysis functions

## Requirements

- Python 3.10+
- See `requirements.txt` for Python package dependencies

Install dependencies:

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Download pit stop data

```bash
# Default: 2024 Bahrain Grand Prix (Race session)
python src/download_pitstops_openf1.py

# Different race
python src/download_pitstops_openf1.py --year 2023 --country Italy

# Different session type
python src/download_pitstops_openf1.py --year 2024 --country Monaco --session Qualifying
```

The CSV is saved to `data/pit_<year>_<country>.csv`.

### 2. Analyze and visualize

```bash
# Analyze the default Bahrain 2024 data
python src/analyze.py

# Analyze a different race
python src/analyze.py --csv data/pit_2023_italy.csv

# Save plots to a specific directory
python src/analyze.py --csv data/pit_2024_bahrain.csv --out-dir reports/

# Skip the plot (stats only)
python src/analyze.py --no-plot
```

### Example output

```
────────────────────────────────────────────────────
  2024 Bahrain Grand Prix – Pit Stop Analysis
────────────────────────────────────────────────────
  Total stops : 44  (2 outlier(s) flagged)
  Fastest     : 23.800 s
  Slowest     : 74.700 s
  Mean        : 25.214 s  (outliers excluded)
  Median      : 24.900 s
  Std dev     :  1.432 s
  IQR         : 24.200 – 25.900 s
────────────────────────────────────────────────────

  Per-driver (sorted by median):
  Driver   Team           Stops    Best  Median    Mean     Std
  ─────────────────────────────────────────────────────────────
  HAM      Mercedes           2  24.500  24.550  24.550   0.071
  LEC      Ferrari            2  23.800  24.900  24.900   1.556
  ...

  Per-team (sorted by median):
  Team             Stops    Best  Median    Mean     Std
  ─────────────────────────────────────────────────────
  Mercedes             2  24.500  24.550  24.550   0.071
  Ferrari              2  23.800  24.900  24.900   1.556
  ...
```

The visualization is a 2×2 figure saved alongside the CSV:

| Panel | Description |
|-------|-------------|
| Top-left | Scatter: duration vs lap, coloured by team (×  = outlier) |
| Top-right | Box plot: duration distribution per driver |
| Bottom-left | Bar chart: median pit stop per team with std error bars |
| Bottom-right | Histogram + Gaussian KDE of pit durations |

## Running Tests

```bash
python -m pytest tests/ -v
```

All 24 tests should pass without a network connection (API calls are mocked).

## Project Structure

```
f1-pitstop-analyzer/
├── src/
│   ├── analyze.py                 # Analysis, statistics, and visualization
│   └── download_pitstops_openf1.py # OpenF1 API download script
├── tests/
│   ├── test_analyze.py            # Unit tests for analyze.py
│   └── test_download.py           # Unit tests for download script
├── data/
│   ├── pit_2024_bahrain.csv       # Example downloaded data
│   └── pit_2024_bahrain_analysis.png  # Example output plot
├── requirements.txt
└── README.md
```

## Data Source

Pit stop data is fetched from the [OpenF1 REST API](https://openf1.org/), which provides free, real-time and historical F1 data.

## License

MIT © drewlackman
