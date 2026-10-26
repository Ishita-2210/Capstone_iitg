# Dynamic parking pricing experiments

`Capstone (2).ipynb` studies two pandas pricing heuristics for parking occupancy and demand. It also preserves an unfinished Pathway streaming experiment. These are exploratory models, without evidence of real-world congestion or revenue improvements.

## Run the pandas models

Use Python 3.11+, install `requirements.txt` in a virtual environment, and run:

```sh
jupyter lab "Capstone (2).ipynb"
```

Provide `data/dataset.csv`, or set `PARKING_CSV` to your CSV path. Run the first four code cells in order, stopping at **Historical streaming and visualization experiments**. Model 1 lowercases columns; model 2 reloads the original case-sensitive CSV. The dataset is not included.

| Column | Meaning |
| --- | --- |
| `SystemCodeNumber` | Parking-lot identifier |
| `LastUpdatedDate`, `LastUpdatedTime` | Day-first date and time |
| `Occupancy`, `Capacity` | Occupied spaces and positive total spaces |
| `QueueLength`, `TrafficConditionNearby` | Numeric queue and traffic indicators |
| `IsSpecialDay` | Numeric event flag |
| `VehicleType` | `car`, `bike` or `truck`; unknown values use weight 1 |

Model 1 uses `10 + 5 × Occupancy / Capacity`, clipped to [5,20]. Model 2 combines occupancy, normalized queue/traffic, special-day status and vehicle weights (car 1, bike 0.5, truck 1.5), min-max normalizes demand and computes `10 × (1 + normalized_demand)`, clipped to [5,20]. Constant demand maps to the base price rather than NaN. Currency units are illustrative.

## Verification and limitations

Install `pytest`, then run `python -m pytest -q`. Synthetic-data tests execute the actual pandas model cells and check constant demand and invalid capacity. CI does not require parking data, Colab or Pathway.

The later Pathway 0.24.1 prototype is incomplete: `source` is undefined, its table-universe operation needs review, and its output lacks the `ts`/`diff` fields expected by the historical Bokeh chart. Installing Pathway alone will not make that section runnable. The chart now preserves constant measured values without adding random variation. Original cells and recorded outputs remain available as historical work; no streaming execution is claimed.

Both pandas models normalize using the whole supplied batch. This is descriptive batch analysis, not a validated online forecaster; temporal evaluation and calibration remain future work.
