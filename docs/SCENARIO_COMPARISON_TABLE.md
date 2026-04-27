# Scenario Comparison Table

Source file: `rq3/scenario_comparison_table_2025.csv`

The table compares the RQ2 flex-only cases and the RQ3 flex-plus-BESS cases against the original 2025 utilisation profile.

| Scenario | Flex Case | BESS Duration | Residual Peak Utilisation | Annual Peak Reduction vs Original (%) | Price-Weighted Cost Reduction vs Original (%) |
| --- | --- | --- | ---: | ---: | ---: |
| 10% Flex only | 10% | No BESS | 0.5643 | 0.0000 | 0.0667 |
| 25% Flex only | 25% | No BESS | 0.5643 | 0.0000 | 0.0631 |
| 10% Flex + 4h BESS | 10% | 4h | 0.4239 | 24.8901 | 2.7884 |
| 10% Flex + 8h BESS | 10% | 8h | 0.4239 | 24.8919 | 3.3791 |
| 25% Flex + 4h BESS | 25% | 4h | 0.4239 | 24.8901 | 2.7891 |
| 25% Flex + 8h BESS | 25% | 8h | 0.4239 | 24.8919 | 3.3761 |

## Interpretation

The column choices follow common data-centre demand-response and storage evaluation practice: peak reduction captures grid and capacity relevance, while electricity-price-weighted cost reduction captures whether the shifted or battery-adjusted profile moves consumption away from expensive hours.

The cost column is a price-weighted proxy:

`sum(load * UK electricity price * dt_hours)`

Because the load data is in utilisation ratios, the values should be interpreted as relative scenario comparisons, not absolute electricity bills. The metric does not include demand charges, fixed charges, taxes, network tariffs, battery degradation, or investment cost.
