# Collaboration And Run Workflow

This project is now organized around one orchestrator and three RQ-specific output modules. The current final-report branch is `main`.

## Main Entry Point

Use the orchestrator for final runs:

```bash
python src/intermediate_report_exports.py --rq all --year 2025 --output-dir .
```

Run one RQ:

```bash
python src/intermediate_report_exports.py --rq rq1 --year 2025 --output-dir .
python src/intermediate_report_exports.py --rq rq2 --year 2025 --output-dir .
python src/intermediate_report_exports.py --rq rq3 --year 2025 --output-dir .
```

## Code Ownership

RQ1:

- code: `src/rq1_figure0.py`
- outputs: `rq1/`
- docs: `docs/RQ1_GRAPH_GUIDE.md`, `docs/RQ1_HANDOFF_NOTES.md`

RQ2:

- code: `src/rq2_figure1.py`, `src/flex_method.py`
- outputs: `rq2/`
- docs: `docs/RQ2_METHOD_NOTES.md`

RQ3:

- code: `src/rq3_figure2.py`, `src/bess_method.py`
- outputs: `rq3/`
- docs: `docs/RQ3_METHOD_NOTES.md`

Shared:

- orchestrator: `src/intermediate_report_exports.py`
- final report guide: `docs/FINAL_REPORT_ALIGNMENT_NOTES.md`
- whitepaper comparison: `docs/PAPER_METHOD_COMPARISON.md`

## Safe Editing Workflow

Before editing:

```bash
git checkout main
git pull origin main
git status -sb
```

After editing:

```bash
python -m py_compile src/intermediate_report_exports.py src/rq1_figure0.py src/rq2_figure1.py src/rq3_figure2.py src/flex_method.py src/bess_method.py
python src/intermediate_report_exports.py --rq all --year 2025 --output-dir .
git status -sb
```

Commit only intended changes:

```bash
git add README.md docs src rq1 rq2 rq3
git commit -m "<clear message>"
git push origin main
```

## Merge Conflict Guidance

- RQ1 figure changes should stay mostly in `src/rq1_figure0.py` and `rq1/`.
- RQ2 flexibility changes should stay mostly in `src/flex_method.py`, `src/rq2_figure1.py`, and `rq2/`.
- RQ3 BESS changes should stay mostly in `src/bess_method.py`, `src/rq3_figure2.py`, and `rq3/`.
- Changes to `src/intermediate_report_exports.py` affect all RQs and should be checked by running all outputs.

## Final Report Rule

If code changes affect a result, update the matching documentation in the same commit. The report should not contain graph explanations or numeric claims that differ from the generated CSV outputs.
