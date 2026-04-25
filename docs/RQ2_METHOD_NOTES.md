# RQ2 Method Notes

## Research Question

How does operational load shifting affect the annual load profile when flexibility is defined by load-reduction magnitude, event duration, and recipient hours?

RQ2 translates the flexibility concept into explicit operational scenarios. It does not optimize workload scheduling. It asks what happens if a fixed share of load is reduced during selected peak-event hours and recovered in a fixed off-peak window.

## Data Basis

The pipeline uses the filtered full-year half-hour utilisation series for 2025. It is not based on one characteristic day.

The main reporting profile is an annual mean day, created by averaging the full-year half-hour series by `halfhour_index`. This keeps the figure readable while preserving a full-year basis for the underlying calculations.

The committed RQ2 outputs are in `rq2/`. If the runner is executed without `--output-dir .`, equivalent outputs are written under `outputs/rq2/`.

## Baseline Construction

The runner first aggregates valid rows into one half-hour utilisation time series. It then computes:

- `mean_day_base`: mean utilisation by `year` and `halfhour_index`.
- `med_base`: weekday and half-hour median reference, kept as a diagnostic baseline.
- `med_base_sensitivity`: month, weekday, and half-hour median reference, kept as a sensitivity diagnostic.

The report figures use `mean_day_base`, so the baseline is a full-year annual mean-day view.

## Operational Flexibility Definition

Flexibility is defined by three parameters:

- reduction magnitude: how much load may be reduced during a peak hour
- event duration: how many consecutive peak hours may be reduced
- recipient window: where the shifted load is recovered

Implemented scenarios:

- `10% Flex only`: up to `10%` load reduction for at most `3` consecutive peak hours.
- `25% Flex only`: up to `25%` load reduction for at most `3` consecutive peak hours.
- recipient window for both scenarios: `22:00-02:00`.

The event search window is `14:00-22:00` on weekdays. Within that window, the model selects the consecutive 3-hour block with the largest shiftable peak-hour load.

## Recovery Rule

Reduced load is recovered only inside the fixed overnight recipient window linked to the same source day:

- start: `22:00`
- end: `02:00` on the following day

Recipient slots are filled from the lowest-load feasible slots first. The implementation also applies utilisation ceiling and rebound rules so that overnight recovery does not create a new load spike above the original annual peak.

## Current 2025 Results

From `rq2/flexibility_summary_intermediate.csv`:

- Both the `10%` and `25%` scenarios are active on `132` flex days.
- The maximum peak-event duration is `3` hours.
- Shifted energy is about `3.75` utilisation-hours in the `10%` case.
- Shifted energy is about `3.86` utilisation-hours in the `25%` case.
- The absolute annual peak remains `0.5643` before and after RQ2 flexibility in this dataset.

This means RQ2 should not be presented as reducing the annual peak by itself for the current dataset. Its contribution is the operational load-shifting definition and the annual profile change that becomes the input to RQ3.

## Figure 1 Outputs

Report-ready files:

- `rq2/figure1_flex_intermediate.png`
- `rq2/figure1_flex_intermediate_annual_shift_components.png`
- `rq2/figure1_flex_intermediate_annual_48h_shift_window.png`
- `rq2/flexibility_summary_intermediate.csv`

Figure 1 views show:

- baseline annual mean load
- `10%` operational flex profile
- `25%` operational flex profile
- event-window reduction and overnight recovery shading
- annual mean reduction and recovery components
- annual mean 48-hour shift window
- UK electricity price on the right-hand axis when the price CSV is present

## Final Report Wording

Use:

> RQ2 defines flexibility operationally. The 10% case allows up to 10% load reduction for a maximum of 3 consecutive peak hours, and the 25% case allows up to 25% load reduction for the same maximum duration. In both cases, shifted load is recovered in the fixed 22:00-02:00 off-peak window.

Also include:

> In the current 2025 utilisation dataset, this rule shifts load but does not reduce the absolute annual peak. This indicates that the selected peak windows and recovery constraints matter, and it motivates testing BESS as the next step in RQ3.

## Presentation Use

Recommended slide:

1. Show the operational definition: magnitude, duration, and recipient window.
2. State exactly what `10%` and `25%` mean.
3. Show Figure 1 or the annual shift-components view.
4. Explain that RQ2 is the load-shifting scenario, while RQ3 tests storage on top of that shifted profile.

## Caveats

- The model uses utilisation ratios, not MW.
- The method is a transparent scenario rule, not an optimization of every possible workload shift.
- The fixed recipient window is a modelling choice for reproducibility.
- The current RQ2 scenario does not reduce the absolute annual peak in the generated 2025 summary.
