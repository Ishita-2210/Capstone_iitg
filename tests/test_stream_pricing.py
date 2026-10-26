import math

import pytest

from pricing import (
    PricingConfig,
    calculate_demand,
    calculate_price,
    checked_lot_id,
    observation_timestamp,
)
from stream_pricing import main


CONFIG = PricingConfig()


@pytest.mark.parametrize(
    "inputs, expected_demand, expected_price",
    [
        ((10, 100, 0, 0, 0, "car"), 0.4, 11.6),
        ((80, 100, 5, 2, 1, "car"), 1.89, 17.56),
        ((100, 100, 10, 0, 1, "truck"), 2.75, 20.0),
        ((0, 100, 0, 5, 0, "bike"), -0.16, 9.36),
        ((10, 100, 0, 0, 0, "unknown"), 0.4, 11.6),
        ((10, 100, 0, 0, 0, " CAR "), 0.4, 11.6),
    ],
)
def test_historical_streaming_rule(inputs, expected_demand, expected_price):
    demand = calculate_demand(*inputs, CONFIG)
    assert demand == pytest.approx(expected_demand)
    assert calculate_price(demand, CONFIG) == pytest.approx(expected_price)


def test_configured_scales_and_saturation():
    config = PricingConfig(queue_scale=20, traffic_scale=10)
    assert calculate_demand(0, 100, 10, 5, 0, "car", config) == pytest.approx(0.45)
    assert calculate_demand(0, 100, 100, 100, 0, "car", config) == pytest.approx(0.6)


def test_prices_respect_custom_bounds():
    config = PricingConfig(base_price=20, min_multiplier=1, max_multiplier=1.5)
    assert calculate_price(-0.16, config) == 20
    assert calculate_price(2.75, config) == 30


def test_repeat_observation_is_independent_of_other_arrivals():
    inputs = (80, 100, 5, 2, 1, "car")
    before = calculate_price(calculate_demand(*inputs, CONFIG), CONFIG)
    calculate_demand(100, 100, 1_000, 1_000, 1, "truck", CONFIG)
    assert calculate_price(calculate_demand(*inputs, CONFIG), CONFIG) == before


@pytest.mark.parametrize(
    "index, value, message",
    [
        (0, -1, "Occupancy"),
        (0, 101, "Occupancy"),
        (1, 0, "Capacity"),
        (1, -10, "Capacity"),
        (2, -1, "nonnegative"),
        (3, -1, "nonnegative"),
        (4, 0.5, "IsSpecialDay"),
        (5, "", "VehicleType"),
    ],
)
def test_invalid_observations_fail(index, value, message):
    inputs = [10, 100, 0, 0, 0, "car"]
    inputs[index] = value
    with pytest.raises(ValueError, match=message):
        calculate_demand(*inputs, CONFIG)


@pytest.mark.parametrize("index", range(5))
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_features_fail(index, value):
    inputs = [10, 100, 0, 0, 0, "car"]
    inputs[index] = value
    with pytest.raises(ValueError, match="finite"):
        calculate_demand(*inputs, CONFIG)


@pytest.mark.parametrize(
    "settings",
    [
        {"queue_scale": 0},
        {"traffic_scale": -1},
        {"base_price": math.nan},
        {"max_multiplier": math.inf},
        {"min_multiplier": 3, "max_multiplier": 2},
        {"base_price": 1e308, "max_multiplier": 2},
        {"base_price": 1e-200, "min_multiplier": 1e-200},
    ],
)
def test_invalid_configuration_fails(settings):
    with pytest.raises(ValueError):
        PricingConfig(**settings)


def test_lot_and_event_timestamp_validation():
    assert checked_lot_id(" A ") == "A"
    assert observation_timestamp("01-12-2016", "09:00:00") == "2016-12-01T09:00:00"
    with pytest.raises(ValueError, match="lot identifier"):
        checked_lot_id(" ")
    with pytest.raises(ValueError, match="DD-MM-YYYY"):
        observation_timestamp("31-02-2016", "09:00:00")


def test_cli_rejects_streaming_file_before_loading_runtime(tmp_path, capsys):
    source = tmp_path / "source.csv"
    source.write_text("header\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["--input", str(source), "--output", str(tmp_path / "out.csv"), "--mode", "streaming"])
    assert error.value.code == 2
    assert "requires a directory" in capsys.readouterr().err


def test_cli_keeps_output_outside_source(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["--input", str(tmp_path), "--output", str(tmp_path / "out.csv")])
    assert "outside the input directory" in capsys.readouterr().err


def test_cli_preserves_existing_output(tmp_path, capsys):
    source = tmp_path / "source.csv"
    source.write_text("untouched\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--input", str(source), "--output", str(source)])
    assert "must not already exist" in capsys.readouterr().err
    assert source.read_text(encoding="utf-8") == "untouched\n"
