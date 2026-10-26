"""CSV input -> validated pricing rule -> Pathway CSV change log."""

import argparse
from pathlib import Path

from pricing import (
    PricingConfig,
    calculate_demand,
    calculate_price,
    checked_lot_id,
    observation_timestamp,
)


def run_pipeline(source_path: Path, output_path: Path, mode: str, config: PricingConfig) -> None:
    # Keep CLI help and the pricing module usable on hosts without Pathway.
    import pathway as pw

    class ParkingSchema(pw.Schema):
        SystemCodeNumber: str
        LastUpdatedDate: str
        LastUpdatedTime: str
        Occupancy: float
        Capacity: float
        QueueLength: float
        TrafficConditionNearby: float
        IsSpecialDay: float
        VehicleType: str

    @pw.udf(deterministic=True)
    def demand(
        occupancy: float,
        capacity: float,
        queue_length: float,
        traffic: float,
        special_day: float,
        vehicle_type: str,
    ) -> float:
        return calculate_demand(occupancy, capacity, queue_length, traffic, special_day, vehicle_type, config)

    @pw.udf(deterministic=True)
    def price(value: float) -> float:
        return calculate_price(value, config)

    source = pw.io.csv.read(
        str(source_path / "*.csv" if source_path.is_dir() else source_path),
        schema=ParkingSchema,
        mode=mode,
        autocommit_duration_ms=100,
    )
    features = source.select(
        lot_id=pw.udf(checked_lot_id, deterministic=True)(source.SystemCodeNumber),
        timestamp=pw.udf(observation_timestamp, deterministic=True)(
            source.LastUpdatedDate, source.LastUpdatedTime
        ),
        demand=demand(
            source.Occupancy,
            source.Capacity,
            source.QueueLength,
            source.TrafficConditionNearby,
            source.IsSpecialDay,
            source.VehicleType,
        ),
    )
    result = features.with_columns(price=price(features.demand))
    pw.io.csv.write(result, str(output_path))
    # Invalid rows fail the run rather than silently producing a quote.
    pw.run(monitoring_level=pw.MonitoringLevel.NONE, terminate_on_error=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV file or directory of CSV files")
    parser.add_argument("--output", type=Path, required=True, help="new CSV change log, outside the input directory")
    parser.add_argument("--mode", choices=("static", "streaming"), default="static")
    parser.add_argument("--queue-scale", type=float, default=10.0)
    parser.add_argument("--traffic-scale", type=float, default=5.0)
    parser.add_argument("--base-price", type=float, default=10.0)
    parser.add_argument("--min-multiplier", type=float, default=0.5)
    parser.add_argument("--max-multiplier", type=float, default=2.0)
    args = parser.parse_args(argv)

    source_path, output_path = args.input.resolve(), args.output.resolve()
    if not source_path.exists():
        parser.error("--input must exist")
    if args.mode == "streaming" and not source_path.is_dir():
        parser.error("--mode streaming requires a directory")
    if output_path.exists():
        parser.error("--output must not already exist; choose a new change log")
    if source_path.is_dir() and output_path.is_relative_to(source_path):
        parser.error("--output must be outside the input directory")
    try:
        config = PricingConfig(
            queue_scale=args.queue_scale,
            traffic_scale=args.traffic_scale,
            base_price=args.base_price,
            min_multiplier=args.min_multiplier,
            max_multiplier=args.max_multiplier,
        )
    except ValueError as error:
        parser.error(str(error))

    try:
        import pathway  # noqa: F401 - fail before creating output directories
    except ImportError:
        parser.error("Pathway is required: install requirements-pathway.txt on Linux or macOS (WSL2 on Windows)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_pipeline(source_path, output_path, args.mode, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
