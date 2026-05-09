# AI Flex

Code-only repository for the AI data-centre flexibility analysis.

## Contents

- `src/`: analysis modules for RQ1, RQ2 flexibility, and RQ3 BESS dispatch.
- `requirements.txt`: Python dependencies.
- `.gitignore`: excludes local data, virtual environments, caches, and generated outputs.

Generated figures and CSVs are intentionally not tracked in this clean repository state.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Data

The raw input files are local-only and ignored by Git:

- `data/raw/ukpn-data-centre-demand-profiles.csv`
- optional price file: `data/raw/United Kingdom.csv`

If the demand file is stored elsewhere, pass it with `--input`.

## Run

Run the full analysis for 2025:

```bash
python src/intermediate_report_exports.py --rq all --year 2025
```

By default, generated outputs are written to `outputs/`, which is ignored by Git.

Run a single research question:

```bash
python src/intermediate_report_exports.py --rq rq1 --year 2025
python src/intermediate_report_exports.py --rq rq2 --year 2025
python src/intermediate_report_exports.py --rq rq3 --year 2025
```

Use an explicit demand input:

```bash
python src/intermediate_report_exports.py --rq all --year 2025 --input "<path-to-demand-csv>"
```

Use an explicit price input:

```bash
python src/intermediate_report_exports.py --rq rq3 --year 2025 \
  --price-input "data/raw/United Kingdom.csv" \
  --price-timestamp-col "Datetime (UTC)" \
  --price-col "Price (EUR/MWhe)"
```

## Notes

- The model uses utilisation ratios, not MW.
- RQ2 flexibility is load-driven; price is excluded from flex source selection.
- RQ3 BESS dispatch is peak-first and uses price only as a secondary dispatch signal when a price file is available.
