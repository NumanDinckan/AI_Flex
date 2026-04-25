# RQ2 Method Notes

This note documents the current RQ2 flexibility implementation.

## Purpose
RQ2 asks how much load can be moved away from peak hours when flexibility is defined operationally rather than only as a percentage.

The current implementation uses the full-year half-hour series and reports an annual mean-day profile.

## Baseline
The pipeline first aggregates filtered rows into a half-hour utilisation series. It then computes:

- `mean_day_base`: mean utilisation by `year` and `halfhour_index`
- `med_base`: weekday/half-hour median reference, kept as a secondary diagnostic baseline
- `med_base_sensitivity`: month/weekday/half-hour median reference

The flexibility outputs use `mean_day_base`, so the reported profile is anchored to a full-year mean-day perspective.

## Operational Flex Definition
Flexibility is defined by three factors:

- how much load may be reduced during a peak hour
- for how many consecutive peak hours
- to which off-peak hours the shifted load is moved

Implemented scenarios:

- `10% Flex only`: up to `10%` load reduction for a maximum of `3` consecutive peak hours
- `25% Flex only`: up to `25%` load reduction for a maximum of `3` consecutive peak hours
- recipient window for both scenarios: `22:00-02:00`

The weekday event window remains `14:00-22:00`. Within that window, the model selects the consecutive 3-hour block with the largest shiftable peak-hour load.

## Recovery Rule
Shifted load is recovered only inside the fixed recipient window anchored to the same source day:

- start: `22:00`
- end: `02:00` on the following day

Recipient slots are filled from the lowest-load feasible slots first, subject to the utilisation ceiling, recovery-cap rules, and a rebound cap that prevents overnight recovery from exceeding the original annual peak. Recovery is now forward-looking into the fixed overnight window; it is no longer allowed to appear in arbitrary earlier daytime slots.

## Outputs
RQ2 writes:

- `outputs/rq2/figure1_flex_intermediate.png`
- `outputs/rq2/figure1_flex_intermediate_annual_shift_components.png`
- `outputs/rq2/figure1_flex_intermediate_annual_48h_shift_window.png`
- `outputs/rq2/flexibility_summary_intermediate.csv`

The Figure 1 exports show:

- baseline annual mean load
- `10%` operational flex result
- `25%` operational flex result
- event-window reduction and overnight recovery shading
- annual mean-day reduction/recovery components by source and recipient hour
- an annual mean 48-hour shift window, averaged from rolling 48-hour windows with no specific calendar days
- UK electricity price on a right-hand axis when the price CSV is present

The CSV reports both annual and mean-day metrics, including:

- `original_peak_load`
- `residual_peak_after_flex`
- `annual_peak_reduction_vs_original_percent`
- `mean_day_peak_load`
- `mean_day_energy_utilisation_hours`
- `annual_energy_utilisation_hours`
- `shifted_energy_utilisation_hours_year`
- `unmet_shift_budget_utilisation_hours_year`
- `max_peak_hours`
- `recipient_window`

## Report Wording
Recommended slide wording:

“Flexibility is modelled as an operational shift: during weekday peak-event hours, up to 10% or 25% of load may be reduced for at most 3 consecutive peak hours and recovered in the fixed 22:00-02:00 off-peak window.”

This aligns with Colangelo-style flexibility tiers in which data-centre load reduction is described by reduction magnitude and event duration, while this repo keeps the recipient hours explicit for reproducibility.
