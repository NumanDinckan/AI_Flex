# RQ2 Method Notes

## Research Question

How does operational load shifting affect the annual load profile when flexibility is defined by load-reduction magnitude, event duration, and recipient hours?

RQ2 translates the flexibility concept into explicit operational scenarios. It does not optimize workload scheduling in a full queue-aware sense. It asks what happens if a fixed share of load is reduced during selected high-load hours and recovered in scenario-specific off-peak windows.

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
- daily duration budget: how much peak-equivalent flexible time may be used across the day
- recipient window: where the shifted load is recovered

Implemented scenarios:

- `10% Flex only`: up to `10%` load reduction, co-optimized across up to `2.5` peak-equivalent hours per day.
- `25% Flex only`: up to `25%` load reduction, co-optimized across up to `4.0` peak-equivalent hours per day.
- recipient window for `10%` flex: `22:00-06:00`.
- recipient window for `25%` flex: `20:00-08:00`.

The `10%` recipient window is intentionally wider than the earlier `22:00-02:00` specification. The exploratory `25%` case uses a still broader `20:00-08:00` recovery corridor because the deeper reduction budget otherwise saturates overnight recovery capacity before the additional flexibility can be tested.

The current selector does not use the original broad all-day eligibility rule. It now restricts source reductions to a narrower daytime peak window:

- eligible source hours: `11:00-19:00`
- daily flexible energy is still capped using a scenario-scaled peak-equivalent budget: `2.5` hours in the `10%` case and `4.0` hours in the `25%` case
- price is deliberately excluded from the flex selector; source intervals are prioritized by load magnitude and surplus above the annual mean-day reference

Operationally, this means the RQ2 reduction now starts earlier than a late-evening-only event, but no longer smears across nearly the whole day.

## Recovery Rule

Reduced load is recovered only inside the scenario-specific recipient window linked to the same source day:

- `10%` flex: `22:00-06:00`
- `25%` flex: `20:00-08:00`

Recovery is now co-optimized jointly with source reductions inside the daily linear program. Each overnight recipient slot has a scenario-specific upper bound:

`recovery_ceiling = max(baseline_slot_load, annual_mean_load) * (1 + flex_magnitude)`

This means the `10%` case can recover up to `1.10x` the higher of the slot baseline or annual mean load, and the `25%` case can recover up to `1.25x`. Using annual mean load as a floor prevents low overnight baselines from artificially choking the high-flex recovery test, while keeping slot-specific load shape where it is already higher than the annual mean.

The daily LP also minimizes a shared daily peak variable across the affected source and recovery slots. This prevents the optimizer from reducing the daytime event cleanly only to create a new rebound peak immediately after `22:00`.

Price signals are deliberately excluded from this flexibility dispatch. RQ2 is framed as direct load control for grid-stress reduction, so the source-selection rule stays load-driven. Price responsiveness is handled only in RQ3, where the BESS LP uses price as a secondary dispatch criterion after the feasible peak cap has been established.

## Current 2025 Results

From `rq2/flexibility_summary_intermediate.csv`:

- Both the `10%` and `25%` scenarios are active on `365` flex days.
- The aggregate daily flexibility budget is `2.5` peak-equivalent hours in the `10%` case and `4.0` peak-equivalent hours in the `25%` case.
- Shifted energy is about `16.96` utilisation-hours in the `10%` case.
- Shifted energy is about `27.95` utilisation-hours in the `25%` case.
- The `10%` case reduces the annual peak from `0.3684` to `0.3616`, about `1.84%`.
- The `25%` case also reduces the annual peak to `0.3616`, about `1.84%`.
- Unmet shift budget is about `13.06` utilisation-hours in the `10%` case and about `92.13` utilisation-hours in the `25%` case.
- Recovery diagnostics flag high unmet budget on `301` days for the `10%` case and all `365` days for the `25%` case.

The wider `25%` recovery corridor materially increases realized shifted energy, but it does not create a different flex-only annual peak result. Recovery limits remain strongly binding, especially in the `25%` case. RQ2 should therefore be presented as a modest operational peak-shaving step and as the structured input to RQ3, not as the main source of annual peak reduction.

## Remaining Limitation

The current implementation does include recovery: reduced load is reallocated into scenario-specific off-peak windows subject to ceiling constraints, and reductions and recovery are solved jointly each day. However, it still does not model endogenous task queues, stochastic deferral release, or synchronized rebound after event conditions relax. Chen et al. (2025) warn that deferred inference or training tasks can be rescheduled together once conditions improve, potentially creating secondary peaks.

Operational implication:

- the model captures deterministic same-night recovery, but not workload-queue dynamics
- it therefore may still understate rebound risk in the hours after a stress event or after low-price periods resume
- annual peak results should be interpreted as scenario outputs under a simplified recovery rule, not as proof that rebound risk has been fully characterized

## Figure 1 Outputs

Report-ready files:

- `rq2/figure1_flex_intermediate.png`
- `rq2/figure1_flex_intermediate_annual_shift_components.png`
- `rq2/figure1_flex_intermediate_annual_48h_shift_window.png`
- `rq2/flexibility_summary_intermediate.csv`

Figure 1 views show:

- Panel A: baseline annual mean load with `10%` and `25%` operational flex profiles
- Panel B: the single highest-load day in the filtered year with baseline, `10%` flex, and `25%` flex shown directly
- flexible-load reduction and overnight recovery shading
- annual mean reduction and recovery components
- annual mean 48-hour shift window
- UK electricity price on the right-hand axis when the price CSV is present

In the current filtered 2025 run, Panel B selects `2025-08-12`, the day containing the annual peak. On this branch, the annual-mean and peak-event story is more muted than in the more aggressive flex experiments: the narrower source window improves interpretability, but the stricter recovery and event-shape assumptions compress the difference between the `10%` and `25%` flex-only outcomes.

## Final Report Wording

Use:

> RQ2 defines flexibility operationally. The 10% case allows up to 10% load reduction under a `2.5` peak-equivalent-hour daily budget, while the 25% case allows up to 25% load reduction under a `4.0` peak-equivalent-hour daily budget. In both cases, source reductions are restricted to an `11:00-19:00` daytime peak window. Shifted load is recovered in `22:00-06:00` for the 10% case and `20:00-08:00` for the exploratory 25% case.
>
> The current selector allocates reductions across eligible intervals where they do the most peak-shaving work while respecting a recovery ceiling of `max(baseline_slot_load, annual_mean_load) * (1 + flex_magnitude)`. The daily optimization also constrains recovery against the same peak-cap variable so that rebound does not simply replace the daytime peak.
>
> Price signals are deliberately excluded from the flexibility dispatch to keep RQ2 a single-objective peak-shaving scenario. Price responsiveness is handled exclusively in the BESS dispatch layer.

Also include:

> In the current 2025 utilisation dataset, the narrower `11:00-19:00` flex window gives both flex scenarios a modest annual peak reduction of about `1.84%`. Recovery constraints remain strongly binding, especially in the `25%` case, which motivates testing BESS as the next step in RQ3.

## Presentation Use

Recommended slide:

1. Show the operational definition: magnitude, duration, and recipient window.
2. State exactly what `10%` and `25%` mean.
3. Show Figure 1 or the annual shift-components view.
4. Explain that RQ2 is the load-shifting scenario, while RQ3 tests storage on top of that shifted profile.

## Caveats

- The model uses utilisation ratios, not MW.
- The method is a transparent scenario rule, not an optimization of every possible workload shift.
- The prescribed recipient windows are modelling choices for reproducibility.
- The model uses deterministic overnight recovery, but it does not fully model endogenous rebound dynamics.

## References

- Norris, T. H., Profeta, T., Patiño-Echeverri, D., and Cowie-Haskell, A. (2025), *Rethinking Load Growth: Assessing the Potential for Integration of Large Flexible Loads in US Power Systems*. Nicholas Institute for Energy, Environment & Sustainability, Duke University. `https://nicholasinstitute.duke.edu/publications/rethinking-load-growth`
- IEA (2025), *Energy and AI*. International Energy Agency. `https://www.iea.org/reports/energy-and-ai`
- Wang, Y., Guo, Q., and Chen, M. (2025), *Providing load flexibility by reshaping power profiles of large language model workloads*. *Advances in Applied Energy*, 19, 100232. `https://doi.org/10.1016/j.adapen.2025.100232`
- Chen, X., Wang, X., Colacelli, A., Lee, M., and Xie, L. (2025), *Electricity Demand and Grid Impacts of AI Data Centers: Challenges and Prospects*. `https://doi.org/10.48550/arXiv.2509.07218`
