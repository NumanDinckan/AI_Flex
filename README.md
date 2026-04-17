# AI Flex Project

## Structure
- `src/` Python code
- `docs/` project notes and handoff documents
- `outputs/rq1/` RQ1 figures and CSVs
- `outputs/rq2/` RQ2 figures and CSVs
- `outputs/rq3/` RQ3 figures and CSVs
- `data/raw/ukpn-data-centre-demand-profiles.csv.gz` compressed shared dataset committed to git
- `data/raw/ukpn-data-centre-demand-profiles.csv` optional local uncompressed copy
- `archive/` legacy files

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

## Input Data
Default input path now is:

`data/raw/ukpn-data-centre-demand-profiles.csv.gz`

If your dataset is elsewhere, pass `--input <path>`.
