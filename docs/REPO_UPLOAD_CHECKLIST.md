# Repository Submission Checklist

Use this checklist before final submission or presentation sharing.

## Keep In The Repository

These files are part of the final report package:

- `README.md`
- `requirements.txt`
- `src/intermediate_report_exports.py`
- `src/rq1_figure0.py`
- `src/rq2_figure1.py`
- `src/rq3_figure2.py`
- `src/flex_method.py`
- `src/bess_method.py`
- `docs/*.md`
- `rq1/*.png`
- `rq1/*.csv`
- `rq2/*.png`
- `rq2/*.csv`
- `rq3/*.png`
- `rq3/*.csv`

The committed `rq1/`, `rq2/`, and `rq3/` folders are the report-ready output folders.

## Do Not Commit

Do not commit:

- `.DS_Store`
- `__pycache__/`
- `.venv/`
- `outputs/` scratch runs
- local raw demand CSVs larger than GitHub limits
- temporary notebooks or draft exports not used in the final report

The main demand file should stay local:

`data/raw/ukpn-data-centre-demand-profiles.csv`

It is too large for GitHub. The compressed raw profile was removed from the repository as well.

## Regenerate Report Outputs

Run from the repository root:

```bash
source .venv/bin/activate
python src/intermediate_report_exports.py --rq all --year 2025 --output-dir .
```

This writes the report-ready outputs to:

- `rq1/`
- `rq2/`
- `rq3/`

## Quick Validation

Run:

```bash
python -m py_compile src/intermediate_report_exports.py src/rq1_figure0.py src/rq2_figure1.py src/rq3_figure2.py src/flex_method.py src/bess_method.py
git status -sb
```

Check that only intended files are changed before committing.

## Final Report Files To Cite

RQ1:

- `docs/RQ1_GRAPH_GUIDE.md`
- `rq1/figure0_intro_annual_mean_day_all_centres.png`
- `rq1/rq1_profile_answer_summary_2025.csv`
- `rq1/rq1_peak_shaving_opportunity_2025.csv`

RQ2:

- `docs/RQ2_METHOD_NOTES.md`
- `rq2/figure1_flex_intermediate.png`
- `rq2/figure1_flex_intermediate_annual_shift_components.png`
- `rq2/flexibility_summary_intermediate.csv`

RQ3:

- `docs/RQ3_METHOD_NOTES.md`
- `rq3/figure2_flex_bess_10_intermediate.png`
- `rq3/figure2_flex_bess_25_intermediate.png`
- `rq3/bess_summary_intermediate.csv`

Report storyline:

- `docs/FINAL_REPORT_ALIGNMENT_NOTES.md`
- `docs/PAPER_METHOD_COMPARISON.md`

## Commit And Push

When the working tree contains only intended final-report changes:

```bash
git add README.md docs src rq1 rq2 rq3
git commit -m "Update final report documentation"
git push origin main
```
