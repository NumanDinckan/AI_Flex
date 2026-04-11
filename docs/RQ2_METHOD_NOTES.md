# RQ2 Method Notes

This note documents the current RQ2 implementation in this branch only. It is meant for collaborators who need to understand how the flexibility model behaves in the code and how to read the outputs.

## Baseline definition

RQ2 starts from the aggregated half-hour utilisation time series loaded in `intermediate_report_exports.py`.

- `utilisation` is the mean load across filtered rows at each timestamp.
- `med_base` is the median reference used by the flexibility logic, computed by `year`, `weekday`, and `halfhour_index`.
- `med_base_sensitivity` is also computed in the pipeline, but the current RQ2 flex logic uses `med_base`.

The baseline line in the figure is `utilisation`, not the median reference.

## Current flex scenarios

The branch implements two scenarios only:

- `10%` conservative flex
  - `flex_share = 0.10`
  - `recovery_window_hours = 6.0`
  - `selected_event_steps = 2`
- `25%` exploratory/aggressive flex
  - `flex_share = 0.25`
  - `recovery_window_hours = 12.0`
  - `selected_event_steps = 6`

## Event window

Flex is only eligible on weekdays during the fixed event window:

- start: `14:00`
- end: `22:00`

In code, this is applied through the timestamp filter in `is_event_eligible(...)`.

## Selection logic

For each day, the model first finds candidate event slots inside the weekday event window.

An event slot is only considered if:

- it is inside the `14:00-22:00` weekday window, and
- `utilisation > med_base`

The selected event slots are sorted by the size of the surplus above the median reference:

- primary sort: `utilisation - med_base`
- secondary sort: `utilisation`
- tertiary sort: index order

Then only the top `selected_event_steps` are acted on.

## Shiftable amount cap

The amount that can be shifted out of an event slot is capped by:

- the flexible share itself, and
- the surplus above `med_base`

In code:

- `available_shift = max(0, min(load_flex_orig, utilisation - med_base))`

So the model never shifts more than:

- the flexible portion of the load, or
- the amount above the median reference

This is why a `10%` case can be small on the aggregate trace.

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

## Why recovery can appear before or after the peak

The current implementation does not force recovery to happen only after the peak. It allows any non-event slot within the recovery window, both before and after the event slot.

That is why a reduction around `16:00` can create recovery around `10:00-12:00` if those slots are inside the allowed window and rank as low-load candidates.

In other words:

- the model is window-bounded, not strictly forward-shift only
- recovery is placed where there is capacity and where the slot looks most suitable under the current heuristic

## Recovery capacity rule

For each candidate recovery slot, the code caps the amount that can be added back using three limits:

- `base_load + median_gap_allowance`
- `(1 + flex_share) * base_load`
- `1.0`

The final recovery upper bound is the minimum of those three values.

This prevents the flexed load from exceeding the unit-scale utilisation ceiling and keeps the recovery bounded relative to the original load and the median reference.

## Current outputs

RQ2 currently writes these files:

- `outputs/rq2/figure1_flex_intermediate.png`
- `outputs/rq2/figure1_flex_intermediate_two_day.png`
- `outputs/rq2/flexibility_summary_intermediate.csv`

The CSV includes the baseline and flex summary metrics for:

- `Original`
- `10% Flex only`
- `25% Flex only`

The two figures are:

- a characteristic-day plot using the `halfhour_index` `0-47`
- a two-day diagnostic around the characteristic day

## Interpretation caveats

- The `10%` scenario can be subtle on the aggregate series because only a few event slots are affected.
- `25%` is currently treated as an exploratory case, not a claim that this amount is always available.
- Recovery can show up before the peak, which can make the load look like it increases in earlier hours even though the model is staying inside the configured window.
- The model is weekday-only and event-window-only; it does not attempt to flex every hour of the day.
- The outputs are heuristic summaries of the implemented logic, not an optimisation proof.

## Where to run it

The RQ2 pipeline is driven from `src/intermediate_report_exports.py`, which calls `run_rq2(...)` after the shared preprocessing and flex calculations.
