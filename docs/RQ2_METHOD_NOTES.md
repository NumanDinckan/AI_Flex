# RQ2 Method Notes

This note documents the current RQ2 implementation in this branch only. It is meant for collaborators who need to understand how the flexibility model behaves in the code and how to read the outputs.

## Purpose of RQ2

RQ2 is the project’s flexibility module.

Its role is to answer a narrow question:

- if part of the data-center load is flexible,
- and that flexibility is only activated during weekday afternoon/evening stress hours,
- how much of that load can be shifted away from the event window and recovered elsewhere without violating the model’s caps and timing rules?

The implementation is intentionally heuristic and transparent. It is not a full optimisation model. The point is to create reproducible, readable scenarios that can be plotted and compared consistently across the project.

## Baseline definition

RQ2 starts from the aggregated half-hour utilisation time series loaded in `intermediate_report_exports.py`.

- `utilisation` is the mean load across filtered rows at each timestamp.
- `med_base` is the median reference used by the flexibility logic, computed by `year`, `weekday`, and `halfhour_index`.
- `med_base_sensitivity` is also computed in the pipeline, but the current RQ2 flex logic uses `med_base`.

The baseline line in the figure is `utilisation`, not the median reference.

## Data and time resolution

The current implementation assumes:

- half-hourly data
- `dt_hours = 0.5`
- one aggregated utilisation series after filtering the raw input

This means:

- one day contains 48 slots
- a `6h` recovery window means up to 12 half-hour slots
- a `12h` recovery window means up to 24 half-hour slots

## Current flex scenarios

The branch implements two scenarios only:

- `10%` conservative flex
  - `flex_share = 0.10`
  - `recovery_window_hours = 6.0`
- `25%` exploratory/aggressive flex
  - `flex_share = 0.25`
  - `recovery_window_hours = 12.0`

Interpretation:

- `10%` is the conservative scenario
- `25%` is an exploratory upper-bound case
- both values are treated as maximum flexible shares, not guaranteed reductions at every eligible step

## Event window

Flex is only eligible on weekdays during the fixed event window:

- start: `14:00`
- end: `22:00`

In code, this is applied through the timestamp filter in `is_event_eligible(...)`.

Operational interpretation:

- the model assumes flexibility is event-driven rather than continuously active
- the event window is a simple proxy for stressed afternoon/evening periods
- weekends are excluded

## Selection logic

For each day, the model first finds candidate event slots inside the weekday event window.

An event slot is only considered if:

- it is inside the `14:00-22:00` weekday window, and
- `utilisation > med_base`

The selected event slots are sorted by the size of the surplus above the median reference:

- primary sort: `utilisation - med_base`
- secondary sort: `utilisation`
- tertiary sort: index order

There is no longer a fixed activation duration such as “top 2 hours” or “top 6 hours”.

Instead, all eligible event-window slots contribute to a daily shiftable-workload budget. The model may apply flex at any eligible timestep, up to the per-slot cap, as long as the total shifted workload stays within that daily budget and can be fully recovered inside the configured recovery window.

This is the main behavioural change relative to the earlier version that forced a fixed number of active slots.

## Shiftable amount cap and budget

The amount that can be shifted out of an event slot is capped by:

- the flexible share itself, and
- the surplus above `med_base`

At each eligible timestep, the reduction cap is:

- `available_shift = max(0, min(load_flex_orig, utilisation - med_base))`

This means the model never shifts more than:

- the flexible portion of the load, or
- the amount above the median reference

For each day, the total shiftable budget is the sum of these per-slot caps across all eligible event-window slots. The optimisation is therefore budget-based, not duration-based.

This is why a `10%` case can still be small on the aggregate trace: the daily budget is limited both by the `10%` flexible share and by how much the event-window load sits above the median reference.

In practical terms:

- if the event-window load is only slightly above the median reference, the budget stays small
- if the event-window load is much higher than the median reference, the budget is larger
- the `25%` case usually has a larger budget because its per-slot cap is larger

## Recovery window and candidate rules

Recovery uses the same day only, within a bounded window around each selected event slot.

- `10%` uses a `6h` recovery window
- `25%` uses a `12h` recovery window

For each selected peak slot, the recovery candidates are:

- on the same day
- not the peak slot itself
- not inside the event window
- within `abs(rec_idx - peak_idx) <= recovery_steps`

Candidates are sorted by:

- lowest `utilisation` first
- then closest distance to the peak
- then index order

This means the model prefers “lowest-load feasible slots nearby” rather than “strictly the next slot after the event” or “the absolute minimum of the day”.

## Why recovery can appear before or after the peak

The current implementation does not force recovery to happen only after the peak. It allows any non-event slot within the recovery window, both before and after the event slot.

That is why a reduction around `16:00` can create recovery around `10:00-12:00` if those slots are inside the allowed window and rank as low-load candidates.

In other words:

- the model is window-bounded, not strictly forward-shift only
- recovery is placed where there is capacity and where the slot looks most suitable under the current heuristic

Example:

- if an event slot is at `16:00`
- the `10%` scenario allows a `6h` window
- then non-event recovery can appear in any same-day slot roughly between `10:00` and `22:00`, provided the slot is feasible under the recovery cap

That is why some RQ2 figures show recovery before the visible afternoon peak.

## Full recovery condition

The model only counts workload as shifted when it can actually be placed into recovery slots inside the allowed window. In other words:

- the daily budget defines the maximum shiftable workload
- the realised shifted workload can be lower than that budget if recovery capacity is limited
- any workload that is counted as shifted is fully recovered inside the configured recovery window

So the implementation is closer to “recoverable budget use” than to “mandatory activation for a fixed number of hours”.

This is important for interpretation:

- a large budget does not automatically mean a large realised shift
- realised shift depends on whether the model can find admissible recovery slots
- if recovery capacity is tight, some of the daily budget stays unused

## Recovery capacity rule

For each candidate recovery slot, the code caps the amount that can be added back using three limits:

- `base_load + median_gap_allowance`
- `(1 + flex_share) * base_load`
- `1.0`

The final recovery upper bound is the minimum of those three values.

This prevents the flexed load from exceeding the unit-scale utilisation ceiling and keeps the recovery bounded relative to the original load and the median reference.

Conceptually, this means recovered load cannot be placed without limit into low-load hours.

## Current outputs

RQ2 currently writes these files:

- `outputs/rq2/figure1_flex_intermediate.png`
- `outputs/rq2/figure1_flex_intermediate_two_day.png`
- `outputs/rq2/figure1_flex_intermediate_two_day_aggregated.png`
- `outputs/rq2/flexibility_summary_intermediate.csv`

The CSV includes the baseline and flex summary metrics for:

- `Original`
- `10% Flex only`
- `25% Flex only`

The two figures are:

- a characteristic-day plot using the `halfhour_index` `0-47`
- a two-day diagnostic around the characteristic day
- an aggregated two-day diagnostic with fewer arrows so the source-to-recovery direction is easier to read

## How to read the figures

### `figure1_flex_intermediate.png`

This is the main characteristic-day figure.

- x-axis: `0-47` half-hour slots for the selected characteristic day
- dark blue line: actual aggregated baseline load
- grey dashed line: median reference `med_base`
- orange line: `10%` flex result
- green line: `25%` flex result

Interpretation:

- if the flex line drops below the baseline in the event window, that is active load reduction
- if the flex line rises above baseline outside the event window, that is recovery

### `figure1_flex_intermediate_two_day.png`

This is the detailed two-day diagnostic.

- it shows the day before and the characteristic day together
- green shading marks reduction during the event window
- red shading marks recovery in non-event slots
- many numbered arrows show individual source-to-recovery transfer pairings

This version is useful when you want to inspect the detailed matching logic.

### `figure1_flex_intermediate_two_day_aggregated.png`

This is the cleaner diagnostic.

- it keeps the same two-day view
- it aggregates each event-slot reduction into one weighted-average destination arrow
- labels show `source time -> recovery time`

This version is easier to read when the detailed arrow version is too dense.

## How to read the summary CSV

The summary CSV is a compact day-level comparison for the characteristic day.

Main fields:

- `peak_load`: maximum load on the plotted characteristic day
- `peak_reduction_vs_original_percent`: peak reduction relative to baseline
- `daily_energy`: total daily energy proxy on the characteristic day
- `daily_energy_delta_percent`: should remain close to zero because shifted workload is recovered
- `shifted_energy_utilisation_hours`: realised shifted workload on the characteristic day
- `max_increase_vs_original`: largest recovery bump above baseline
- `halfhours_above_original`: number of recovery half-hours above baseline

Naming caveat:

- `unmet_energy_utilisation_hours` currently means unused shift budget on the characteristic day, not failed recovery of already-shifted energy
- the column name was kept for continuity, but conceptually it is “budget not realised”

## Interpretation caveats

- The `10%` scenario can be subtle on the aggregate series because only a few event slots are affected.
- `25%` is currently treated as an exploratory case, not a claim that this amount is always available.
- Recovery can show up before the peak, which can make the load look like it increases in earlier hours even though the model is staying inside the configured window.
- The model is weekday-only and event-window-only; it does not attempt to flex every hour of the day.
- The outputs are heuristic summaries of the implemented logic, not an optimisation proof.

Additional caveats:

- because recovery can happen before or after the peak, the visual effect can look counterintuitive if you expect strictly forward shifting
- the aggregate trace can hide stronger behaviour visible at individual-site level
- the model uses a median reference, not a market signal, carbon signal, or queueing model
- the chosen event window is fixed and not inferred from prices or operator warnings

## Where to run it

The RQ2 pipeline is driven from `src/intermediate_report_exports.py`, which calls `run_rq2(...)` after the shared preprocessing and flex calculations.

Typical command:

```bash
.venv/bin/python src/intermediate_report_exports.py --rq rq2 --year 2025 --output-dir outputs/rq2
```

To test a single centre:

```bash
.venv/bin/python src/intermediate_report_exports.py --rq rq2 --year 2025 --centres "Data Centre #44" --output-dir outputs/rq2_dc44_test
```
