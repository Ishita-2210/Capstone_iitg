# Dynamic parking pricing

`Capstone (2).ipynb` studies two pandas pricing heuristics for parking occupancy and demand and preserves an unfinished historical Pathway experiment. `stream_pricing.py` adds a separate CSV pipeline using that historical streaming pricing rule. These are exploratory heuristics, without evidence of real-world congestion or revenue improvements.

## Run the Pathway CSV pipeline

Use Python 3.11 on Linux or macOS, or Linux through WSL2 on Windows. Pathway's [published wheels](https://pypi.org/project/pathway/0.33.0/#files) do not include native Windows. The streaming dependency is separate from the notebook dependencies:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-pathway.txt
python stream_pricing.py --input examples/parking.csv --output runs/quotes.csv --mode static
```

The static command reads the included [synthetic fixture](examples/README.md) and exits. Use a fresh output path for every run. Expected prices are 11.60, 17.56, 20.00 and 9.36; output row order is unspecified.

To watch new and changed CSV files, start with an empty directory:

```sh
mkdir -p incoming
python stream_pricing.py --input incoming --output runs/live-quotes.csv --mode streaming
```

In a second terminal, publish a complete file atomically:

```sh
cp examples/parking.csv incoming/part.tmp
mv incoming/part.tmp incoming/part.csv
```

The process keeps running until interrupted with Ctrl+C. Add more complete `.csv` files to produce further quotes; each needs the same header. Replacing or removing an input file causes retractions and insertions in the output. Keep the output outside the input directory. These behaviors use Pathway's documented [CSV input and output connectors](https://pathway.com/developers/api-docs/pathway-io/csv), with a typed schema and deterministic [Python UDFs](https://pathway.com/developers/api-docs/pathway/#udf).

Each observation produces `lot_id`, `timestamp`, `demand` and `price`. `timestamp` comes from the source date/time, without an inferred timezone. Pathway adds `time` (engine processing batch time) and `diff` (+1 insertion, -1 retraction). This file is a change log: `diff` is not a price difference, and summing prices across its rows is not a revenue calculation. It retains observation history; it does not select the latest quote per lot.

### Pricing rule and validation

The CLI retains the historical Pathway cell's coefficients and vehicle weights:

```text
occupancy_ratio = Occupancy / Capacity
queue_norm = min(QueueLength / queue_scale, 1)
traffic_norm = min(TrafficConditionNearby / traffic_scale, 1)
vehicle_weight = car: 1.0, bike: 0.8, truck: 1.5, other: 1.0
demand = occupancy_ratio + 0.7*queue_norm - 0.4*traffic_norm
         + 0.6*IsSpecialDay + 0.3*vehicle_weight
price = clip(base_price * (1 + 0.4*demand),
             base_price * min_multiplier, base_price * max_multiplier)
```

Defaults are `queue_scale=10`, `traffic_scale=5`, `base_price=10` and multipliers `[0.5, 2]`. These scales are illustrative configuration, not calibration learned from real data. Unlike the unfinished notebook's evolving global maxima, fixed scales give the same observation the same quote regardless of later arrivals. Values beyond a scale saturate at 1. Traffic retains the historical negative coefficient; no causal or optimal-pricing claim is made. The separate pandas model below uses different coefficients and a bike weight of 0.5.

Use `--queue-scale`, `--traffic-scale`, `--base-price`, `--min-multiplier` and `--max-multiplier` to configure the policy. Scales and prices must be finite and positive, and the minimum multiplier must not exceed the maximum. The CSV uses the columns listed below. Dates must be `DD-MM-YYYY`, times `HH:MM:SS`, lot and vehicle strings nonempty, capacity positive, occupancy in `[0, Capacity]`, queue/traffic nonnegative, and the special-day flag 0 or 1. All numeric fields must be finite. Invalid observations stop the pipeline instead of being imputed. Currency units are illustrative.

## Run the pandas models

Use Python 3.11+, install `requirements.txt` in a virtual environment, and run:

```sh
jupyter lab "Capstone (2).ipynb"
```

Provide `data/dataset.csv`, or set `PARKING_CSV` to your CSV path. For a self-contained example, use `PARKING_CSV=examples/parking.csv`. Run the first four code cells in order, stopping at **Historical streaming and visualization experiments**. Model 1 lowercases columns; model 2 reloads the original case-sensitive CSV. The original research dataset is not included.

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

Install `pytest`, then run `python -m pytest -q`. Synthetic-data tests execute the actual pandas model cells and check constant demand and invalid capacity. `python -m pytest -q tests/test_stream_pricing.py` tests the pricing rule, feature scales, bounds, validation and CLI safeguards with only pytest installed. The notebook regression CI job needs neither real parking data nor Pathway.

The separate [Linux Pathway integration workflow](.github/workflows/pathway.yml) installs the pinned runtime and executes `python -m pytest -q tests/integration`. It checks the included fixture end to end, invalid-capacity failure, and file addition/replacement/removal while a real streaming process remains alive. These tests skip when Pathway is absent. A Windows unit-test pass does not verify streaming; require a successful Linux integration run for that claim.

The notebook's later Pathway 0.24.1 prototype remains incomplete: `source` is undefined, its table-universe operation needs review, and its output lacks the `ts`/`diff` fields expected by the historical Bokeh chart. Installing Pathway alone will not make that section runnable. The chart preserves constant measured values without adding random variation. Original cells and recorded outputs remain available as historical work. The new CLI is an independent recovery and does not feed that historical chart.

The pandas demand model normalizes using the whole supplied batch. The CLI uses fixed scales and prices each row independently; it has no forecasting, deduplication, persistent restart state or production sensor integration. Temporal evaluation and calibration remain future work. No throughput, latency, scalability or business-impact measurements are claimed.
