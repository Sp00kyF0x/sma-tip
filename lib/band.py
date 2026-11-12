"""
SMA-Rohsignal mit Band (Hysterese) - eine gemeinsame Umsetzung für canary.py und backtest.py, damit Live-Signal
und Backtest garantiert dieselbe Regel verwenden. Die Werte stehen in strategie.toml ([sma] band_*).

  Ausstieg (RISK -> DEFENSIVE): Kurs <= SMA * (1 - exit_pct / 100)
  Einstieg (DEFENSIVE -> RISK): Kurs >  SMA * (1 + entry_pct / 100)
  Dazwischen bleibt der vorherige Zustand (Gedächtnis). Startzustand: Kurs > SMA.
  exit_pct = entry_pct = 0: identisch zum einfachen Rohsignal "Kurs > SMA".

Der Whipsaw-Filter (bestaetigung_aus/_ein) wird danach auf dieses Rohsignal angewendet.
"""

from __future__ import annotations

import numpy as np


def band_raw_risk(price: np.ndarray, sma: np.ndarray, exit_pct: float, entry_pct: float) -> np.ndarray:
    """Rohsignal je Tag (True = RISK) für Kurs- und SMA-Werte ohne Lücken."""
    price = np.asarray(price, dtype=float)
    sma = np.asarray(sma, dtype=float)
    if exit_pct == 0 and entry_pct == 0:
        return price > sma
    exit_th = sma * (1.0 - exit_pct / 100.0)
    entry_th = sma * (1.0 + entry_pct / 100.0)
    out = np.empty(len(price), dtype=bool)
    if len(price) == 0:
        return out
    state = bool(price[0] > sma[0])
    out[0] = state
    for i in range(1, len(price)):
        if state:
            if price[i] <= exit_th[i]:
                state = False
        elif price[i] > entry_th[i]:
            state = True
        out[i] = state
    return out


def next_close_thresholds(closes: np.ndarray, sma_days: int, exit_pct: float,
                          entry_pct: float) -> tuple[float, float]:
    """Indexstand, ab dem der NÄCHSTE Schlusskurs die Ausstiegs- bzw. Einstiegsschwelle erreicht. Die SMA des
    nächsten Tages enthält diesen Schlusskurs selbst: SMA' = (S + p) / n mit S = Summe der letzten n-1 Kurse.
    Ausstieg bei p <= f * SMA' mit f = 1 - exit/100  ->  p <= f * S / (n - f); Einstieg analog mit f = 1 + entry/100."""
    s = float(np.sum(np.asarray(closes, dtype=float)[-(sma_days - 1):]))
    f_out = 1.0 - exit_pct / 100.0
    f_in = 1.0 + entry_pct / 100.0
    return f_out * s / (sma_days - f_out), f_in * s / (sma_days - f_in)
