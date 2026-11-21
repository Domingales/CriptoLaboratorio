"""Pruebas offline del diagnóstico de velas; no requieren acceso a Binance."""
import json
import unittest
from unittest.mock import Mock
from research.market_data_resilience import (
    DataUnavailable, fetch_closed_klines, validate_klines,
)

STEP = 3_600_000
NOW = STEP * 1000 + 12345


def sample(n=240):
    first = (NOW // STEP - n) * STEP
    return [[first + i * STEP, "10", "11", "9", "10.5", "100",
             first + (i + 1) * STEP - 1, "0", 0, "0", "0", "0"]
            for i in range(n)]


class Response:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.rows).encode()


class MarketDataTests(unittest.TestCase):
    def test_valid_closed_contiguous_series(self):
        self.assertEqual(len(validate_klines(sample(), "1h", NOW)), 240)

    def test_gap_rejected(self):
        rows = sample()
        rows.pop(30)
        with self.assertRaises(DataUnavailable):
            validate_klines(rows, "1h", NOW)

    def test_open_candle_rejected(self):
        rows = sample()
        rows.append([NOW // STEP * STEP, "10", "11", "9", "10", "100",
                     (NOW // STEP + 1) * STEP - 1])
        with self.assertRaises(DataUnavailable):
            validate_klines(rows, "1h", NOW)

    def test_invalid_price_rejected(self):
        rows = sample()
        rows[0][2] = "8"
        with self.assertRaises(DataUnavailable):
            validate_klines(rows, "1h", NOW)

    def test_short_history_rejected(self):
        with self.assertRaises(DataUnavailable):
            validate_klines(sample(199), "1h", NOW)

    def test_fallback_after_network_error(self):
        calls = []

        def opener(url, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise OSError("DNS failed")
            return Response(sample())

        result = fetch_closed_klines("BTC", "1h", now_ms=NOW, opener=opener)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["source"], "https://api1.binance.com")
        self.assertEqual(len(result["rows"]), 240)

    def test_all_endpoints_fail_closed(self):
        def opener(url, timeout):
            raise OSError("DNS failed")

        with self.assertRaises(DataUnavailable):
            fetch_closed_klines("BTC", "1h", now_ms=NOW, opener=opener)


if __name__ == "__main__":
    unittest.main()
