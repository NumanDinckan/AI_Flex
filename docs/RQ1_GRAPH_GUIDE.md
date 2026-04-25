# RQ1 Graph Guide

Research question:

> What do publicly available data centre load profiles reveal about variability, peak concentration, and potential flexibility?

This guide explains how the RQ1 figures should be read and how they can be used in the final report or presentation. The important shift is that Figure 0 is no longer only a descriptive daily load-shape plot. It is now structured as evidence for the three parts of RQ1:

- variability
- peak concentration
- potential flexibility

In the final report, RQ1 is the evidence step before the scenario analysis. It shows where flexibility may be valuable; RQ2 defines the actual flexibility rule, and RQ3 tests BESS on top of that rule.

## Main Message

The public data suggests that average data-centre load is relatively stable, but the profile still contains meaningful short-run movement and a concentrated upper tail. The annual peak is about `1.79x` the mean, and the top `10%` of half-hour intervals account for about `50.3%` of all above-mean load. This means flexibility potential is not spread evenly across the whole year: it is concentrated in identifiable high-load intervals.

Use this as the main RQ1 answer:

> Publicly available data centre load profiles show limited average-day variation but meaningful short-run jumps and a concentrated peak tail. The top 10% of half-hour intervals contain about half of above-mean load, which indicates that flexibility should target a limited set of high-load intervals rather than the whole year equally.

## Figure 0

File:

`rq1/figure0_intro_annual_mean_day_all_centres.png`

This is the main RQ1 dashboard. Each panel answers one part of the research question.

## Panel A: Variability

Title:

`Variability: One-Hour Load Jump Distribution by Hour`

What it shows:

- The distribution of one-hour absolute load changes by hour of day.
- The metric is `|delta_1h|`, calculated at centre level.
- Each value compares a centre's utilisation with its utilisation exactly one hour earlier.
- The boxplot uses all centres and all available 2025 observations after filtering.

How to read it:

- A higher median means typical one-hour movement is larger in that hour.
- A wider box means centres or days differ more strongly in that hour.
- Longer whiskers show less frequent but larger one-hour movements.
- The strongest one-hour movements are visible around the morning to midday period, especially around `08:00-11:00`.

What it answers:

- It answers the `variability` part of RQ1.
- It shows that variability is not just about the annual mean profile; there are short-run operational changes within the day.

Suggested report wording:

> One-hour load changes are small in the median case but show clear hourly structure, with larger movement around morning to midday periods. This suggests that public data-centre profiles are not completely flat at operational timescales.

Important caveat:

- This is a utilisation-ratio movement, not MW.
- It shows observed load movement, not necessarily controllable flexibility.

## Panel B: Peak Concentration

Title:

`Peak Concentration: Highest-Load Half-Hours`

What it shows:

- The top part of the annual load-duration curve.
- The x-axis is the highest-load half-hours included, expressed as a percentage of all observed half-hours.
- The y-axis is utilisation.
- Horizontal and vertical guide lines mark p99, p95, and p90 load thresholds.

How to read it:

- A steep left-hand tail means that the highest loads are concentrated in a small share of the year.
- The annual peak sits well above the mean: `peak/mean = 1.79x`.
- The top `10%` of half-hours account for about `50.3%` of above-mean load.

What it answers:

- It answers the `peak concentration` part of RQ1.
- It shows whether high load is a broad everyday condition or a narrower upper-tail problem.

Suggested report wording:

> The load-duration curve shows a concentrated upper tail. The highest half-hours are materially above the rest of the profile, and the top 10% of intervals account for around half of above-mean load.

Important caveat:

- The curve is based on available filtered observations, not a guaranteed complete 8760-hour measured year.
- The result should be interpreted as concentration in the available public profile.

## Panel C: Peak Timing

Title:

`Peak Timing: Top 10% Load Intervals by Hour`

What it shows:

- The share of top-10% load intervals occurring in each hour of the day.
- It uses the same aggregate annual profile as the load-duration curve.

How to read it:

- Higher bars identify hours that are overrepresented among high-load periods.
- Peaks are not evenly distributed across all hours.
- The strongest concentration appears around late morning to afternoon, with a noticeable contribution around the late evening boundary.

What it answers:

- It connects peak concentration to time-of-day structure.
- It helps explain where flexibility or peak-shaving actions would most likely need to focus.

Suggested report wording:

> The top-load intervals have a visible time-of-day pattern, meaning peak concentration is not random. This supports defining flexibility around operational windows rather than treating all hours equally.

Important caveat:

- Panel C does not yet apply the RQ2 flexibility rule.
- It only identifies when high-load intervals occur before any scenario is imposed.

## Panel D: Potential Flexibility

Title:

`Potential Flexibility: Peak-Shaving Opportunity`

What it shows:

- Candidate peak caps at p99, p95, p90, p85, and p80.
- Green bars show `utilisation-hours above cap`.
- The red line shows the implied annual peak reduction as a share of the original peak.
- Labels above the bars show how many hours sit above each cap.

How to read it:

- A smaller bar means less energy would need to be shifted to reach that cap.
- A larger red-line value means stronger peak reduction.
- Moving from p99 to p90 increases the amount of shifting required, but it also increases the peak reduction.

Current 2025 values:

- Cap at `p99`: `44.0` hours above cap, `1.05` utilisation-hours to shift, `23.6%` peak reduction.
- Cap at `p95`: `219.5` hours above cap, `5.37` utilisation-hours to shift, `30.7%` peak reduction.
- Cap at `p90`: `439.0` hours above cap, `11.95` utilisation-hours to shift, `34.3%` peak reduction.
- Cap at `p85`: `658.0` hours above cap, `18.92` utilisation-hours to shift, `36.6%` peak reduction.
- Cap at `p80`: `877.5` hours above cap, `26.13` utilisation-hours to shift, `38.3%` peak reduction.

What it answers:

- It answers the `potential flexibility` part of RQ1.
- It gives a pre-scenario estimate of how much load would need to move if the objective were to cap the upper tail.

Suggested report wording:

> The flexibility potential is measurable because the excess above high-percentile caps is finite and concentrated. For example, capping the profile at p95 would affect about 219.5 hours and require shifting about 5.37 utilisation-hours.

Important caveat:

- This is not the RQ2 operational flexibility result.
- It does not specify recipient hours, maximum consecutive shift duration, or recovery limits.
- It is a diagnostic opportunity measure: "how much would need to move", not "how much can definitely move".

## Figure 0 Left Panels

File:

`rq1/figure0_intro_annual_mean_day_all_centres_left.png`

This is a simplified backup figure. It keeps the two most presentation-friendly RQ1 components:

- one-hour load jump distribution
- utilisation-hours above candidate peak caps

Use this version if the full 2x2 dashboard is too dense for a slide.

## Centre-Level Jump Detail

File:

`rq1/figure0_1_rq1_center_load_jumps_2025.png`

This figure gives centre-level detail for the accepted one-hour jump analysis.

Panel A:

- Heatmap of mean `|delta_1h|` by centre and hour.
- Centres are sorted by mean one-hour movement.
- This shows which centres drive the variability pattern.

Panel B:

- Hourly one-hour jump profiles for the top 10 centres by mean `|delta_1h|`.
- This shows whether high-variability centres move at similar or different times of day.

How to use it:

- Use it as a backup slide or appendix figure.
- It supports the claim that variability differs across centres, not only across hours.

Important caveat:

- Centres with fewer than one week of observations are excluded from stable ranking and labelled as `insufficient coverage` in the metrics CSV.

## CSVs Behind The Graphs

## `rq1_profile_answer_summary_2025.csv`

Use this for high-level RQ1 result statements.

Important values:

- `peak_to_average_ratio = 1.7904`
- `p90_utilisation = 0.3706`
- `p95_utilisation = 0.3912`
- `p99_utilisation = 0.4312`
- `median_centre_cv = 0.0679`
- `p90_centre_cv = 0.3029`
- `top_10pct_share_of_above_mean_energy_percent = 50.2922`

Best use:

- Final report text.
- Presentation headline numbers.
- Short result summaries.

## `rq1_peak_shaving_opportunity_2025.csv`

Use this for the flexibility-potential story.

Important columns:

- `cap_percentile`
- `cap_utilisation`
- `hours_above_cap`
- `excess_utilisation_hours_to_shift`
- `peak_reduction_percent_of_peak`

Best use:

- Explaining why RQ2/RQ3 flexibility scenarios are relevant.
- Showing that peak shaving has a measurable target before applying scenario rules.

## `rq1_center_variability_metrics_2025.csv`

Use this for centre-level variability.

Important columns:

- `coefficient_of_variation`
- `mean_abs_delta_1h`
- `peak_to_average_ratio`
- `sufficient_coverage`
- `variability_bucket`

Best use:

- Appendix table.
- Explaining why some centres are more variable than others.
- Supporting the centre-level jump heatmap.

## `rq1_center_variability_bucket_summary_2025.csv`

Use this to summarize centre groups.

Current 2025 pattern:

- High-variability centres have mean CV about `0.231`.
- Medium-variability centres have mean CV about `0.069`.
- Low-variability centres have mean CV about `0.033`.
- High-variability centres also have a higher mean peak-to-average ratio.

Best use:

- One compact sentence in the results discussion.
- Backup slide if asked whether all centres behave the same.

## How RQ1 Links To RQ2 And RQ3

RQ1 does not apply flexibility. It identifies where flexibility might matter.

- RQ1 shows that the upper tail is concentrated.
- RQ2 then defines an operational load-shifting scenario for peak hours.
- RQ3 then tests whether BESS can reduce the residual peak after flexibility.

Use this transition:

> RQ1 identifies the empirical reason to test flexibility: peaks are concentrated in a limited set of high-load intervals. RQ2 then turns this opportunity into explicit operational scenarios, and RQ3 tests how storage changes the residual peak.

## Claims To Avoid

Do not say:

- The public data proves these loads are contractually flexible.
- The utilisation-hours are the same as MWh.
- RQ1 alone determines an optimal flexibility schedule.
- The p95 or p90 caps are recommended operational targets.
- The one-hour jumps are all voluntary workload shifts.

Safer wording:

> RQ1 identifies observed variability and peak concentration. It provides evidence of flexibility potential, but the actual flexibility rule is defined later in RQ2.

## Slide Structure

Recommended RQ1 slide:

1. Title: `RQ1: Public profiles show concentrated peaks and measurable flexibility potential`
2. Main figure: use `figure0_intro_annual_mean_day_all_centres.png`
3. Headline: peak load is `1.79x` the annual mean.
4. Headline: the top `10%` intervals contain `50.3%` of above-mean load.
5. Headline: shaving to `p95` would require shifting `5.37` utilisation-hours across `219.5` hours.
6. Speaker note: "This does not prove exact operational flexibility, but it tells us where flexibility would be valuable."

Backup slide:

- Use `figure0_1_rq1_center_load_jumps_2025.png`.
- Explain that variability differs across centres and hours.
