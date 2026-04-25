# AI Flex Project

## Structure
- `src/` Python analysis code
- `docs/` project notes and report handoff documents
- `outputs/rq1/` default RQ1 figures and CSVs
- `outputs/rq2/` default RQ2 figures and CSVs
- `outputs/rq3/` default RQ3 figures and CSVs
- `data/raw/ukpn-data-centre-demand-profiles.csv` local UKPN demand input

## Run
Activate environment:

```bash
source .venv/bin/activate
```

Run all RQs:

```bash
python src/intermediate_report_exports.py --rq all --year 2025
```

Run one RQ:

```bash
python src/intermediate_report_exports.py --rq rq1 --year 2025
python src/intermediate_report_exports.py --rq rq2 --year 2025
python src/intermediate_report_exports.py --rq rq3 --year 2025
```

Default outputs are written under `outputs/rq1`, `outputs/rq2`, and `outputs/rq3`. Pass `--output-dir <base-dir>` to choose another base directory.

## Input Data
Default demand input:

`data/raw/ukpn-data-centre-demand-profiles.csv`

If your dataset is elsewhere, pass `--input <path>`.

Optional UK price input can be supplied for price-aware BESS dispatch:

```bash
python src/intermediate_report_exports.py --rq rq3 --year 2025 \
  --price-input "data/raw/United Kingdom.csv" \
  --price-timestamp-col "Datetime (UTC)" \
  --price-col "Price (EUR/MWhe)"
```

If `data/raw/United Kingdom.csv` exists, it is used automatically. Without a price file, RQ3 remains peak-first and reports `price_signal_used = False`.

## Current Method
RQ1 and RQ2 report full-year annual mean-day profiles, not single peak days. Flexibility is defined operationally:

- `10%` flex: up to `10%` reduction for a maximum of `3` consecutive peak hours
- `25%` flex: up to `25%` reduction for a maximum of `3` consecutive peak hours
- shifted work is recovered in a fixed off-peak recipient window, `22:00-02:00`

RQ2 exports the main annual mean-day figure plus companion Figure 1 views for annual shift components and an annual mean 48-hour shift window. When the UK price CSV is present, Figure 1 overlays the mean electricity price on a right-hand axis.

RQ3 applies BESS dispatch to the flex-adjusted full-year series and plots an annual mean 48-hour horizon, not exact calendar days. When the UK price CSV is present, Figure 2 overlays the mean electricity price on a right-hand axis. It reports:

- original peak
- residual peak after flexibility
- residual peak after flexibility and BESS

## Docs
- `docs/RQ1_HANDOFF_NOTES.md`
- `docs/RQ2_METHOD_NOTES.md`
- `docs/RQ3_METHOD_NOTES.md`
- `docs/FINAL_REPORT_ALIGNMENT_NOTES.md`
