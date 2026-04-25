# Final Report Alignment Notes

## Current Implementation
The code now matches the final-report direction more closely:

- RQ2 defines flexibility as reduction magnitude, maximum consecutive peak duration, and fixed recipient hours.
- RQ2 uses a full-year annual mean-day baseline for its figure and summary.
- RQ3 plots an annual mean 48-hour horizon and reports original peak, residual peak after flexibility, and residual peak after flexibility plus BESS.
- RQ3 can combine peak-shaving with a UK price signal when a price CSV is supplied.

## RQ2 Flexibility Definition
Use this wording in the report:

“Flexibility is defined operationally. The 10% case allows up to 10% load reduction for a maximum of 3 consecutive peak hours. The 25% case allows up to 25% load reduction for a maximum of 3 consecutive peak hours. In both cases, shifted load is recovered in the fixed off-peak recipient window 22:00-02:00.”

This gives the three requested dimensions:

- load reduction magnitude
- maximum consecutive peak duration
- fixed recipient hours

The implementation is qualitatively aligned with Colangelo-style flexibility tiers, which discuss data-centre reductions in terms of power-reduction magnitude and event duration. The exact recipient window remains this project’s modelling choice.

## Peak Definitions
Use these terms consistently:

- `original_peak_load`: annual peak before flexibility and BESS
- `residual_peak_after_flex`: annual peak after RQ2 flexibility
- `residual_peak_after_flex_and_bess`: annual peak after RQ2 flexibility plus RQ3 BESS

RQ2 reports the post-flex residual peak. RQ3 reports the post-BESS residual peak and compares it with both the original peak and the matching flex-only peak.

## Price And Peak Framing
The BESS method is peak-first. When `--price-input` is supplied, the LP keeps the peak-minimising cap and then uses price as a secondary dispatch criterion.

Recommended wording:

“The battery dispatch combines peak shaving with a price-aware secondary objective. Peak reduction remains the primary reliability/grid metric, while UK price data can shape charge/discharge timing within the feasible peak cap.”

Avoid calling it a full electricity-bill optimisation unless tariff charges, standing charges, degradation cost, and complete price data are added.

## Presentation Slides
Suggested slide structure:

1. Flexibility logic: reduce a fixed share of load during the highest 3 consecutive peak hours and shift it into the fixed 22:00-02:00 off-peak window.
2. Operational definitions: show exactly what `10%` and `25%` mean in load share, hours, and recipient window.
3. Results and stakeholder implications: compare peak reductions with literature; discuss grid operators, data-centre operators, and flexibility-market stakeholders.
4. Backup questions: why peak-first, why annual mean-day or annual mean 48-hour reporting, why utilisation ratios rather than MW, how the results compare with Colangelo-style data-centre flexibility studies.

## Important Caveats
- The dataset is expressed as utilisation ratios, not MW, so absolute grid-capacity conclusions need a conversion factor.
- RQ2 is still a transparent heuristic allocation model, not a full workload scheduler.
- RQ3 is a short-horizon operational battery dispatch, not a full-year co-optimisation of workload, battery degradation, and tariffs.
- Price-aware dispatch is active only when a price CSV is supplied.
