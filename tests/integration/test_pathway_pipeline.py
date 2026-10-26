"""Execute the real Pathway runtime; skipped when its optional wheel is absent."""

import csv
from collections import Counter
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "examples" / "parking.csv"
pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("pathway") is None,
    reason="Optional Pathway runtime absent; the Linux Pathway integration job installs it",
)


def command(source, output, mode="static"):
    return [
        sys.executable, str(ROOT / "stream_pricing.py"),
        "--input", str(source), "--output", str(output), "--mode", mode,
    ]


def read_changes(path):
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    # The streaming writer might currently be appending its last line.
    complete_lines = [line for line in content.splitlines(keepends=True) if line.endswith("\n")]
    return list(csv.DictReader(io.StringIO("".join(complete_lines))))


def quote_key(row):
    return row["lot_id"], row["timestamp"], float(row["demand"]), float(row["price"])


def same_quote(actual, expected):
    return actual[:2] == expected[:2] and actual[2:] == pytest.approx(expected[2:])


def consolidated_state(rows):
    state = Counter()
    for row in rows:
        state[quote_key(row)] += int(row["diff"])
    # Keep negative counts: an unmatched retraction must fail the state check.
    return {quote: count for quote, count in state.items() if count != 0}


def matches_state(rows, expected):
    actual = consolidated_state(rows)
    if len(actual) != len(expected):
        return False
    return all(
        same_quote(actual_quote, expected_quote) and actual_count == expected_count
        for (actual_quote, actual_count), (expected_quote, expected_count)
        in zip(sorted(actual.items()), sorted(expected.items()))
    )


def contains_change(rows, expected_quote, diff):
    return any(int(row["diff"]) == diff and same_quote(quote_key(row), expected_quote) for row in rows)


def test_static_fixture_executes_pathway(tmp_path):
    output = tmp_path / "quotes.csv"
    result = subprocess.run(command(FIXTURE, output), cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = read_changes(output)
    assert len(rows) == 4
    expected = {
        ("SYNTHETIC-A", "2016-12-01T09:00:00"): (0.4, 11.6),
        ("SYNTHETIC-A", "2016-12-01T10:00:00"): (1.89, 17.56),
        ("SYNTHETIC-B", "2016-12-01T09:00:00"): (2.75, 20.0),
        ("SYNTHETIC-B", "2016-12-01T10:00:00"): (-0.16, 9.36),
    }
    assert {(row["lot_id"], row["timestamp"]) for row in rows} == expected.keys()
    for row in rows:
        demand, price = expected[row["lot_id"], row["timestamp"]]
        assert float(row["demand"]) == pytest.approx(demand)
        assert float(row["price"]) == pytest.approx(price)
        assert int(row["diff"]) == 1
        assert int(row["time"]) >= 0


def test_invalid_capacity_fails_real_runtime(tmp_path):
    source = tmp_path / "invalid.csv"
    with FIXTURE.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        row = next(reader)
        fields = reader.fieldnames
    row["Capacity"] = "0"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    result = subprocess.run(
        command(source, tmp_path / "invalid-quotes.csv"), cwd=ROOT, capture_output=True, text=True, timeout=60
    )
    assert result.returncode != 0
    assert "Capacity must be positive" in result.stdout + result.stderr


def test_streaming_file_addition_replacement_and_removal(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    output = tmp_path / "quotes.csv"
    logs = tmp_path / "pathway.log"
    with FIXTURE.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        first, second = next(reader), next(reader)
        fields = reader.fieldnames

    def publish(filename, row):
        # Publish complete files atomically, as recommended for the CSV connector.
        staged = tmp_path / "incoming.tmp"
        with staged.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)
        staged.replace(source / filename)

    publish("seed.csv", first)
    with logs.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command(source, output, "streaming"), cwd=ROOT, stdout=log, stderr=log)
        try:
            def wait_for_state(expected, required_changes=()):
                deadline = time.monotonic() + 45
                rows = []
                while time.monotonic() < deadline:
                    assert process.poll() is None, logs.read_text(encoding="utf-8")
                    rows = read_changes(output)
                    if matches_state(rows, expected) and all(
                        contains_change(rows, quote, diff) for quote, diff in required_changes
                    ):
                        return rows
                    time.sleep(0.1)
                pytest.fail(
                    f"Timed out waiting for real Pathway state.\nExpected: {expected}\n"
                    f"Actual: {consolidated_state(rows)}\n{logs.read_text(encoding='utf-8')}"
                )

            seed_quote = ("SYNTHETIC-A", "2016-12-01T09:00:00", 0.4, 11.6)
            added_quote = ("SYNTHETIC-A", "2016-12-01T10:00:00", 1.89, 17.56)
            replacement_quote = ("SYNTHETIC-A", "2016-12-01T09:00:00", 0.5, 12.0)

            # The seed quote proves that the graph is live before subsequent changes.
            wait_for_state({seed_quote: 1})
            publish("new.csv", second)
            wait_for_state({seed_quote: 1, added_quote: 1})
            publish("seed.csv", {**first, "Occupancy": "20"})
            wait_for_state(
                {replacement_quote: 1, added_quote: 1},
                required_changes=((seed_quote, -1), (replacement_quote, 1)),
            )
            (source / "new.csv").unlink()
            wait_for_state({replacement_quote: 1}, required_changes=((seed_quote, -1), (added_quote, -1)))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
