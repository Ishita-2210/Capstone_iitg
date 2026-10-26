# Synthetic parking observations

`parking.csv` is a hand-authored fixture added for the reproducible CLI and tests.
The lot names, dates and values are invented. It is not a recovered research
dataset, recorded sensor stream, or evidence of model accuracy. Its columns
match the notebook's source schema.

With the CLI defaults (queue scale 10, traffic scale 5, base price 10), the
expected demand and bounded price are:

| Lot | Time | Demand | Price |
| --- | --- | --- | --- |
| SYNTHETIC-A | 09:00:00 | 0.40 | 11.60 |
| SYNTHETIC-A | 10:00:00 | 1.89 | 17.56 |
| SYNTHETIC-B | 09:00:00 | 2.75 | 20.00 |
| SYNTHETIC-B | 10:00:00 | -0.16 | 9.36 |

For example, the second row has demand
`0.8 + 0.7*(5/10) - 0.4*(2/5) + 0.6 + 0.3 = 1.89`.
The truck row's raw price is 21.00, so the upper bound clips it to 20.00.
