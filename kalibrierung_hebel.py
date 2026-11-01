"""
Kalibrierung des synthetischen Hebel-Modells: SPY gegen reale ETFs
===================================================================

Zweck: die Kosten des synthetischen S&P-500-Assets aus echten Daten schätzen,
bevor sie in den Backtest wandern. Verglichen werden (siehe PRODUCTS):
  18MF.DE  Amundi MSCI USA 2x      (Hauptfall, Hebel in EUR vermutet)
  DBPG.DE  Xtrackers S&P 500 2x    (Hebel in USD vermutet, Sensitivität)
  SXR8.DE  iShares Core S&P 500    (1x, gleicher Index wie SPY)
  SXR4.DE  iShares MSCI USA        (1x, Indexlücke MSCI USA vs. S&P 500)

Modell (je Produkt mit Hebel L):
  Brutto-Reihe = täglich zurückgesetzter Hebel L auf SPY (Adj Close, also
  inkl. Dividenden), nach EUR umgerechnet. Zwei Hypothesen für den Wechselkurs:
    "EUR": erst nach EUR umrechnen, dann hebeln (Wechselkurs wird mitgehebelt,
           Finanzierung zum Euro-Zins),
    "USD": erst in USD hebeln, dann umrechnen (Wechselkurs wirkt einfach,
           Finanzierung zum US-Zins).
  Kosten: dX/dt = -(a + b * (L-1) * Zins(t)), dabei ist X der Logarithmus des
  Verhältnisses reales ETF / Brutto-Reihe. a = fixe Kosten p.a. (TER, Swap-
  Spread, Dividenden-Quellensteuer, Indexlücke ...), b = Durchleitung des
  Zinses (erwartet ~1). Beim 1x-Produkt entfällt der Zinsterm.

Methode:
  - Wöchentliche Stützpunkte (letzter gemeinsamer Handelstag je Woche). Der
    Xetra-Schluss (17:30) liegt vor dem US-Schluss; tägliche Differenzen sind
    deshalb verrauscht, im Niveau (Verhältnis) heben sich die Versätze auf.
  - Regression im Niveau: X(t) = c - a*t - b*S(t) mit S(t) = Summe (L-1) *
    Zins * dt; Standardfehler nach Newey-West (HAC). Zusätzlich a bei fest
    vorgegebenem b = 1 ("a1") und für beide Hälften des Zeitraums.
  - Wechselkurs-Test: Regression der Wochen- bzw. Monatsrenditen des ETFs auf
    SPY (USD) und den Wechselkurs. Koeffizient auf den Wechselkurs ~ L heißt
    "Wechselkurs wird mitgehebelt", ~ 1 heißt "nicht".
  - Zeitversatz: Tagesrenditen des ETFs (durch L geteilt) auf die SPY-Rendite
    desselben Tages und des Vortags. Das Verhältnis zeigt, welcher Anteil der
    US-Tagesbewegung bei Xetra-Schluss schon eingepreist ist.
  - Gegenproben: SPY gegen ^SP500TR (Abzug von SPY selbst) und SXR4 gegen
    SXR8 (Indexlücke MSCI USA / S&P 500, inkl. TER-Unterschied).
  - Der Wechselkurs EUR=X wird von einzelnen Tages-Ausreißern bereinigt
    (Tagesbewegung > SPIKE_THRESHOLD, die am Folgetag zurückläuft); gefundene
    Tage werden ausgegeben. Mehrtägige Fehler erkennt das nicht.

Zinsreihen: FRED (öffentlicher CSV-Export, Internet nötig; Cache in yf_data/FRED_<ID>.csv wie in backtest.py, bei Ausfall mit Cache weiterrechnen oder klare Meldung): USD "DFF" (Fed
Funds), EUR "ECBDFR" (EZB-Einlagezins; €STR lag nach 2019 etwas darunter,
EONIA davor etwas darüber - Näherung, einmalig in den Ergebnissen zu
berücksichtigen). TER-Angaben in PRODUCTS bitte mit den Factsheets abgleichen.

Ausgabe: kalibrierung/kalibrierung_ergebnis.txt und kalibrierung/01_verhaeltnis.png.

Aufruf: python kalibrierung_hebel.py
"""

from __future__ import annotations

import io
import re
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
except ImportError as exc:
    print(f"Fehler: Benötigtes Paket nicht gefunden ({exc.name}).\n"
          f"Bitte einmalig ausführen: pip install -r requirements.txt")
    raise SystemExit(1) from None

from yf_data import (
    BERLIN_TZ,
    compute_query_end_date,
    load_prices,
)

# ----------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------
SPY_TICKER = "SPY"
TR_REFERENCE_TICKER = "^SP500TR"      # Gegenprobe (None = aus)
FX_TICKER = "EUR=X"                   # EUR je 1 USD
FRED_RATES = {"EUR": "ECBDFR", "USD": "DFF"}     # Prozent p.a.
EARLIEST_POSSIBLE_DATE = pd.Timestamp("1990-01-01")

# "hauptfall": Hypothese, die in der Jahrestabelle ausgewiesen wird.
# "ter": laut Factsheet (bitte prüfen), None = unbekannt.
PRODUCTS = {
    "18MF.DE": {"name": "Amundi MSCI USA 2x", "leverage": 2.0, "ter": 0.0050, "hauptfall": "EUR",
                "break_days": ["2013-01-02"]},   # yf_data skaliert hier (Faktor ~282), Rendite = 0 %,
    "DBPG.DE": {"name": "Xtrackers S&P 500 2x", "leverage": 2.0, "ter": 0.0060, "hauptfall": "USD"},
    "SXR8.DE": {"name": "iShares Core S&P 500", "leverage": 1.0, "ter": 0.0007, "hauptfall": "EUR"},
    "SXR4.DE": {"name": "iShares MSCI USA", "leverage": 1.0, "ter": 0.0003, "hauptfall": "EUR",
                "usable_from": "2011-01-01"},
}
START_FROM = "2011-01-01"     # frühere ETF-Kurse sind bei Yahoo teils fehlerhaft (siehe Auswertung)
JUMP_K = 6.0                  # Wochen mit |ΔX| über K * robuster Streuung gelten als Datenfehler
JUMP_MIN = 0.02               # ... mindestens aber 2 %
TRIM_K = 5.0                  # Ausreißer-Grenze in den Renditeregressionen (Vielfache der robusten Streuung)
SPIKE_SUSPECT = 0.02          # Wechselkurs-Verdachtstage (nur Anzeige, keine Bereinigung)
SPIKE_THRESHOLD = 0.04        # Tagesbewegung des Wechselkurses, ab der ein Ausreißer geprüft wird
HAC_LAGS_LEVELS = 26          # Newey-West-Lags (Wochen) für die Niveau-Regression
HAC_LAGS_RETURNS = 4
ROLLING_YEARS = 3
OUTPUT_DIR = Path("kalibrierung")


# ----------------------------------------------------------------------
# Daten
# ----------------------------------------------------------------------
_ADJ_CACHE: dict = {}


def get_adj_close(ticker: str, query_end_date: pd.Timestamp) -> pd.Series:
    """Adj-Close-Reihe über yf_data (Vollständigkeitsprüfung, Sprung-
    korrektur, Sicherheits-Cutoff), einmal je Ticker zwischengespeichert."""
    key = (ticker, query_end_date)
    if key not in _ADJ_CACHE:
        series, _ = load_prices(ticker, EARLIEST_POSSIBLE_DATE, query_end_date)
        _ADJ_CACHE[key] = series
    return _ADJ_CACHE[key].copy()


def load_etf(key: str, cfg: dict, query_end_date: pd.Timestamp) -> pd.Series:
    """ETF-Reihe ab dem späteren von START_FROM und cfg["usable_from"]."""
    etf = get_adj_close(key, query_end_date)
    start = max(pd.Timestamp(START_FROM), pd.Timestamp(cfg.get("usable_from", START_FROM)))
    return etf.loc[etf.index >= start]


FRED_CACHE_DIR = Path(__file__).resolve().parent / "yf_data"   # gemeinsam mit backtest.py


class FredUnavailableError(RuntimeError):
    """FRED nicht erreichbar bzw. liefert keine CSV, und es gibt keinen
    brauchbaren Cache. Wird in __main__ ohne Traceback gemeldet."""


def _describe_failure(exc: Exception) -> str:
    """Kurze, lesbare Ursache statt Roh-Antwort: bei einer HTML-Seite deren
    <title> (z.B. 'Site Maintenance | St. Louis Fed'), sonst die Meldung."""
    msg = str(exc)
    m = re.search(r"<title>\s*(.*?)\s*<", msg.replace("\\n", " "), re.I)
    if m and m.group(1):
        return f"FRED antwortet mit einer Webseite statt Daten: \u201e{m.group(1)}\u201c"
    if "keine FRED-CSV" in msg:
        return "FRED antwortet mit einer Webseite statt Daten"
    return msg


def parse_fred_csv(text: str, series_id: str) -> pd.Series:
    """FRED-CSV (Datum, Wert) in eine Serie in PROZENT; "." wird verworfen. Das
    Format wird vorher geprüft, damit eine Fehlerseite (HTML, Sperre, leere
    Antwort) erkannt wird und nicht in den Cache gelangt."""
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    if "," not in first or series_id not in first or "<" in first:
        raise ValueError(f"keine FRED-CSV f\u00fcr {series_id} (Anfang der Antwort: {text.strip()[:120]!r})")
    df = pd.read_csv(io.StringIO(text))
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    out = pd.Series(values.to_numpy(dtype=float), index=pd.to_datetime(df.iloc[:, 0])).dropna().sort_index()
    if out.empty:
        raise ValueError(f"FRED {series_id}: keine Werte.")
    return out


def load_fred_rate(series_id: str) -> pd.Series:
    """Zinsreihe (Prozent p.a.) von FRED. Die Antwort wird erst auf ein gültiges
    CSV-Format geprüft und dann in yf_data/FRED_<ID>.csv zwischengespeichert
    (derselbe Cache wie in backtest.py; ein gültiger Cache wird nie durch eine
    Fehlerseite überschrieben). Schlägt Abruf oder Prüfung fehl, wird der Cache
    (mit Warnung) genutzt; ohne gültigen Cache bricht die Funktion mit
    FredUnavailableError ab."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    cache = FRED_CACHE_DIR / f"FRED_{series_id}.csv"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (taa-kalibrierung)"})
        with urllib.request.urlopen(request, timeout=30) as resp:
            text = resp.read().decode("utf-8")
        out = parse_fred_csv(text, series_id)
        FRED_CACHE_DIR.mkdir(exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        return out
    except Exception as exc:                                   # noqa: BLE001
        reason = _describe_failure(exc)
        if not cache.exists():
            raise FredUnavailableError(
                f"FRED-Daten {series_id} sind aktuell nicht abrufbar und lokal nicht vorhanden.\n"
                f"  Ursache: {reason}\n"
                f"  Was tun: sp\u00e4ter erneut starten, oder\n"
                f"  die CSV im Browser von {url} laden\n"
                f"  und als {cache} speichern.") from None
        print(f"[warn]     FRED {series_id}: Abruf fehlgeschlagen ({reason}), nutze Cache {cache.name}.")
        try:
            return parse_fred_csv(cache.read_text(encoding="utf-8"), series_id)
        except ValueError:
            raise FredUnavailableError(
                f"FRED-Daten {series_id}: Abruf fehlgeschlagen ({reason}) und der lokale Cache ist ung\u00fcltig.\n"
                f"  Was tun: {cache} l\u00f6schen und sp\u00e4ter erneut starten, oder die CSV im Browser\n"
                f"  von {url} laden und dort speichern.") from None


def clean_fx_spikes(fx: pd.Series, threshold: float) -> tuple[pd.Series, list[tuple]]:
    """Ersetzt eintägige Ausreißer (Bewegung > threshold, die am nächsten Tag
    zu mehr als der Hälfte zurückläuft) durch den Vortageswert. Gibt die
    bereinigte Reihe und die Liste (Datum, Bewegung, Gegenbewegung) zurück."""
    values = fx.to_numpy(dtype=float).copy()
    found = []
    for i in range(1, len(values) - 1):
        r1 = values[i] / values[i - 1] - 1.0
        if abs(r1) <= threshold:
            continue
        r2 = values[i + 1] / values[i] - 1.0
        if r1 * r2 < 0 and abs(values[i + 1] / values[i - 1] - 1.0) < 0.5 * abs(r1):
            found.append((fx.index[i], r1, r2))
            values[i] = values[i - 1]
    return pd.Series(values, index=fx.index), found


def fx_suspects(fx: pd.Series, threshold: float) -> list[tuple]:
    """Tage mit Bewegung > threshold, die am Folgetag zu mehr als der Hälfte
    zurückläuft (nur zur Anzeige, nach der Bereinigung von clean_fx_spikes)."""
    values = fx.to_numpy(dtype=float)
    found = []
    for i in range(1, len(values) - 1):
        r1 = values[i] / values[i - 1] - 1.0
        if abs(r1) <= threshold:
            continue
        r2 = values[i + 1] / values[i] - 1.0
        if r1 * r2 < 0 and abs(values[i + 1] / values[i - 1] - 1.0) < 0.5 * abs(r1):
            found.append((fx.index[i], r1, r2))
    return found


def clean_level_jumps(x: pd.Series, k: float, minimum: float
                      ) -> tuple[pd.Series, list[tuple], list[tuple]]:
    """Entfernt DAUERHAFTE Sprünge aus der Verhältnis-Reihe X. Als Ausreißer gilt
    eine Woche mit |ΔX| > k * robuster Streuung (MAD), mindestens `minimum`.
    Läuft die Bewegung in den 4 Wochen danach oder wurde sie in den 4 Wochen
    davor aufgebaut zu mindestens der Hälfte zurück bzw. hin, ist sie
    VORÜBERGEHEND (typisch: Zeitversatz an extremen Freitagen, Wochenstichtag
    vor der US-Bewegung) und bleibt unverändert. Nur bleibende Sprünge (z.B.
    ein Kursfehler) werden durch die mittlere Änderung ersetzt.
    Rückgabe: (bereinigte Reihe, entfernte Sprünge, vorübergehende Ausreißer)."""
    dx = x.diff().dropna()
    med = float(dx.median())
    mad = float((dx - med).abs().median()) * 1.4826
    thr = max(k * mad, minimum)
    flagged = [d for d in dx.index if abs(dx.loc[d] - med) > thr]
    values = dx.to_numpy()
    persistent, transient = [], []
    clean = dx.copy()
    for d in flagged:
        i = dx.index.get_loc(d)
        jump = float(values[i] - med)
        after = float(values[i + 1:i + 5].sum() - med * len(values[i + 1:i + 5]))
        before = float(values[max(i - 4, 0):i].sum() - med * len(values[max(i - 4, 0):i]))
        offset = max(-after * np.sign(jump), -before * np.sign(jump))
        if offset >= 0.5 * abs(jump):
            transient.append((d, float(values[i])))
        else:
            persistent.append((d, float(values[i])))
            clean.loc[d] = med
    out = pd.concat([pd.Series([0.0], index=[x.index[0]]), clean]).cumsum()
    return out, persistent, transient


# ----------------------------------------------------------------------
# Statistik
# ----------------------------------------------------------------------
def ols_hac(y: np.ndarray, X: np.ndarray, lags: int) -> dict:
    """OLS mit Newey-West-Standardfehlern. Gibt beta, se, Residuen und R² zurück."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    u = X * resid[:, None]
    s = u.T @ u
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1.0 - lag / (lags + 1.0)
        g = u[lag:].T @ u[:-lag]
        s += w * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv * (n / max(n - k, 1))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    return {"beta": beta, "se": np.sqrt(np.clip(np.diag(cov), 0.0, None)), "resid": resid, "r2": r2, "n": n}


def ols_hac_trimmed(y: np.ndarray, X: np.ndarray, lags: int, k: float) -> dict:
    """Wie ols_hac, aber Beobachtungen mit |Residuum| > k * robuster Streuung
    werden einmal verworfen und neu geschätzt ("dropped" = Anzahl)."""
    res = ols_hac(y, X, lags)
    sigma = 1.4826 * float(np.median(np.abs(res["resid"] - np.median(res["resid"]))))
    keep = np.abs(res["resid"]) <= k * sigma if sigma > 0 else np.ones(len(y), dtype=bool)
    if keep.sum() < len(y):
        res = ols_hac(np.asarray(y)[keep], np.asarray(X)[keep], lags)
    res["dropped"] = int(len(y) - keep.sum())
    return res


def weekly_points(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Letzter Handelstag je ISO-Woche."""
    iso = index.isocalendar()
    key = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    series = pd.Series(index, index=index)
    return pd.DatetimeIndex(series.groupby(key).last().to_numpy())


def funding_integral(rate_pct: pd.Series, dates: pd.DatetimeIndex, start: pd.Timestamp) -> pd.Series:
    """S(t) = Summe über Kalendertage von Zins/100/365 seit `start`, an `dates`."""
    days = pd.date_range(start, dates.max(), freq="D")
    rate = rate_pct.reindex(rate_pct.index.union(days)).ffill().reindex(days)
    if rate.isna().any():
        raise ValueError(f"Zinsreihe beginnt erst nach {start.date()} - Zeitraum verkürzen.")
    cum = (rate / 100.0 / 365.0).cumsum()
    return (cum - cum.iloc[0]).reindex(dates)


def years_since(dates: pd.DatetimeIndex, start: pd.Timestamp) -> np.ndarray:
    return np.asarray((dates - start).days, dtype=float) / 365.25


def build_gross(spy: pd.Series, fx_on_spy: pd.Series, leverage: float, hypothesis: str) -> pd.Series:
    """Brutto-Reihe (ohne Kosten) auf dem SPY-Kalender, Start = 1."""
    r_spy = spy.pct_change().fillna(0.0)
    r_fx = fx_on_spy.pct_change().fillna(0.0)
    if hypothesis == "EUR":
        r = leverage * ((1.0 + r_spy) * (1.0 + r_fx) - 1.0)
    elif hypothesis == "USD":
        r = (1.0 + leverage * r_spy) * (1.0 + r_fx) - 1.0
    else:
        raise ValueError(hypothesis)
    return (1.0 + r).cumprod()


def neutralize_break_days(etf: pd.Series, gross: pd.Series, break_days: list[str]) -> tuple[pd.Series, list[tuple]]:
    """yf_data skaliert die Reihe vor einem Kursbruch (z.B. 18MF.DE am 02.01.2013,
    Faktor ~282) so, dass die Rendite des Bruchtags exakt 0 % ist; die echte Bewegung
    über den Bruch (hier inkl. der Tage, an denen Xetra geschlossen hatte) geht dabei
    verloren. Damit das Modell keinen künstlichen Dauerschritt sieht, wird dessen
    Rendite vom letzten Handelstag davor bis zum Bruchtag ebenfalls auf 0 gesetzt.
    Die Bruchtage stehen je Produkt in PRODUCTS["break_days"] (automatische Erkennung
    wäre unsicher: ETF-Stillstandstage mit Rendite 0 sehen genauso aus).
    Rückgabe: (angepasste Brutto-Reihe, [(Datum, entfernte Modellrendite)])."""
    out = gross.copy()
    found = []
    for ds in break_days:
        d = pd.Timestamp(ds)
        pos = etf.index.searchsorted(d)
        if pos <= 0 or pos >= len(etf) or etf.index[pos] != d:
            continue
        prev = etf.index[pos - 1]          # letzter ETF-Handelstag vor dem Bruch
        lg = float(np.log(out.asof(d)) - np.log(out.asof(prev)))
        out.loc[out.index >= d] *= np.exp(-lg)
        found.append((d, lg))
    return out, found


def pct(v: float, digits: int = 2) -> str:
    return f"{v * 100:+.{digits}f}%" if pd.notna(v) else "n/a"


# ----------------------------------------------------------------------
# Auswertungen
# ----------------------------------------------------------------------
def fit_levels(x_log: pd.Series, s_funding: pd.Series | None, start: pd.Timestamp) -> dict:
    """Niveau-Regression X = c - a*t - b*S (bzw. nur a ohne S)."""
    t = years_since(x_log.index, start)
    y = x_log.to_numpy()
    ones = np.ones_like(t)
    out: dict = {"n": len(y)}
    if s_funding is None:
        res = ols_hac(y, np.column_stack([ones, t]), HAC_LAGS_LEVELS)
        out.update(a=-res["beta"][1], a_se=res["se"][1], b=float("nan"), b_se=float("nan"),
                   a1=-res["beta"][1], a1_se=res["se"][1], resid=res["resid"])
    else:
        s = s_funding.to_numpy()
        res = ols_hac(y, np.column_stack([ones, t, s]), HAC_LAGS_LEVELS)
        out.update(a=-res["beta"][1], a_se=res["se"][1], b=-res["beta"][2], b_se=res["se"][2],
                   resid=res["resid"])
        res1 = ols_hac(y + s, np.column_stack([ones, t]), HAC_LAGS_LEVELS)
        out.update(a1=-res1["beta"][1], a1_se=res1["se"][1])
    out["resid_std"] = float(np.std(out["resid"]))
    # Stabilität: a1 in den beiden Hälften
    half = len(y) // 2
    halves = {}
    for label, sl in (("erste Hälfte", slice(0, half)), ("zweite Hälfte", slice(half, None))):
        yy = y[sl] + (s_funding.to_numpy()[sl] if s_funding is not None else 0.0)
        tt = t[sl]
        if len(yy) > 20:
            rr = ols_hac(yy, np.column_stack([np.ones_like(tt), tt]), HAC_LAGS_LEVELS)
            halves[label] = (-rr["beta"][1], rr["se"][1])
    out["halves"] = halves
    # rollierende Kosten über ROLLING_YEARS Jahre (realisiert, p.a.)
    win = int(ROLLING_YEARS * 52)
    if len(y) > win:
        roll = -(y[win:] - y[:-win]) / ROLLING_YEARS
        out["rolling"] = (float(roll.min()), float(np.median(roll)), float(roll.max()))
    return out


def yearly_table(x_log: pd.Series, s_funding: pd.Series | None) -> list[tuple]:
    """Je Kalenderjahr: realisierte Kosten (p.a.-Punkte), Finanzierungsanteil."""
    rows = []
    for year in sorted(set(x_log.index.year)):
        sel = x_log.index.year == year
        xs = x_log.loc[sel]
        if len(xs) < 4:
            continue
        # Jahresbeginn = letzter Punkt des Vorjahres (falls vorhanden)
        prev = x_log.loc[x_log.index.year == year - 1]
        x0 = prev.iloc[-1] if len(prev) else xs.iloc[0]
        d0 = prev.index[-1] if len(prev) else xs.index[0]
        realized = -(xs.iloc[-1] - x0)
        funding = np.nan
        if s_funding is not None:
            s0 = s_funding.loc[d0]
            funding = s_funding.loc[xs.index[-1]] - s0
        rows.append((year, realized, funding, len(xs)))
    return rows


def fx_leverage_test(etf: pd.Series, spy: pd.Series, fx_on_spy: pd.Series, points: pd.DatetimeIndex) -> dict:
    """Rendite des ETFs auf SPY (USD) und Wechselkurs, an den Stützpunkten."""
    spy_p = np.log(spy.reindex(points)).diff().dropna()
    fx_p = np.log(fx_on_spy.reindex(points)).diff().dropna()
    y = np.log(etf.reindex(points)).diff().dropna()
    df = pd.concat([y, spy_p, fx_p], axis=1, keys=["y", "spy", "fx"]).dropna()
    if len(df) < 30:
        return {}
    res = ols_hac_trimmed(df["y"].to_numpy(), np.column_stack([np.ones(len(df)), df["spy"], df["fx"]]),
                          HAC_LAGS_RETURNS, TRIM_K)
    return {"n": res["n"], "dropped": res["dropped"], "b_eq": res["beta"][1], "b_eq_se": res["se"][1],
            "b_fx": res["beta"][2], "b_fx_se": res["se"][2], "r2": res["r2"]}


def timing_test(etf: pd.Series, spy: pd.Series, leverage: float, start: pd.Timestamp) -> dict:
    """Tagesrendite des ETFs (durch L) auf die SPY-Rendite von t, t-1 und t+1
    (t+1 ist Kontrolle und sollte ~0 sein)."""
    common = etf.index.intersection(spy.index)
    common = common[common >= start]
    y = np.log(etf.reindex(common)).diff() / leverage
    s0 = np.log(spy.reindex(common)).diff()
    df = pd.concat([y, s0, s0.shift(1), s0.shift(-1)], axis=1, keys=["y", "s0", "s1", "sp"]).dropna()
    if len(df) < 100:
        return {}
    res = ols_hac_trimmed(df["y"].to_numpy(), np.column_stack([np.ones(len(df)), df["s0"], df["s1"], df["sp"]]),
                          5, TRIM_K)
    b0, b1 = res["beta"][1], res["beta"][2]
    return {"n": res["n"], "dropped": res["dropped"], "b0": b0, "b0_se": res["se"][1], "b1": b1, "b1_se": res["se"][2],
            "b_lead": res["beta"][3], "share": b0 / (b0 + b1) if (b0 + b1) else float("nan"), "r2": res["r2"]}


def pair_drift(a: pd.Series, b: pd.Series, start: pd.Timestamp | None = None) -> dict:
    """Drift von log(a/b) pro Jahr (wöchentlich). Negativ = a bleibt hinter b zurück."""
    common = a.index.intersection(b.index)
    if start is not None:
        common = common[common >= start]
    pts = weekly_points(common)
    x = (np.log(a.reindex(pts)) - np.log(b.reindex(pts)))
    x = x - x.iloc[0]
    x, jumps, _ = clean_level_jumps(x, JUMP_K, JUMP_MIN)
    t = years_since(x.index, x.index[0])
    res = ols_hac(x.to_numpy(), np.column_stack([np.ones_like(t), t]), HAC_LAGS_LEVELS)
    return {"drift": res["beta"][1], "se": res["se"][1], "start": pts[0], "end": pts[-1],
            "years": yearly_table(x, None), "jumps": jumps}


# ----------------------------------------------------------------------
# Hauptprogramm
# ----------------------------------------------------------------------
def run() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    now = datetime.now(BERLIN_TZ)
    query_end = compute_query_end_date(now)
    lines: list[str] = ["=" * 70, "Kalibrierung des synthetischen Hebel-Modells (SPY gegen reale ETFs)",
                        f"Erstellt: {now.strftime('%Y-%m-%d %H:%M:%S')} (Berlin), Kurse bis {query_end.date()}",
                        "=" * 70]

    def emit(text: str) -> None:
        print(text)
        lines.append(text)

    spy = get_adj_close(SPY_TICKER, query_end)
    fx_raw = get_adj_close(FX_TICKER, query_end)
    fx, spikes = clean_fx_spikes(fx_raw, SPIKE_THRESHOLD)
    if spikes:
        emit(f"\nWechselkurs {FX_TICKER}: {len(spikes)} eintägige(r) Ausreißer bereinigt:")
        for d, r1, r2 in spikes:
            emit(f"  {d.date()}  {r1:+.1%} am Tag, {r2:+.1%} am Folgetag")
    else:
        emit(f"\nWechselkurs {FX_TICKER}: keine eintägigen Ausreißer über {SPIKE_THRESHOLD:.0%} gefunden.")
    suspects = fx_suspects(fx, SPIKE_SUSPECT)
    if suspects:
        emit(f"  Verdachtstage {SPIKE_SUSPECT:.0%}-{SPIKE_THRESHOLD:.0%} (nicht bereinigt, bitte prüfen): " +
             ", ".join(f"{d.date()} ({r1:+.1%}/{r2:+.1%})" for d, r1, r2 in suspects))
    fx_on_spy = fx.reindex(spy.index.union(fx.index)).ffill().reindex(spy.index).dropna()
    spy = spy.loc[fx_on_spy.index]

    rates = {cur: load_fred_rate(sid) for cur, sid in FRED_RATES.items()}

    results: dict = {}
    plot_data: list = []
    emit("\n" + "-" * 70 + "\n1) Kosten je Produkt und Hypothese (wöchentlich, Niveau-Regression)\n" + "-" * 70)
    emit("a  = fixe Kosten p.a. (frei geschätzt), b = Durchleitung des Zinses, "
         "a1 = fixe Kosten bei b = 1.\nSE = Newey-West-Standardfehler. 'Resid.' = Streuung der "
         "Abweichung vom Modell (kleiner = besser).")
    for key, cfg in PRODUCTS.items():
        lev = cfg["leverage"]
        try:
            etf = load_etf(key, cfg, query_end)
        except Exception as exc:                               # noqa: BLE001
            emit(f"\n{key}: Daten nicht ladbar ({exc}) - übersprungen.")
            continue
        hyps = ["EUR", "USD"] if lev != 1.0 else ["EUR"]
        results[key] = {}
        for hyp in hyps:
            gross = build_gross(spy, fx_on_spy, lev, hyp)
            gross, breaks = neutralize_break_days(etf, gross, cfg.get("break_days", []))
            common = etf.index.intersection(gross.index)
            pts = weekly_points(common)
            if len(pts) < 60:
                emit(f"\n{key}: zu wenig gemeinsame Daten ({len(pts)} Wochen).")
                continue
            x_raw = np.log(etf.reindex(pts)) - np.log(gross.reindex(pts))
            x_raw = x_raw - x_raw.iloc[0]
            x, jumps, transient = clean_level_jumps(x_raw, JUMP_K, JUMP_MIN)
            start = pts[0]
            s_fund = None
            if lev != 1.0:
                s_fund = (lev - 1.0) * funding_integral(rates[hyp], pts, start)
            fit = fit_levels(x, s_fund, start)
            fit_raw = fit_levels(x_raw, s_fund, start)
            fit.update(points=pts, x=x, s=s_fund, start=start, jumps=jumps, raw_a1=fit_raw["a1"],
                       raw_resid=fit_raw["resid_std"])
            results[key][hyp] = fit
            if lev != 1.0:
                label = f"{key}, Hebel in {hyp}, Zins {FRED_RATES[hyp]}"
            else:
                label = f"{key}"
            emit(f"\n{label}  ({cfg['name']}), {pts[0].date()} bis {pts[-1].date()}, {fit['n']} Wochen")
            for bd, lg in breaks:
                emit(f"  Kursbruch-Korrektur durch yf_data am {bd.date()}: Modellrendite {lg * 100:+.1f}% "
                     f"über das Intervall ebenfalls entfernt (ETF-Rendite dort 0 %).")
            ter = cfg.get("ter")
            if lev != 1.0:
                emit(f"  a  = {pct(fit['a'])} (SE {fit['a_se'] * 100:.2f})   b = {fit['b']:.2f} (SE {fit['b_se']:.2f})")
                emit(f"  a1 = {pct(fit['a1'])} (SE {fit['a1_se'] * 100:.2f})   Resid. {fit['resid_std'] * 100:.2f}%")
            else:
                emit(f"  Kosten p.a. = {pct(fit['a'])} (SE {fit['a_se'] * 100:.2f})   Resid. {fit['resid_std'] * 100:.2f}%")
            if jumps:
                emit(f"  bleibende Sprünge entfernt ({len(jumps)} Wochen, ΔX gegen Modell): " +
                     ", ".join(f"{d.date()} ({v:+.1%})" for d, v in jumps[:12]) +
                     (" ..." if len(jumps) > 12 else ""))
                emit(f"  (ohne Bereinigung: a1 {pct(fit_raw['a1'])}, Resid. {fit_raw['resid_std'] * 100:.2f}%)")
            if transient:
                emit(f"  vorübergehende Ausreißer, NICHT entfernt ({len(transient)} Wochen): " +
                     ", ".join(f"{d.date()} ({v:+.1%})" for d, v in transient[:12]) +
                     (" ..." if len(transient) > 12 else ""))
            top = x_raw.diff().dropna().abs().sort_values(ascending=False).head(5)
            emit("  größte Wochenabweichungen (Rohdaten): " +
                 ", ".join(f"{d.date()} ({x_raw.diff().loc[d]:+.1%})" for d in top.index))
            if ter is not None:
                emit(f"  TER laut Konfiguration {pct(ter)} -> über TER hinaus (Swap-Spread, Quellensteuer, "
                     f"Indexlücke ...): {pct(fit['a1'] - ter)}")
            for hl, (ah, seh) in fit["halves"].items():
                emit(f"  a1 {hl}: {pct(ah)} (SE {seh * 100:.2f})")
            if "rolling" in fit:
                lo, med, hi = fit["rolling"]
                emit(f"  realisierte Kosten über {ROLLING_YEARS} Jahre (p.a.): min {pct(lo)}, Median {pct(med)}, "
                     f"max {pct(hi)}")
            plot_data.append((label, x, fit))

    # Welche Hypothese passt besser?
    emit("\n" + "-" * 70 + "\n2) Welche Hebelwährung passt? (Streuung vom Modell, Wechselkurs-Test)\n" + "-" * 70)
    for key, cfg in PRODUCTS.items():
        lev = cfg["leverage"]
        if key not in results or not results[key]:
            continue
        if lev != 1.0 and set(results[key]) == {"EUR", "USD"}:
            r_e, r_u = results[key]["EUR"]["resid_std"], results[key]["USD"]["resid_std"]
            better = "EUR" if r_e < r_u else "USD"
            emit(f"\n{key}: Streuung vom Modell EUR {r_e * 100:.2f}% gegen USD {r_u * 100:.2f}% -> "
                 f"{better} passt besser.")
        etf = load_etf(key, cfg, query_end)
        pts_all = weekly_points(etf.index.intersection(spy.index))
        month_end = ~pd.Series(pts_all.to_period("M")).duplicated(keep="last").to_numpy()
        for label, pts in (("wöchentlich", pts_all), ("monatlich", pts_all[month_end])):
            t = fx_leverage_test(etf, spy, fx_on_spy, pts)
            if not t:
                continue
            emit(f"  Wechselkurs-Test {key} ({label}, n={t['n']}, {t['dropped']} Ausreißer entfernt): "
                 f"Koeffizient auf SPY {t['b_eq']:.2f} (SE {t['b_eq_se']:.2f}), "
                 f"auf Wechselkurs {t['b_fx']:.2f} (SE {t['b_fx_se']:.2f}), R² {t['r2']:.2f}")
        if lev != 1.0:
            emit(f"  Erwartung: Wechselkurs-Koeffizient ~ {lev:g} bei Hebel in EUR, ~ 1 bei Hebel in USD.")
        else:
            emit("  Erwartung: Wechselkurs-Koeffizient ~ 1 (physische bzw. 1x-Replikation).")

    emit("\n" + "-" * 70 + "\n3) Zeitversatz (Xetra-Schluss 17:30 gegen US-Schluss)\n" + "-" * 70)
    emit("Tagesrendite des ETFs (durch Hebel geteilt) auf die SPY-Rendite am selben Tag (t), am "
         "Vortag (t-1) und am Folgetag (t+1, Kontrolle). 'eingepreist' = t / (t + t-1).")
    timing_results = {}
    for key, cfg in PRODUCTS.items():
        if key not in results or not results[key]:
            continue
        etf = load_etf(key, cfg, query_end)
        start = next(iter(results[key].values()))["start"]
        tm = timing_test(etf, spy, cfg["leverage"], start)
        if not tm:
            continue
        timing_results[key] = tm
        emit(f"  {key}: t {tm['b0']:.2f} (SE {tm['b0_se']:.2f}), t-1 {tm['b1']:.2f} (SE {tm['b1_se']:.2f}), "
             f"t+1 {tm['b_lead']:.2f}, eingepreist {tm['share']:.0%}, R² {tm['r2']:.2f}, n={tm['n']} "
             f"({tm['dropped']} Ausreißer entfernt)")

    emit("\n" + "-" * 70 + "\n4) Gegenproben\n" + "-" * 70)
    if TR_REFERENCE_TICKER:
        try:
            tr = get_adj_close(TR_REFERENCE_TICKER, query_end)
            pd_ = pair_drift(spy, tr)
            emit(f"  SPY gegen {TR_REFERENCE_TICKER} (Gesamtertragsindex, brutto): {pct(pd_['drift'])} p.a. "
                 f"(SE {pd_['se'] * 100:.2f}), {pd_['start'].date()} bis {pd_['end'].date()} "
                 f"- Abzug von SPY selbst (TER 0,09 %, Dividenden-Timing).")
        except Exception as exc:                               # noqa: BLE001
            emit(f"  SPY gegen {TR_REFERENCE_TICKER}: nicht auswertbar ({exc}).")
    if "SXR4.DE" in PRODUCTS and "SXR8.DE" in PRODUCTS:
        try:
            a = load_etf("SXR4.DE", PRODUCTS["SXR4.DE"], query_end)
            b = load_etf("SXR8.DE", PRODUCTS["SXR8.DE"], query_end)
            pd_ = pair_drift(a, b)
            emit(f"  SXR4.DE (MSCI USA) gegen SXR8.DE (S&P 500): {pct(pd_['drift'])} p.a. "
                 f"(SE {pd_['se'] * 100:.2f}), {pd_['start'].date()} bis {pd_['end'].date()} "
                 f"- Indexlücke plus TER-Unterschied.")
            rows = " ".join(f"{y}:{pct(v, 1)}" for y, v, _, _ in pd_["years"])
            emit(f"    pro Jahr (Differenz): {rows}")
            if pd_["jumps"]:
                emit("    bleibende Sprünge entfernt: " + ", ".join(f"{d.date()} ({v:+.1%})" for d, v in pd_["jumps"][:12]))
        except Exception as exc:                               # noqa: BLE001
            emit(f"  SXR4 gegen SXR8: nicht auswertbar ({exc}).")

    emit("\n" + "-" * 70 + "\n5) Jahre im Detail (Hauptfall-Hypothese): realisierte Kosten gegen Finanzierungsanteil\n" + "-" * 70)
    for key, cfg in PRODUCTS.items():
        hyp = cfg["hauptfall"]
        if key not in results or hyp not in results[key]:
            continue
        fit = results[key][hyp]
        emit(f"\n{key} (Hypothese {hyp}):  Jahr   realisiert   Finanzierung (L-1)*Zins   Rest")
        for year, real, fund, n in yearly_table(fit["x"], fit["s"]):
            fund_s = pct(fund) if pd.notna(fund) else "   -  "
            rest = pct(real - fund) if pd.notna(fund) else pct(real)
            emit(f"    {year}   {pct(real):>9}   {fund_s:>12}   {rest:>9}   ({n} Wochen)")

    emit("\n" + "-" * 70 + "\n6) Modellparameter für den Backtest (Hauptfall)\n" + "-" * 70)
    for key, cfg in PRODUCTS.items():
        hyp = cfg["hauptfall"]
        if key not in results or hyp not in results[key]:
            continue
        fit = results[key][hyp]
        lev = cfg["leverage"]
        if lev != 1.0:
            emit(f"  {key}: Hebel {lev:g} in {hyp}, Finanzierung zu {FRED_RATES[hyp]} "
                 f"(b = {fit['b']:.2f}, bei b = 1: fixe Kosten a1 = {pct(fit['a1'])} p.a.)")
            emit(f"     Modell: Tagesrendite = {lev:g} * Basis - (a1 + ({lev:g}-1) * Zins({FRED_RATES[hyp]})) / 252")
        else:
            emit(f"  {key}: Hebel 1, fixe Kosten {pct(fit['a'])} p.a. (SPY-Basis bereits abzüglich 0,09 % SPY-TER).")
    emit(f"\nAlle ETF-Daten ab {START_FROM}; Wochen mit Datenfehlern (|ΔX| > {JUMP_K:g} x robuste Streuung, "
         f"mind. {JUMP_MIN:.0%}), die NICHT zurücklaufen, sind in 1) aufgelistet und entfernt; "
         f"zurücklaufende Ausreißer (Zeitversatz an extremen Freitagen) bleiben drin.")
    emit("\nHinweis: Die Kosten gelten relativ zu SPY (dessen TER ist schon im Kurs). Beim MSCI-USA-Produkt "
         "(18MF, SXR4) steckt die Indexlücke gegen den S&P 500 in den Kosten; sie ist keine echte Kostenkomponente "
         "und kann ihr Vorzeichen wechseln.")

    (OUTPUT_DIR / "kalibrierung_ergebnis.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if plot_data:
        n = len(plot_data)
        fig, axes = plt.subplots(n, 1, figsize=(10, 2.8 * n), sharex=False)
        axes = np.atleast_1d(axes)
        for ax, (label, x, fit) in zip(axes, plot_data):
            ax.plot(x.index, x.values * 100, linewidth=1.1, label="log(ETF / Brutto-Reihe)")
            t = years_since(x.index, fit["start"])
            model = -fit["a1"] * t - (fit["s"].to_numpy() if fit["s"] is not None else 0.0)
            ax.plot(x.index, model * 100, linestyle="--", linewidth=1.0, label="Modell (b = 1)")
            ax.set_title(label, fontsize=9)
            ax.set_ylabel("%")
            ax.grid(True, linestyle="--", alpha=0.4)
            ax.legend(fontsize=7, loc="lower left")
        fig.tight_layout()
        fig.savefig(OUTPUT_DIR / "01_verhaeltnis.png", dpi=130)
        plt.close(fig)
    print(f"\nErgebnis und Plot gespeichert in: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    try:
        run()
    except FredUnavailableError as err:
        print(f"\n[Abbruch] {err}")
        input("\nEnter zum Beenden dr\u00fccken...")
        raise SystemExit(1)
    input("\nFertig - Enter zum Beenden drücken...")
