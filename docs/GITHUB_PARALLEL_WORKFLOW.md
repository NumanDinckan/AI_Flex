# GitHub Parallel Workflow (RQ Split)

This repository is now split so 3 developers can work in parallel with minimal merge conflicts.

## Ownership Split

- `rq1_figure0.py`
  - Owner: RQ1 developer
  - Scope: Figure 0 (`figure0_intro_annual_mean_day_all_centres.png`)
- `rq2_figure1.py`
  - Owner: RQ2 developer
  - Scope: Figure 1 set (`figure1_flex_intermediate*.png`) and flexibility summary (`flexibility_summary_intermediate.csv`)
- `rq3_figure2.py`
  - Owner: RQ3 developer
  - Scope: Figure 2 outputs (`figure2_flex_bess_10_intermediate.png`, `figure2_flex_bess_25_intermediate.png`) and BESS summary (`bess_summary_intermediate.csv`)

Shared logic:

- `intermediate_report_exports.py` (single orchestrator + core analysis engine)
- `rq2_figure1.py` helper functions (`apply_zoomed_ylim`, `apply_granular_x_axis`, `add_peak_valley_shading`) are reused by `rq3_figure2.py`

## Branching Strategy

Create one branch per RQ from `main`:

```bash
git checkout main
git pull
git checkout -b feature/rq1-figure0

# or
# feature/rq2-figure1
# feature/rq3-figure2
```

## How Each Developer Runs Their Scope

RQ1:

```bash
python3 rq1_figure0.py --year 2025
```

RQ2:

```bash
python3 rq2_figure1.py --year 2025
```

RQ3:

```bash
python3 rq3_figure2.py --year 2025
```

Integration (all outputs):

```bash
python3 intermediate_report_exports.py --rq all --year 2025
```

Or run one RQ through the orchestrator:

```bash
python3 intermediate_report_exports.py --rq rq1 --year 2025
python3 intermediate_report_exports.py --rq rq2 --year 2025
python3 intermediate_report_exports.py --rq rq3 --year 2025
```

## Merge Order Recommendation

1. Merge `feature/rq1-figure0` into `main`.
2. Merge `feature/rq2-figure1` into `main`.
3. Rebase `feature/rq3-figure2` on latest `main`, then merge.
4. Run integration command and commit any final output updates.

This order keeps likely conflicts low because each RQ has a dedicated file.
