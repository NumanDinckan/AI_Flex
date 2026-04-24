# Final Report Alignment Notes

This note checks the recent project suggestions against the code currently in this repository. It is intentionally descriptive only. It does not propose code changes in detail and it does not assume that the suggested approach has already been implemented.

## Bottom line

Your colleague’s note is directionally sensible, but it does **not** match the current implementation yet.

The largest mismatches are:

- RQ2 currently defines flexibility mainly by `flex_share` plus a recovery window, not by `flex_share + maximum consecutive peak hours + fixed off-peak recipient window`.
- RQ2 currently does **not** shift load only into a clearly fixed overnight window like `02:00-06:00` or `22:00-02:00`.
- RQ2 currently does **not** enforce “top 3 consecutive peak hours only”.
- the code currently does **not** use UK electricity prices in either RQ2 or RQ3
- RQ3 is currently peak-cap based, not price-based

So the note is a valid **final-report redesign direction**, but not a description of what the code does today.

## 1. Flexibility definition: current code vs suggested definition

### Suggested definition from the note

The note proposes that flexibility should be defined by three operational dimensions:

- how much load may be reduced
- for how many consecutive hours
- to which specific hours it is shifted

Example in the note:

- `10%` flexibility: up to `10%` load reduction for up to `3` consecutive peak hours
- `25%` flexibility: up to `25%` load reduction for up to `3` consecutive peak hours
- recovery shifted into a predefined off-peak window such as `02:00-06:00` or `22:00-02:00`

### What the current code does

In `src/flex_method.py`, the current RQ2 model defines flexibility using:

- a flexible share: `10%` or `25%`
- a recovery window length: `6h` or `12h`
- a weekday event window: `14:00-22:00`

This means:

- the current code already has a clear “how much” dimension
- it already has a timing dimension, but this is a **recovery window**, not a strict “max 3 consecutive peak hours” rule
- it does **not** have a fixed recipient-hour block like `02:00-06:00`

### Important behavioural differences

The current code:

- considers all eligible event-window slots above `med_base`
- does not force activation to only the highest `3` consecutive hours
- allows recovery before or after the event slot, as long as it is inside the allowed recovery window
- selects recovery slots heuristically by feasibility and low load

So if you describe the current implementation in the final report as:

“We reduce a fixed share during the highest 3 peak hours and move it to a fixed overnight window”

that would currently be inaccurate.

## 2. Is the Colangelo reference conceptually relevant?

Yes, conceptually.

The accessible Colangelo sources support the idea that data-center flexibility should be described in operational terms rather than as an abstract percentage only.

Relevant links:

- Colangelo et al. (2025), arXiv field demonstration:
  `https://arxiv.org/abs/2507.00909`
- Colangelo et al. (2026), *Nature Energy* article:
  `https://doi.org/10.1038/s41560-025-01927-1`

What these sources clearly support:

- data centers can provide time-bounded, event-oriented demand reductions
- operational descriptions like “`25%` reduction for `3` hours” are meaningful and communicable

What they do **not** automatically prove for this repo:

- that `10%` and `25%` with `3` consecutive hours and a fixed overnight shift window are already implemented here
- that the exact same flexibility tiers should be copied without adaptation to your dataset and modelling scope

So the note is a strong argument for changing your **scenario definition**, but it should not be presented as already reflected in the code.

## 3. Peak definition: current state

The note asks for clearer peak definitions:

- original peak
- residual peak after flexibility
- residual peak after BESS

### Current code status

This is partly implemented, but not yet fully packaged in one clean reporting layer.

What the code currently has:

- original load series: `utilisation`
- flex-only series: `load_flex_10`, `load_flex_25`
- BESS-adjusted series: `load_*_batt`

RQ2 reports flex-only peak outcomes.

RQ3 now reports:

- annual peak after BESS
- two-day-window peak after BESS
- peak reduction versus original
- peak reduction versus the matching flex-only case

So analytically the three peak concepts are available in the code, but the reporting could still be made more explicit and more presentation-friendly.

## 4. Price-based approach: does that match the current code?

No, not yet.

Your colleague wrote:

- “I would say we take the price-based approach now since we use the electricity prices from the UK”

Based on the current repository, this is not reflected in the code.

### Current code reality

RQ2:

- does not import electricity price data
- does not optimize against price
- is a heuristic load-shifting model

RQ3:

- uses a two-day peak-cap BESS dispatch
- minimizes residual peak, not electricity bill
- does not use UK price series in the objective

So if you move to a price-based story in the report or presentation, that would require a model change first. Right now the defensible statement is:

- the code uses a **peak-shaving** approach
- not a **price-based** co-optimisation approach

## 5. Slide guidance: what is already defensible today?

### Slide 1: explain the flexibility logic

A slide is possible today, but it must reflect the actual code.

Accurate wording today would be closer to:

“During weekday `14:00-22:00` event hours, the model identifies load above a median baseline as potentially shiftable. It then reallocates part of that load to feasible non-event hours within a bounded recovery window.”

It would **not** currently be accurate to say:

“We reduce the highest 3 peak hours and shift them into a fixed overnight window.”

### Slide 2: define `10%` and `25%`

This is already possible, but the correct wording today is:

- `10%` scenario: up to `10%` of load may be shifted, subject to median-baseline surplus and a `6h` recovery window
- `25%` scenario: up to `25%` of load may be shifted, subject to median-baseline surplus and a `12h` recovery window

If you want “operational” wording in terms of exact hours and recipient windows, that is a future model change, not the current method.

### Slide 3: discussion against literature

This is possible now, but the comparison should be framed carefully.

Reasonable comparison points:

- your RQ2 model is a transparent heuristic flexibility allocation model
- your RQ3 model is a short-horizon behind-the-meter peak-shaving battery model
- Colangelo-style results are closer to software-controlled, event-based data-center flexibility demonstrations
- NREL / BTM storage papers are the stronger match for the RQ3 battery methodology

### Slide 4: backup questions

The note’s backup-slide ideas are sensible. Based on the current code, the clean answers would be:

- why peak-based:
  because the implemented battery objective is peak shaving, not bill co-optimisation
- why not full yearly co-optimisation:
  because the current repo deliberately uses transparent, modular heuristics plus a short-horizon battery dispatch instead of a larger integrated optimisation model
- why relative ratios instead of MW:
  because the dataset and current analysis are normalized around utilisation ratios rather than absolute load in MW
- how results compare to literature:
  qualitatively comparable on operational logic, but not a one-to-one replication of published data-center flexibility demonstrations

## 6. Practical recommendation for the report

If you want to stay fully consistent with the code **right now**, the final report should say:

- RQ2 flexibility is a percentage-based, event-window, recoverable-load model with bounded recovery timing
- RQ3 battery dispatch is a two-day, peak-oriented behind-the-meter controller on the flex-adjusted load

If you want to adopt your colleague’s proposed definition for the final report, then the code should later be changed so that RQ2 explicitly includes:

- fixed maximum reduction share
- fixed consecutive peak duration
- fixed recipient off-peak window

and, if desired, a separate price-based objective layer.

## References for the report discussion

- Colangelo, P. et al. (2025), *Turning AI Data Centers into Grid-Interactive Assets: Results from a Field Demonstration in Phoenix, Arizona*.
  `https://arxiv.org/abs/2507.00909`
- Colangelo, P. et al. (2026), *AI data centres as grid-interactive assets*, *Nature Energy*.
  `https://doi.org/10.1038/s41560-025-01927-1`
- DiOrio, N. (2017), *An Overview of the Automated Dispatch Controller Algorithms in the System Advisor Model (SAM)*.
  `https://www.nrel.gov/docs/fy18osti/68614.pdf`
- Mirletz, B. T. and Guittet, D. L. (2021), *Heuristic Dispatch Based on Price Signals for Behind-the-Meter PV-Battery Systems in the System Advisor Model*.
  `https://www.nrel.gov/docs/fy21osti/80258.pdf`
- Neubauer, J. and Simpson, M. (2015), *Deployment of Behind-The-Meter Energy Storage for Demand Charge Reduction*.
  `https://doi.org/10.2172/1168774`
- Rehman, M. M., Kimball, J. W. and Bo, R. (2023), *Multi-layered Energy Management Framework for Extreme Fast Charging Stations Considering Demand Charges, Battery Degradation, and Forecast Uncertainties*.
  `https://www.osti.gov/servlets/purl/1973122`
