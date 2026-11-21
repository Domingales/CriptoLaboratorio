"""Lectura diagnóstica de velas Binance con validación estricta y failover.

No modifica los motores predictivos ni emite señales. Solo se usan endpoints
oficiales Binance; el failover NO garantiza independencia de proveedor.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ENDPOINTS = (
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://data-api.binance.vision",
)
INTERVAL_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
SYMBOLS = (
    "BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOGE", "SHIB",
    "DOT", "AVAX", "TRX", "LINK", "POL", "ATOM", "LTC", "XLM",
    "NEAR", "ETC", "FIL", "HBAR", "EGLD", "AAVE", "VET",
    "THETA", "SAND", "ICP", "XTZ", "MKR", "GRT", "ENS",
)


class DataUnavailable(RuntimeError):
    """No hay datos suficientemente verificables para producir una señal."""


def validate_klines(rows, interval, now_ms=None, min_rows=200):
    """Rechaza series cortas, discontinuas, futuras, abiertas o incoherentes."""
    if interval not in INTERVAL_MS:
        raise ValueError("Intervalo no soportado")
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    if not isinstance(rows, list) or len(rows) < min_rows:
        raise DataUnavailable("Historial insuficiente")
    step = INTERVAL_MS[interval]
    previous = None
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            raise DataUnavailable("Formato OHLCV inválido")
        try:
            opening, closing = int(row[0]), int(row[6])
            op, hi, lo, cl, vol = map(float, row[1:6])
        except (ValueError, TypeError, OverflowError) as exc:
            raise DataUnavailable("OHLCV no numérico") from exc
        from math import isfinite
        if not all(map(isfinite, (op, hi, lo, cl, vol))):
            raise DataUnavailable("OHLCV no finito")
        if opening % step or closing != opening + step - 1:
            raise DataUnavailable("Marca temporal de vela inválida")
        if previous is not None and opening - previous != step:
            raise DataUnavailable("Hueco o duplicado de velas")
        if lo <= 0 or vol < 0 or hi < max(op, cl, lo) or lo > min(op, cl):
            raise DataUnavailable("Precios o volumen incoherentes")
        previous = opening
    if int(rows[-1][6]) >= now_ms:
        raise DataUnavailable("La última vela no está cerrada")
    if now_ms - int(rows[-1][6]) > step * 2:
        raise DataUnavailable("Serie desactualizada")
    return rows


def fetch_closed_klines(symbol, interval, limit=240, now_ms=None, opener=urlopen):
    """Devuelve velas cerradas validadas o falla explícitamente."""
    if symbol not in SYMBOLS or interval not in INTERVAL_MS:
        raise ValueError("Símbolo o intervalo no autorizado")
    if not 200 <= limit <= 1000:
        raise ValueError("Se requieren entre 200 y 1000 velas")
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    step = INTERVAL_MS[interval]
    # endTime fija el último cierre completo; no usar velas en formación.
    last_close = (now_ms // step) * step - 1
    query = urlencode({"symbol": symbol + "USDT", "interval": interval,
                       "limit": limit, "endTime": last_close})
    errors = []
    for endpoint in ENDPOINTS:
        url = endpoint + "/api/v3/klines?" + query
        try:
            with opener(url, timeout=8) as response:
                rows = json.loads(response.read())
            validate_klines(rows, interval, now_ms=now_ms, min_rows=200)
            if int(rows[-1][6]) != last_close:
                raise DataUnavailable("Falta la última vela cerrada")
            return {"source": endpoint, "symbol": symbol + "USDT",
                    "interval": interval, "retrieved_at": datetime.fromtimestamp(
                        now_ms / 1000, tz=timezone.utc).isoformat(), "rows": rows}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError,
                TypeError, DataUnavailable) as exc:
            errors.append(endpoint + ": " + str(exc))
    raise DataUnavailable("Ningún endpoint verificable: " + " | ".join(errors))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", choices=SYMBOLS, default="BTC")
    parser.add_argument("--interval", choices=INTERVAL_MS, default="1h")
    args = parser.parse_args()
    try:
        result = fetch_closed_klines(args.symbol, args.interval)
        print(json.dumps({k: v for k, v in result.items() if k != "rows"},
                         ensure_ascii=False))
        print("velas_validadas=", len(result["rows"]))
    except DataUnavailable as exc:
        print("DATOS_NO_VERIFICABLES:", exc)
        raise SystemExit(2)
