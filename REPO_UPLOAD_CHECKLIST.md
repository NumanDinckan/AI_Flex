# Repo Upload Checklist

## Delete Before Upload

These should be removed from the repository folder (or at minimum not committed):

- `.DS_Store`
- `__pycache__/`
- `old/__pycache__/`
- `figure0_intro_typical_day_all_centres.png`
- `figure1_flex_intermediate.png`
- `figure2_flex_bess_10_intermediate.png`
- `figure2_flex_bess_25_intermediate.png`
- `flexibility_summary_intermediate.csv`
- `bess_summary_intermediate.csv`

Optional delete (recommended for clean repo):

- `old/` (legacy scripts and notes)

## Must Not Upload To GitHub (size limit)

- `ukpn-data-centre-demand-profiles.csv` (about 579MB)

GitHub blocks files larger than 100MB.

## Keep In Repo

- `intermediate_report_exports.py`
- `rq1_figure0.py`
- `rq2_figure1.py`
- `rq3_figure2.py`
- `GITHUB_PARALLEL_WORKFLOW.md`
- `requirements.txt`
- `.gitignore`

## Quick Cleanup Commands

Run from repo root:

```bash
rm -f .DS_Store
rm -rf __pycache__ old/__pycache__
rm -f figure0_intro_typical_day_all_centres.png
rm -f figure1_flex_intermediate.png
rm -f figure2_flex_bess_10_intermediate.png
rm -f figure2_flex_bess_25_intermediate.png
rm -f flexibility_summary_intermediate.csv
rm -f bess_summary_intermediate.csv
```

If you want to remove legacy files too:

```bash
rm -rf old
```

## Git Init / Upload Steps

```bash
git init
git add .
git commit -m "Initial upload: parallel RQ split"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```
