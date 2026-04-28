# AI Flex Project

This repository contains the final analysis pipeline and report-ready outputs for the AI data-centre flexibility project.

The project answers three research questions:

- RQ1: What do publicly available data-centre load profiles reveal about variability, peak concentration, and potential flexibility?
- RQ2: How does operational load shifting affect the annual load profile under fixed flexibility definitions?
- RQ3: How much additional peak reduction can a co-located BESS provide after flexibility?

## Repository Structure

- `src/`: Python analysis code.
- `rq1/`: committed report outputs for RQ1.
- `rq2/`: committed report outputs for RQ2.
- `rq3/`: committed report outputs for RQ3.
- `docs/`: final-report notes, graph guides, method explanations, and caveats.
- `data/raw/United Kingdom.csv`: optional UK electricity price input if present locally.
- `data/raw/ukpn-data-centre-demand-profiles.csv`: local demand input, not committed because it is too large for GitHub.

By default, the runner writes to `outputs/`. The report-ready committed files in this repository were generated with `--output-dir .`, so they appear under `rq1/`, `rq2/`, and `rq3/`.

## Run

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Regenerate the committed report outputs:

```bash
python src/intermediate_report_exports.py --rq all --year 2025 --output-dir .
```

Run one research question:

```bash
python src/intermediate_report_exports.py --rq rq1 --year 2025 --output-dir .
python src/intermediate_report_exports.py --rq rq2 --year 2025 --output-dir .
python src/intermediate_report_exports.py --rq rq3 --year 2025 --output-dir .
```

To write into the default `outputs/` folder instead, omit `--output-dir .`.

## Input Data

Default demand input:

`data/raw/ukpn-data-centre-demand-profiles.csv`

If the dataset is elsewhere, pass:

```bash
python src/intermediate_report_exports.py --rq all --year 2025 --output-dir . --input "<path-to-demand-csv>"
```

Optional UK electricity price input:

```bash
python src/intermediate_report_exports.py --rq rq3 --year 2025 --output-dir . \
  --price-input "data/raw/United Kingdom.csv" \
  --price-timestamp-col "Datetime (UTC)" \
  --price-col "Price (EUR/MWhe)"
```

If `data/raw/United Kingdom.csv` exists, it is used automatically. Without a price file, RQ3 remains peak-first and reports `price_signal_used = False`.

## Current Method Summary

RQ1 uses the full-year centre-level profiles to answer variability, peak concentration, and potential flexibility. Figure 0 combines the accepted one-hour load-jump view with an annual load-duration curve, peak-timing histogram, and peak-shaving opportunity curve.

RQ2 uses the full-year half-hour load profile and reports annual mean-day and annual mean 48-hour views. Flexibility is defined operationally:

- `10%` flex: up to `10%` reduction for a maximum of `3` consecutive peak hours.
- `25%` flex: up to `25%` reduction for a maximum of `3` consecutive peak hours.
- shifted load is recovered in the fixed off-peak recipient window `22:00-02:00`.

RQ3 applies BESS dispatch to the RQ2 flex-adjusted full-year series. The battery dispatch is peak-first and, when UK price data is present, price-aware as a secondary objective. Figure 2 shows annual mean 48-hour profiles for the `10%` and `25%` flexibility cases with `4h` and `8h` BESS durations.

## Report-Ready Outputs

RQ1:

- `rq1/figure0_intro_annual_mean_day_all_centres.png`
- `rq1/figure0_intro_annual_mean_day_all_centres_left.png`
- `rq1/figure0_1_rq1_center_load_jumps_2025.png`
- `rq1/rq1_profile_answer_summary_2025.csv`
- `rq1/rq1_peak_shaving_opportunity_2025.csv`
- `rq1/rq1_center_variability_metrics_2025.csv`
- `rq1/rq1_center_variability_bucket_summary_2025.csv`

RQ2:

- `rq2/figure1_flex_intermediate.png`
- `rq2/figure1_flex_intermediate_annual_shift_components.png`
- `rq2/figure1_flex_intermediate_annual_48h_shift_window.png`
- `rq2/flexibility_summary_intermediate.csv`

RQ3:

- `rq3/figure2_flex_bess_10_intermediate.png`
- `rq3/figure2_flex_bess_25_intermediate.png`
- `rq3/bess_summary_intermediate.csv`
- `rq3/scenario_comparison_table_2025.csv`

## Documentation

- `docs/FINAL_REPORT_ALIGNMENT_NOTES.md`: final report and presentation storyline.
- `docs/RQ1_GRAPH_GUIDE.md`: detailed Figure 0 and RQ1 graph explanation.
- `docs/RQ1_HANDOFF_NOTES.md`: compact RQ1 handoff.
- `docs/RQ2_METHOD_NOTES.md`: RQ2 flexibility method and Figure 1 interpretation.
- `docs/RQ3_METHOD_NOTES.md`: RQ3 BESS method, Figure 2 interpretation, and compact scenario comparison table.
- `docs/SCENARIO_COMPARISON_TABLE.md`: report-ready six-column table for flex and BESS scenarios.
- `docs/PROJECT_PROCESS_SUMMARY.md`: step-by-step summary of the full project process.
- `docs/PAPER_METHOD_COMPARISON.md`: comparison with the flexible data-centres whitepaper.
- `docs/REPO_UPLOAD_CHECKLIST.md`: submission and repository hygiene checklist.
- `docs/GITHUB_PARALLEL_WORKFLOW.md`: collaboration and run workflow.

## Key Caveats

- The demand data is expressed as utilisation ratios, not MW.
- RQ1 identifies observed variability and peak concentration; it does not prove contractual or technical flexibility.
- RQ2 is a transparent load-shifting scenario, not a full workload scheduler.
- RQ3 is a peak-first BESS dispatch, not a full tariff, degradation, or investment optimization.
- The UK price signal is used for plotting and secondary BESS dispatch logic; it does not turn the model into a full electricity-bill optimization.
