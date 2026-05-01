# Final Report And Presentation Guide

This document gives the recommended storyline for the final report and presentation. It is aligned with the current code, figures, and CSV outputs.

## One-Sentence Project Summary

The project uses public UK data-centre utilisation profiles to identify variability and peak concentration, then tests an explicit operational flexibility rule and a co-located BESS dispatch strategy to estimate how much peak reduction is achievable in utilisation-ratio terms.

## Research Questions

RQ1:

What do publicly available data-centre load profiles reveal about variability, peak concentration, and potential flexibility?

RQ2:

How does operational load shifting affect the annual load profile under fixed flexibility definitions?

RQ3:

How much additional peak reduction can a co-located BESS provide after flexibility?

## Method Storyline

The report should present the analysis in three steps:

1. RQ1 identifies the empirical opportunity.
2. RQ2 turns that opportunity into a transparent load-shifting scenario.
3. RQ3 adds BESS dispatch after the flexibility scenario.

This sequencing is important. RQ1 does not apply flexibility. RQ2 applies flexibility but does not reduce the absolute annual peak in the current dataset. RQ3 provides the main annual peak reduction result.

## RQ1 Report Message

RQ1 uses the full-year centre-level utilisation profiles. Figure 0 answers variability, peak concentration, and potential flexibility in one dashboard.

Use this wording:

> Publicly available data-centre load profiles show limited average-day variation but meaningful short-run jumps and a concentrated peak tail. The top 10% of half-hour intervals contain about half of above-mean load, which indicates that flexibility should target a limited set of high-load intervals rather than the whole year equally.

Key 2025 values from `rq1/rq1_profile_answer_summary_2025.csv`:

- annual peak is about `1.79x` the mean
- top `10%` of intervals contain about `50.3%` of above-mean load
- shaving to `p95` would affect about `219.5` hours and require about `5.37` utilisation-hours above cap
- shaving to `p90` would affect about `439.0` hours and require about `11.95` utilisation-hours above cap

Use `docs/RQ1_GRAPH_GUIDE.md` for detailed Figure 0 interpretation.

## RQ2 Report Message

RQ2 defines flexibility operationally:

- `10%` case: `10%` load reduction co-optimized across up to `2.5` peak-equivalent hours per day
- `25%` case: `25%` load reduction co-optimized across up to `4.0` peak-equivalent hours per day
- both cases recover shifted load in `22:00-06:00`

Use this wording:

> Flexibility is defined by reduction magnitude, daily peak-equivalent budget, source window, and recipient hours. The 10% case allows 10% load reduction under a 2.5 peak-equivalent-hour daily budget, while the 25% case allows 25% load reduction under a 4.0 peak-equivalent-hour daily budget. In both cases, source reductions are restricted to 11:00-19:00 and shifted load is recovered in the fixed 22:00-06:00 overnight window.

Current 2025 result:

- RQ2 shifts load in both scenarios.
- The annual peak falls from `0.3684` to `0.3616` after RQ2 flexibility, about `1.84%`.
- Therefore, RQ2 should be presented as an operational load-shifting scenario and setup for RQ3, not as the final peak-reduction result.

## RQ3 Report Message

RQ3 applies BESS dispatch after RQ2 flexibility. The BESS controller is peak-first and uses the UK price signal as a secondary dispatch objective when the price CSV is available.

Use this wording:

> RQ3 models a co-located BESS as a behind-the-meter asset operating on the flex-adjusted data-centre load. Dispatch is solved over a duration-specific receding horizon: 48 hours for 4h batteries and 72 hours for 8h batteries. It minimizes residual peaks first and uses UK electricity price as a secondary criterion within the feasible peak cap.

Current 2025 result from `rq3/bess_summary_intermediate.csv`:

- original annual peak: `0.3684`
- residual annual peak after RQ2 flexibility: `0.3616`
- residual annual peak after BESS: about `0.3454` to `0.3407`
- annual peak reduction after BESS: about `6.24%` to `7.51%`
- price signal used: `True`

The annual peak metrics are the main result. The annual mean 48-hour Figure 2 is a visualization and should not replace the annual peak summary.

## Suggested Presentation Structure

Slide 1: Research question and data

- Public data-centre utilisation profiles.
- Unit is utilisation ratio, not MW.
- Year shown: 2025.

Slide 2: RQ1 empirical opportunity

- Use Figure 0.
- Headline: peaks are concentrated and short-run jumps exist.
- Key number: top `10%` intervals contain about `50.3%` of above-mean load.

Slide 3: RQ2 flexibility definition

- Explain magnitude, duration, and recipient window.
- Show exactly what `10%` and `25%` mean.
- Mention the fixed `22:00-06:00` recovery window.

Slide 4: RQ2 load-shifting result

- Use Figure 1 or the annual shift-components view.
- Explain that load is shifted and annual peak reduction is modest under this rule.

Slide 5: RQ3 BESS result

- Use Figure 2.
- State the residual annual peak reduction: `0.3684` to about `0.3407` in the strongest case, or about `7.51%`.
- Mention that UK price data is used as a secondary dispatch signal.

Slide 6: Comparison with literature

- The project is conceptually aligned with data-centre flexibility literature because it defines flexibility by magnitude and duration.
- It is not the same as a full interconnection, conditional firm service, or BYOC study.
- Use `docs/PAPER_METHOD_COMPARISON.md` for exact wording.

Slide 7: Stakeholder implications

- Data-centre operators: operational flexibility and BESS can reduce exposure to peak constraints, but actual MW value depends on site scale.
- Grid operators: peak concentration suggests targeted flexibility may be more useful than broad average-load assumptions.
- Researchers: public utilisation data can show flexibility opportunity, but not contractual flexibility by itself.

Slide 8: Backup caveats

- Utilisation ratios are not MW.
- RQ1 shows potential, not controllability.
- RQ2 is a scenario rule, not a workload optimizer.
- RQ3 is not a full tariff or investment optimization.
- The whitepaper comparison should not be used to claim BYOC or interconnection-speed results.

## Terms To Use Consistently

- `original_peak_load`: annual peak before flexibility and BESS
- `residual_peak_after_flex`: annual peak after RQ2 flexibility
- `residual_peak_after_flex_and_bess`: annual peak after RQ2 flexibility and RQ3 BESS
- `utilisation-hours`: area under utilisation-ratio curves, not MWh
- `annual mean day`: a full-year average by time of day
- `annual mean 48-hour horizon`: averaged 48-hour reporting view, not exact calendar days

## Claims To Avoid

Avoid:

- RQ1 proves the loads are technically or contractually flexible.
- RQ2 reduces the annual peak in the current generated results.
- RQ3 is a full electricity-bill optimization.
- Utilisation ratios can be interpreted directly as MW.
- The project replicates the whitepaper's BYOC or conditional firm service method.

Use:

> The analysis identifies observed flexibility potential in public utilisation data, tests explicit load-shifting scenarios, and evaluates BESS as a peak-first operational asset. Absolute grid-capacity and cost conclusions would require MW conversion and site-specific grid modelling.
