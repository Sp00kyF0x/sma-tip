"""
TIP-Canary-Signal: Aktuelle Lage & Handlungsempfehlung
========================================================

Kein Backtest, keine Steuer-/Performance-Simulation, keine Plots/CSV-
Exporte. Das Script arbeitet in zwei Stufen:

  Stufe 1 - Signal-Assets:
    Lädt TIP (Canary) und ^NDX (Trend) über eine lange Historie
    (REGIME_HISTORY_YEARS plus Einlaufzeit), berechnet das TIP-13612U-
    Momentum und das NDX-SMA200-Trendsignal, filtert beide getrennt
    (Whipsaw) und kombiniert sie zur Hybrid-Logik (siehe unten) zum
    Regime RISK / DEFENSIVE - für JEDEN Tag der Historie.
  Stufe 2 - Risk-Assets:
    Im Regime RISK wird aus der Regime-Historie der Beginn der aktuellen
    Risk-Phase bestimmt. Erst dann werden die Kurse der Kandidaten geladen
    (ab einem Datum so weit vor dem Phasenbeginn, dass das 13612U-Momentum
    dort berechenbar ist) und der Kandidat zum PHASENBEGINN ausgewählt. Im
    Regime DEFENSIVE werden die Kandidaten nur zur Information geladen und
    ihr heutiges Momentum angezeigt (Empfehlung bleibt Tagesgeld; die
    Auswahl trifft erst der Tag, an dem RISK bestätigt wird). Scheitert
    dieser Abruf, gibt es eine [info]-Zeile, das Signal bleibt gültig.
  Danach: Signal-Historie der letzten 10 Handelstage (TIP-Signal, Abstand
  des NDX-Kurses zur SMA200, SMA-Signal, Hybrid-Regime) und ein kurzes
  Fazit mit dem aktuell bestätigten Regime, den tragenden Signalen und
  einem Hinweis, falls ein Regime-Wechsel im Aufbau ist.

Hybrid-Logik (TIP + SMA):
  Zwei Signale, jedes mit eigenem Bestätigungsfilter:
    - TIP-Canary: 13612U-Score(TIP) > 0 -> RISK (Filter a=CONFIRMATION_A,
      b=CONFIRMATION_B)
    - Trend: Schlusskurs des TREND_TICKER (^NDX) STRIKT über seinem
      TREND_SMA_DAYS-Tage-SMA (inkl. des aktuellen Schlusskurses) -> RISK,
      sonst nicht RISK (Filter a=TREND_CONFIRMATION_A, b=TREND_CONFIRMATION_B).
      Der SMA läuft auf dem eigenen Kalender des Index und wird auf den
      TIP-Kalender vorwärtsgefüllt.
  Regime = RISK, sobald MINDESTENS EINES der beiden bestätigten Signale
  RISK meldet (ODER-Verknüpfung). Nur wenn beide nicht RISK melden, gilt
  das Regime DEFENSIVE. Das gehaltene Asset ist dann ausschließlich
  Tagesgeld. Das entspricht dem Modus "hybrid" in backtest.py.

Mehrere Kandidaten für die Risk-Seite (RISK_TICKERS):
  Das Makro-Regime wird ausschließlich von den beiden Signalen bestimmt -
  die Kandidaten haben darauf keinen Einfluss. Erst INNERHALB einer
  Risk-Phase wird ausgewählt (siehe select_best_candidate()): der
  Kandidat mit dem höchsten 13612U-Momentum (reine relative Auswahl, kein
  Schwellenwert). Die Momentum-Länge wird absteigend geprüft (13612U,
  136U, 13U, 1U): Hat mindestens ein Kandidat einen Wert der jeweiligen
  Länge, gewinnt unter den Kandidaten MIT Wert der höchste; Kandidaten
  mit zu kurzer Historie nehmen am Vergleich dann nicht teil (bleiben
  aber in der Tabelle sichtbar). Hat kein Kandidat einen Wert, wird die
  nächstkürzere Länge geprüft. Geht auch 1U für keinen Kandidaten, wird
  der Kandidat mit der LÄNGSTEN verfügbaren Kurshistorie gewählt.
    Die Momentum-Tabelle sortiert die Kandidaten nach derselben Logik
  (zuerst alle mit 13612U-Wert absteigend, dann 136U, 13U, 1U; ohne Wert
  am Ende). Der gewählte Kandidat steht damit oben.
    Hinweis zum Hebel: Die Kandidaten werden ohne Hebel-Anpassung direkt
  verglichen. Der Pool sollte deshalb nur gleich gehebelte Produkte
  enthalten (aktuell nur 2x): Ein 1x-Produkt würde nach einem Crash vom
  Momentum bevorzugt und kostet dann in der Erholung Rendite. Ein Test der
  Auswahlmethoden (Risk-Tage-Momentum gegen Kalender-Momentum) zeigte bei
  gleich gehebelten Kandidaten keinen belastbaren Unterschied, daher wird
  die einfachere Kalender-Methode verwendet.

Auswahl zum Phasenbeginn (statt täglich):
  Die Kandidatenauswahl gilt für die gesamte Risk-Phase. Das Script
  bestimmt aus der Regime-Historie den ersten Tag der aktuellen
  bestätigten Risk-Phase und berechnet das Ranking so, wie es an diesem
  Tag war (nur Daten bis zu diesem Tag). Das ist dieselbe Annahme wie im
  Backtest (Wahl zu Beginn der Phase, Halten bis zum Phasenende) und
  vermeidet Umschichtungen innerhalb der Phase. Das Script braucht dafür
  keinen gespeicherten Zustand: Die Auswahl wird bei jedem Lauf aus der
  Historie neu abgeleitet. Das heutige Ranking wird zusätzlich nur zur
  Information gezeigt. Läuft die Phase schon am Beginn der Regime-
  Historie, ist der echte Beginn nicht bestimmbar; dann gilt ersatzweise
  das heutige Ranking (mit Warnung).

13612U-Momentum - Handelstage-Methode (TIP und Risk-Kandidaten):
  Score(t) = 1/4 * [ (P0/P1-1) + (P0/P3-1) + (P0/P6-1) + (P0/P12-1) ],
  wobei P1/P3/P6/P12 die Kurse 21/63/126/252 Handelstage ZUVOR in der
  EIGENEN Kurshistorie des jeweiligen Tickers sind (keine Kalenderlogik).
  136U, 13U und 1U nutzen die ersten drei, zwei bzw. eine Komponente.
  Das Momentum der Kandidaten ist unabhängig vom Regime (normale Kurse,
  auch über Tagesgeld-Phasen hinweg).

Kalender:
  Das Canary-Signal (Momentum, Rohsignal, Bestätigungsfilter) läuft
  vollständig auf dem eigenen Handelskalender von TIP (NYSE). Die Risk-
  Kandidaten laufen auf ihrem eigenen Kalender.

Whipsaw-/Bestätigungsfilter (Makro-Regime):
  Ein neuer Rohsignal-Wert wird erst nach mehreren aufeinanderfolgenden
  Handelstagen mit demselben (abweichenden) Wert als "bestätigt"
  übernommen - mit zwei getrennten Fenstern je Richtung:
    CONFIRMATION_A = 1  - Handelstage, die nötig sind für einen Wechsel
                          WEG von RISK (zu DEFENSIVE)
    CONFIRMATION_B = 2  - Handelstage, die nötig sind für einen Wechsel
                          HIN ZU RISK
  Für das Trend-Signal gelten die eigenen Fenster TREND_CONFIRMATION_A /
  TREND_CONFIRMATION_B (1 / 2). Die Signal-Tabelle zeigt das bestätigte
  Signal beider Zweige sowie das daraus kombinierte Regime je Tag.
  Zusätzlich wird ausgegeben, falls sich ein Regimewechsel im Aufbau
  befindet (z.B. "seit 1 Tag abweichend, noch 1 weitere Bestätigung
  nötig"). Ein im Aufbau befindlicher Signalwechsel, der das Hybrid-Regime
  nicht ändern würde (das andere Signal hält RISK), löst keinen Regime-
  Hinweis aus, wird aber im Fazit beim jeweiligen Signal vermerkt.

Timing:
  Das mit dem HEUTIGEN Schlusskurs bestätigte Regime ist die
  Handlungsgrundlage für die Order am heutigen Abend: das Script wird
  nach Börsenschluss ausgeführt, der heutige Schlusskurs ist dann bekannt
  (siehe "Sicherer Auswertungszeitpunkt").

Umfang der abgefragten Kursdaten:
    - Stufe 1 (TIP, ^NDX): REGIME_HISTORY_YEARS Jahre Regime-Historie
      PLUS die Einlaufzeit für die Signale (252 Handelstage für das
      13612U, 200 für den SMA200) und DISPLAY_LAST_N_DAYS=10 Handelstage
      für die Signal-Historie, großzügig (CALENDAR_DAYS_PER_TRADING_DAY)
      in Kalendertage umgerechnet. Es ist je Ticker nur ein Abruf, die
      Datenmenge ist klein.
    - Stufe 2 (Risk-Kandidaten, nur im Regime RISK): ab dem Auswahltag
      minus der Einlaufzeit für das 13612U (252 Handelstage, großzügig in
      Kalendertage umgerechnet).
  Als Enddatum der Abfrage gilt (siehe compute_query_end_date()):
    - HEUTE (Kalendertag in New Yorker Zeit), falls
      SAFE_EVALUATION_TIME_NY bereits erreicht ist,
    - sonst der letzte Handelstag VOR heute (i.d.R. der Vortag).

Sicherer Auswertungszeitpunkt (yfinance liefert am selben Tag VOR
Börsenschluss einen unfertigen Intraday-Stand statt des Schlusskurses):
  Der reguläre Handelsschluss von NYSE/Nasdaq (TIP) liegt bei 16:00 Uhr
  New Yorker Zeit (meist 22:00 Uhr deutscher Zeit, in den Wochen mit
  abweichender Sommerzeit-Umstellung 21:00 Uhr). Maßgeblich ist die New
  Yorker Zeit: SAFE_EVALUATION_TIME_NY = 16:05 Uhr ist ein Sicherheits-
  puffer. Wird das Script davor ausgeführt, wird als Abfrage-Enddatum
  der letzte VOLLSTÄNDIGE Handelstag verwendet (siehe
  compute_query_end_date()). Zusätzlich verwirft load_prices() eine ggf.
  dennoch gelieferte unfertige heutige Kurszeile. Die Regel gilt
  einheitlich für ALLE Ticker, auch für Xetra-ETFs mit früherem
  Handelsschluss - das ist für diese unnötig konservativ (ihre heutige
  Zeile wird erst am Folgeabend berücksichtigt), aber harmlos und hält
  die Logik einheitlich.

Währung:
  Es werden ausschließlich EUR-notierte Risk-Ticker konfiguriert, eine
  Währungsumrechnung ist daher nicht nötig. Für das Canary-Asset TIP
  (USD) ist die Währung irrelevant, da nur das Kursverhältnis P0/Pn in
  die Momentum-Formel eingeht. Gleiches gilt für den Trend-Index ^NDX
  (USD): nur das Verhältnis Kurs/SMA zählt.

Hinweis: Bitte prüfen, dass die Kurshistorien der konfigurierten Ticker
das abbilden, was Tickername/ISIN vermuten lassen.

Abhängigkeiten:
    pip install -r requirements.txt
"""

from __future__ import annotations

import sys
from datetime import datetime

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    print(f"Fehler: Benötigtes Paket nicht gefunden ({exc.name}).\n"
          f"Bitte einmalig ausführen: pip install -r requirements.txt")
    raise SystemExit(1) from None

from yf_data import (
    BERLIN_TZ,
    NEW_YORK_TZ,
    SAFE_EVALUATION_TIME_NY,
    compute_query_end_date,
    load_prices,
)

# ----------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------
# Ticker -> Anzeigename. Der Ticker (Dictionary-Key) wird für die
# yf-Abfrage verwendet, der Anzeigename ausschließlich für die Ausgabe.
CANARY = {
    "TIP": "TIP",                # iShares TIPS Bond ETF als Canary-Asset
}
CANARY_TICKER = next(iter(CANARY))

# Trend-Index für das SMA-Signal der Hybrid-Logik.
TREND = {
    "^NDX": "Nasdaq 100",        # Trend-Signalquelle (Kurs gegen SMA)
}
TREND_TICKER = next(iter(TREND))

RISK_TICKERS = {
    "DBPG.DE": "Xtrackers S&P 500 (2x)",
    "18MF.DE": "Amundi MSCI USA (2x)",
    "LVWC.DE": "Amundi MSCI World (2x)",
    "SC2X.DE": "Scalable MSCI ACWI (2x)",
}

# Zustände des Regimes. Im Regime DEFENSIVE wird ausschließlich Tagesgeld gehalten.
RISK = "RISK"
DEFENSIVE = "DEFENSIVE"

# Ticker -> Anzeigename über alle konfigurierten Ticker (nur Ausgabe).
ALL_TICKER_NAMES: dict[str, str] = {CANARY_TICKER: CANARY[CANARY_TICKER],
                                    TREND_TICKER: TREND[TREND_TICKER],
                                    **RISK_TICKERS}

# Lookbacks (Handelstage) für den 13612U-Score von TIP und den Risk-
# Kandidaten. 136U/13U/1U nutzen die ersten drei/zwei/eine Komponente.
LOOKBACK_DAYS = (21, 63, 126, 252)

# Whipsaw-/Bestätigungsfenster (Handelstage) des TIP-Canary-Makrosignals,
# getrennt je Wechselrichtung (siehe Modul-Docstring).
CONFIRMATION_A = 1  # weg von RISK (-> DEFENSIVE)
CONFIRMATION_B = 2  # hin zu RISK

# Trend-Signal (SMA) der Hybrid-Logik: SMA-Länge in Handelstagen und
# eigene Bestätigungsfenster (gleiche Bedeutung wie oben).
TREND_SMA_DAYS = 200
TREND_CONFIRMATION_A = 1  # weg von RISK
TREND_CONFIRMATION_B = 2  # hin zu RISK

# Anzahl der zuletzt angezeigten Tage in der Signal-Historie.
DISPLAY_LAST_N_DAYS = 10

# Stufe 1: Einlaufzeit der Signale (252 Handelstage 13612U bzw. SMA-Länge,
# falls größer) + DISPLAY_LAST_N_DAYS, großzügig (Faktor 1.6 + Puffer) in
# Kalendertage umgerechnet, um Wochenenden/Feiertage abzudecken.
TRADING_DAYS_NEEDED = max(LOOKBACK_DAYS[-1], TREND_SMA_DAYS) + DISPLAY_LAST_N_DAYS  # 262
CALENDAR_DAYS_PER_TRADING_DAY = 1.6
WARMUP_CALENDAR_DAYS = int(TRADING_DAYS_NEEDED * CALENDAR_DAYS_PER_TRADING_DAY) + 30

# Länge der Regime-Historie NACH der Einlaufzeit in Jahren. Sie muss den
# Beginn der aktuellen Risk-Phase enthalten.
REGIME_HISTORY_YEARS = 10
REGIME_HISTORY_CALENDAR_DAYS = WARMUP_CALENDAR_DAYS + int(REGIME_HISTORY_YEARS * 365.25)

# Stufe 2: Die Kandidaten werden ab dem Auswahltag minus dieser Einlaufzeit
# geladen (252 Handelstage für das 13612U plus Puffer, in Kalendertage).
CANDIDATE_WARMUP_CALENDAR_DAYS = int((LOOKBACK_DAYS[-1] + 1) * CALENDAR_DAYS_PER_TRADING_DAY) + 30

# Maximale Breite der Namensspalte in der Momentum-Tabelle; längere Namen
# werden mit "…" gekürzt.
MOM_TABLE_NAME_COL_MAX = 34


# ----------------------------------------------------------------------
# Kursdaten je Ticker laden
# ----------------------------------------------------------------------
def load_ticker(ticker: str, start_date: pd.Timestamp, query_end_date: pd.Timestamp) -> dict:
    """Lädt die Kurshistorie eines Tickers von `start_date` bis
    `query_end_date` über yf_data.load_prices() (inkl. Konsens-Abfrage,
    Vollständigkeitsprüfung gegen den Börsenkalender und Verwerfen eines
    unfertigen heutigen Kurses)."""
    safe, dropped = load_prices(ticker, start_date, query_end_date)
    return {"ticker": ticker, "prices": safe, "dropped_today": dropped}


# ----------------------------------------------------------------------
# Momentum-Berechnung
# ----------------------------------------------------------------------
def momentum_13612u(adj_close: pd.Series, lookback_days: tuple[int, ...] = LOOKBACK_DAYS) -> pd.Series:
    """13612U-Score in Handelstagen (Series.shift(n)) für jeden Tag der Reihe."""
    components = [adj_close / adj_close.shift(n) - 1.0 for n in lookback_days]
    return sum(components) / len(components)


def candidate_momenta(prices: pd.Series, asof: pd.Timestamp) -> dict:
    """Momentum-Kennzahlen eines Kandidaten zum Tag `asof` (Handelstage-
    Methode wie momentum_13612u(), nur Kurse bis einschließlich `asof`).
    Rückgabe: {"1u", "13u", "136u", "13612u": Wert oder NaN, "n": Anzahl
    Renditen}. Eine Komponente (21/63/126/252 Handelstage) ist NaN, wenn
    die Historie dafür nicht reicht; eine Kennzahl ist NaN, sobald eine
    ihrer Komponenten fehlt."""
    p = prices.loc[:asof].dropna().to_numpy()
    n = len(p) - 1
    comps = [float(p[-1] / p[-1 - k] - 1.0) if n >= k else float("nan") for k in LOOKBACK_DAYS]
    out: dict = {"n": n}
    for key, m in (("1u", 1), ("13u", 2), ("136u", 3), ("13612u", 4)):
        vals = comps[:m]
        out[key] = float("nan") if any(np.isnan(v) for v in vals) else float(np.mean(vals))
    return out


# ----------------------------------------------------------------------
# Whipsaw-/Bestätigungsfilter (Makro-Regime)
# ----------------------------------------------------------------------
def raw_target_position(canary_mom: pd.Series) -> pd.Series:
    """Tägliches Rohsignal (ohne Bestätigungsfilter):
      Score(Canary) > 0   -> "RISK"
      sonst               -> "DEFENSIVE"
    (NaN > 0 ist False, d.h. Tage ohne Score gelten als DEFENSIVE; sie
    werden vor der Verwendung ohnehin abgeschnitten.)"""
    return pd.Series(np.where(canary_mom > 0, RISK, DEFENSIVE),
                     index=canary_mom.index, dtype=object)


def apply_confirmation_filter(raw_position: pd.Series, a: int, b: int) -> tuple[pd.Series, str | None, int]:
    """
    Whipsaw-Filter mit zwei getrennten Bestätigungsfenstern je
    Wechselrichtung (siehe Modul-Docstring): ein neuer Zustand wird erst
    übernommen, wenn das rohe Tagessignal mehrere aufeinanderfolgende
    Handelstage denselben neuen Wert `s` zeigt - wie viele, hängt vom
    ZIEL-Wert ab:
      s == "RISK"  -> `b` Handelstage nötig (Wechsel HIN ZU Risk)
      s != "RISK"  -> `a` Handelstage nötig (Wechsel WEG von Risk)
    a=1 bzw. b=1 bedeutet: dieser Wechsel wird sofort übernommen.

    Gibt zusätzlich zur bestätigten Zeitreihe den Bestätigungsstatus
    NACH DEM LETZTEN TAG zurück: (Kandidat, Anzahl bereits
    aufeinanderfolgend bestätigter Tage). candidate=None bedeutet: das
    Rohsignal stimmt am letzten Tag mit dem bestätigten Regime überein,
    kein Wechsel im Aufbau.
    """
    if raw_position.empty:
        return raw_position.copy(), None, 0

    values = raw_position.to_numpy()
    confirmed = np.empty(len(values), dtype=object)

    held = values[0]
    candidate = None
    candidate_count = 0
    confirmed[0] = held

    for i in range(1, len(values)):
        s = values[i]
        if s == held:
            candidate = None
            candidate_count = 0
        else:
            if s == candidate:
                candidate_count += 1
            else:
                candidate = s
                candidate_count = 1
            required = b if s == RISK else a
            if candidate_count >= required:
                held = s
                candidate = None
                candidate_count = 0
        confirmed[i] = held

    return pd.Series(confirmed, index=raw_position.index), candidate, candidate_count


# ----------------------------------------------------------------------
# Trend-Signal (SMA) und Hybrid-Verknüpfung
# ----------------------------------------------------------------------
def trend_raw_position(trend_prices: pd.Series, sma_days: int) -> tuple[pd.Series, pd.Series]:
    """Tägliches Rohsignal des Trend-Index (ohne Bestätigungsfilter) auf
    dessen EIGENEM Kalender: Schlusskurs STRIKT über dem `sma_days`-Tage-
    SMA (inkl. des aktuellen Schlusskurses) -> "RISK", sonst "DEFENSIVE"
    (Gleichstand: nicht RISK, wie beim TIP-Score = 0). Tage ohne SMA-Wert
    entfallen. Rückgabe: (Rohsignal, SMA-Serie auf dem vollen Kalender)."""
    sma = trend_prices.rolling(sma_days).mean()
    raw = pd.Series(np.where(trend_prices > sma, RISK, DEFENSIVE),
                    index=trend_prices.index, dtype=object)[sma.notna()]
    return raw, sma


def combine_state(tip_state: str, trend_state: str) -> str:
    """Hybrid-Verknüpfung für einen einzelnen Zustand: "RISK", sobald
    mindestens eines der beiden Signale "RISK" meldet; sonst "DEFENSIVE"."""
    return RISK if RISK in (tip_state, trend_state) else DEFENSIVE


def combine_regime(tip_state: pd.Series, trend_state: pd.Series) -> pd.Series:
    """Wie combine_state(), für zwei Zeitreihen gleichen Index."""
    risk = (tip_state == RISK) | (trend_state == RISK)
    return tip_state.mask(risk, RISK)


def regime_change_scenarios(today_regime: str, tip_state: str, trend_state: str,
                            tip_pending: tuple[str, int, int] | None,
                            trend_pending: tuple[str, int, int] | None) -> list[dict]:
    """Welche im Aufbau befindlichen Signalwechsel würden das Hybrid-Regime
    ändern? `*_pending` = (Kandidat, bereits bestätigte Tage, nötige Tage)
    oder None. Geprüft werden jedes pending-Signal allein und - falls beide
    pending sind - beide zusammen; Kombinationen, die nur wegen einer
    bereits wirksamen Teilmenge wirken, werden nicht doppelt gemeldet.
    Rückgabe je Szenario: {"signals", "new", "remaining"} (remaining = Tage,
    bis alle beteiligten Signale bestätigt sind)."""
    pending = {k: v for k, v in (("TIP", tip_pending), ("SMA", trend_pending)) if v is not None}
    names = list(pending)
    subsets = [(n,) for n in names] + ([tuple(names)] if len(names) == 2 else [])
    scenarios: list[dict] = []
    for sub in subsets:
        t = pending["TIP"][0] if "TIP" in sub else tip_state
        s = pending["SMA"][0] if "SMA" in sub else trend_state
        new = combine_state(t, s)
        if new == today_regime:
            continue
        if any(set(prev["signals"]) < set(sub) for prev in scenarios):
            continue
        remaining = max(pending[n][2] - pending[n][1] for n in sub)
        scenarios.append({"signals": sub, "new": new, "remaining": remaining})
    return scenarios


# ----------------------------------------------------------------------
# Auswahl des besten Risk-Kandidaten (für einen Bewertungstag)
# ----------------------------------------------------------------------
# Momentum-Längen in der Reihenfolge, in der sie für die Kandidatenauswahl
# geprüft werden: (Schlüssel in candidate_momenta(), Klartext).
SELECTION_METHODS = (("13612u", "13612U"), ("136u", "136U"), ("13u", "13U"), ("1u", "1U"))


def select_best_candidate(tickers: list[str],
                           price_data: dict[str, dict],
                           moms: dict[str, dict],
                           date: pd.Timestamp) -> tuple[str, float | None, str]:
    """Wählt den Kandidaten aus `tickers` mit dem höchsten Momentum
    (reine relative Auswahl, kein Schwellenwert). Die Momentum-Länge wird
    absteigend geprüft (SELECTION_METHODS: 13612U, 136U, 13U, 1U): Hat
    mindestens ein Kandidat einen Wert der jeweiligen Länge, gewinnt unter
    den Kandidaten MIT Wert der höchste (Kandidaten ohne Wert, d.h. zu
    kurze Kurshistorie, scheiden aus dem Vergleich aus); sonst wird die
    nächstkürzere Länge geprüft. Hat auch für 1U kein Kandidat einen Wert,
    wird der Kandidat mit der längsten verfügbaren Kurshistorie (Stand
    `date`) gewählt. `moms` = Ticker -> Ausgabe von candidate_momenta() für
    den Bewertungstag; `price_data` wird nur für den Historienlängen-
    Fallback gebraucht. Rückgabe: (Ticker, Score oder None, verwendete
    Methode als Klartext)."""
    for key, label in SELECTION_METHODS:
        scores = {t: moms[t][key] for t in tickers if pd.notna(moms[t][key])}
        if scores:
            best = max(scores, key=scores.get)
            return best, scores[best], label

    hist_len = {t: price_data[t]["prices"].loc[:date].dropna().shape[0] for t in tickers}
    best = max(hist_len, key=hist_len.get)
    return best, None, "längste Historie"


def sort_candidates(tickers: list[str], moms: dict[str, dict]) -> list[str]:
    """Sortiert `tickers` für die Momentum-Tabelle: nach der längsten
    Momentum-Länge (SELECTION_METHODS), für die der Kandidat einen Wert
    hat - Kandidaten mit 13612U-Wert zuerst, dann die mit 136U-Wert usw. -
    und innerhalb derselben Länge absteigend nach diesem Wert. Kandidaten
    ohne jeden Wert stehen am Ende (Reihenfolge der Konfiguration bleibt
    erhalten, da sorted() stabil ist)."""
    def key(t: str) -> tuple[int, float]:
        for rank, (mkey, _) in enumerate(SELECTION_METHODS):
            if pd.notna(moms[t][mkey]):
                return rank, -float(moms[t][mkey])
        return len(SELECTION_METHODS), 0.0
    return sorted(tickers, key=key)


# ----------------------------------------------------------------------
# Hilfsfunktionen für main()
# ----------------------------------------------------------------------
def _mom_table_name(name: str, name_col: int) -> str:
    if len(name) > name_col:
        return name[: name_col - 1] + "…"
    return name


def _fmt_mom(value: float) -> str:
    """Momentum als Prozentwert, "-" falls nicht berechenbar (zu kurze Historie)."""
    return "-" if pd.isna(value) else f"{value:.2%}"


def print_momentum_table(title: str,
                         tickers: dict[str, str],
                         moms: dict[str, dict],
                         markers: dict[str, str]) -> None:
    """Gibt die Momentum-Übersicht (1U/13U/136U/13612U) der Kandidaten aus. `markers`: Ticker -> Text hinter der Zeile (z.B. "gewählt").
    Die Zeilen sind nach sort_candidates() sortiert (längste verfügbare
    Momentum-Länge zuerst, darin absteigend nach Wert). Feste
    Spaltenbreiten, damit die Tabelle bei unterschiedlich langen Namen
    nicht verrutscht; die Namensspalte richtet sich nach dem längsten
    Namen, höchstens aber MOM_TABLE_NAME_COL_MAX."""
    print(f"\n{title}:")
    ticker_col = max(10, max(len(t) for t in tickers) + 1)
    name_col = min(MOM_TABLE_NAME_COL_MAX, max(len(n) for n in tickers.values()))
    header = (f"  {'Ticker':<{ticker_col}}{'Name':<{name_col}}  "
              f"{'1U':>8}{'13U':>8}{'136U':>8}{'13612U':>8}")
    print(header)
    print("-" * len(header))
    for t in sort_candidates(list(tickers), moms):
        m = moms[t]
        marker = f" <- {markers[t]}" if t in markers else ""
        print(f"  {t:<{ticker_col}}"
              f"{_mom_table_name(tickers[t], name_col):<{name_col}}  "
              f"{_fmt_mom(m['1u']):>8}{_fmt_mom(m['13u']):>8}{_fmt_mom(m['136u']):>8}"
              f"{_fmt_mom(m['13612u']):>8}{marker}")


def current_phase_start(confirmed_position: pd.Series) -> tuple[pd.Timestamp, bool]:
    """Erster Tag der aktuellen, mit dem letzten Schlusskurs bestätigten
    RISK-Phase (der Tag, an dem der Wechsel zu RISK bestätigt wurde; das
    Signal-Regime des Tages ist die Handlungsgrundlage der Abend-Order).
    Zweiter Rückgabewert: True, falls die Phase schon am Beginn der
    Regime-Historie läuft (der echte Beginn liegt dann davor)."""
    not_risk = confirmed_position != RISK
    if not not_risk.any():
        return confirmed_position.index[0], True
    last_not_risk = not_risk[not_risk].index[-1]
    pos = confirmed_position.index.get_loc(last_not_risk)
    return confirmed_position.index[pos + 1], False


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    now_berlin = datetime.now(BERLIN_TZ)
    now_ny = now_berlin.astimezone(NEW_YORK_TZ)
    cutoff_str = SAFE_EVALUATION_TIME_NY.strftime("%H:%M")
    print(f"Aktuelle Zeit: {now_berlin.strftime('%Y-%m-%d %H:%M:%S')} (Berlin) / "
          f"{now_ny.strftime('%H:%M')} (New York)")

    query_end_date = compute_query_end_date(now_berlin)
    if now_ny.time() < SAFE_EVALUATION_TIME_NY:
        print(f"[warn] Es ist noch vor {cutoff_str} Uhr New Yorker Zeit - es werden nur "
              f"Kurse bis {query_end_date.date()} (letzter vollständiger Handelstag) "
              f"abgefragt.")
    else:
        print(f"[info] Nach {cutoff_str} Uhr New Yorker Zeit - es werden Kurse bis "
              f"heute ({query_end_date.date()}) abgefragt, falls bereits verfügbar.")
    print()

    # ==================================================================
    # Stufe 1: Signal-Assets (TIP, ^NDX) -> Regime-Historie
    # ==================================================================
    regime_start = query_end_date - pd.Timedelta(days=REGIME_HISTORY_CALENDAR_DAYS)
    canary = load_ticker(CANARY_TICKER, regime_start, query_end_date)
    trend = load_ticker(TREND_TICKER, regime_start, query_end_date)

    for t, d in {CANARY_TICKER: canary, TREND_TICKER: trend}.items():
        if d["dropped_today"]:
            print(f"[info] {ALL_TICKER_NAMES[t]}: heutiger (unfertiger) Kurs verworfen, "
                  f"letzter berücksichtigter Handelstag: {d['prices'].index[-1].date()}")
    print()

    master_calendar = canary["prices"].index
    canary_mom = momentum_13612u(canary["prices"])

    # Trend-Signal (SMA): Rohsignal und Bestätigungsfilter auf dem eigenen
    # Kalender des Index, danach vorwärtsgefüllt auf den TIP-Kalender.
    trend_raw_native, trend_sma_native = trend_raw_position(trend["prices"], TREND_SMA_DAYS)
    if trend_raw_native.empty:
        raise ValueError(f"Zu wenig Historie für den SMA{TREND_SMA_DAYS} von {TREND_TICKER} - "
                          f"ggf. REGIME_HISTORY_YEARS erhöhen.")
    trend_conf_native, trend_pending_candidate, trend_pending_count = apply_confirmation_filter(
        trend_raw_native, TREND_CONFIRMATION_A, TREND_CONFIRMATION_B)
    trend_raw = trend_raw_native.reindex(master_calendar, method="ffill")
    trend_conf = trend_conf_native.reindex(master_calendar, method="ffill")
    trend_gap = (trend["prices"] / trend_sma_native - 1.0).reindex(master_calendar, method="ffill")

    valid_mask = canary_mom.notna() & trend_conf.notna()
    if not valid_mask.any():
        raise ValueError("Zu wenig gemeinsame Historie für die gewählten Lookbacks - "
                          "ggf. REGIME_HISTORY_YEARS erhöhen.")
    first_valid_date = master_calendar[valid_mask][0]

    canary_mom = canary_mom.loc[canary_mom.index >= first_valid_date]
    trend_raw = trend_raw.loc[trend_raw.index >= first_valid_date]
    trend_conf = trend_conf.loc[trend_conf.index >= first_valid_date]
    trend_gap = trend_gap.loc[trend_gap.index >= first_valid_date]

    # --- Rohsignal + Bestätigungsfilter (TIP), Hybrid-Verknüpfung mit SMA ---
    raw_position = raw_target_position(canary_mom)
    tip_confirmed, pending_candidate, pending_count = apply_confirmation_filter(
        raw_position, CONFIRMATION_A, CONFIRMATION_B)
    confirmed_position = combine_regime(tip_confirmed, trend_conf)

    today = confirmed_position.index[-1]
    today_regime = confirmed_position.iloc[-1]
    tip_state = tip_confirmed.iloc[-1]
    trend_state = trend_conf.iloc[-1]

    # ==================================================================
    # Stufe 2: Risk-Kandidaten (im Regime RISK Auswahl, sonst nur Information)
    # ==================================================================
    chosen = None            # (Ticker, Score, Methode)
    phase_start = None
    phase_from_history_start = False
    moms_today: dict[str, dict] = {}
    if today_regime == RISK:
        phase_start, phase_from_history_start = current_phase_start(confirmed_position)
        # Normalfall: Auswahl zum Phasenbeginn. Läuft die Phase schon am Beginn der
        # Regime-Historie, ist der echte Beginn nicht bestimmbar - dann gilt
        # ersatzweise das heutige Ranking.
        selection_date = today if phase_from_history_start else phase_start
        candidates_start = selection_date - pd.Timedelta(days=CANDIDATE_WARMUP_CALENDAR_DAYS)
        print(f"[info] Risk-Phase seit {phase_start.date()}: Risk-Kandidaten werden ab "
              f"{candidates_start.date()} geladen (Auswahltag {selection_date.date()}).")
        if phase_from_history_start:
            print(f"[warn] Die Risk-Phase läuft schon am Beginn der Regime-Historie "
                  f"({phase_start.date()}); der echte Phasenbeginn liegt davor. Ersatzweise "
                  f"gilt das heutige Ranking. REGIME_HISTORY_YEARS erhöhen.")
        risk_data = {t: load_ticker(t, candidates_start, query_end_date) for t in RISK_TICKERS}
        for t, d in risk_data.items():
            if d["dropped_today"]:
                print(f"[info] {ALL_TICKER_NAMES[t]}: heutiger Kurs verworfen "
                      f"(Sicherheitsregel, siehe Docstring), letzter berücksichtigter "
                      f"Handelstag: {d['prices'].index[-1].date()}")
        print()

        moms_today = {t: candidate_momenta(d["prices"], today) for t, d in risk_data.items()}
        moms_at_selection = (moms_today if selection_date == today else
                             {t: candidate_momenta(d["prices"], selection_date)
                              for t, d in risk_data.items()})
        chosen = select_best_candidate(list(RISK_TICKERS), risk_data, moms_at_selection, selection_date)
        top_today = select_best_candidate(list(RISK_TICKERS), risk_data, moms_today, today)
    else:
        # Nur Information: heutiges Momentum der Kandidaten. Ein Fehler hier darf das Signal nicht verhindern.
        candidates_start = today - pd.Timedelta(days=CANDIDATE_WARMUP_CALENDAR_DAYS)
        try:
            risk_data = {t: load_ticker(t, candidates_start, query_end_date) for t in RISK_TICKERS}
            for t, d in risk_data.items():
                if d["dropped_today"]:
                    print(f"[info] {ALL_TICKER_NAMES[t]}: heutiger Kurs verworfen "
                          f"(Sicherheitsregel, siehe Docstring), letzter berücksichtigter "
                          f"Handelstag: {d['prices'].index[-1].date()}")
            moms_today = {t: candidate_momenta(d["prices"], today) for t, d in risk_data.items()}
            top_today = select_best_candidate(list(RISK_TICKERS), risk_data, moms_today, today)
        except Exception as exc:                                   # noqa: BLE001
            # [info] statt [warn]: reine Information, soll keine Warnung in der Push-Nachricht auslösen
            print(f"[info] Momentum der Risk-Kandidaten nicht verfügbar ({exc}); "
                  f"das Signal ist davon nicht betroffen.")
            moms_today = {}
        print()

    if trend["prices"].index[-1] != today:
        print(f"[warn] Letzter Kurs von {ALL_TICKER_NAMES[TREND_TICKER]} ist "
              f"{trend['prices'].index[-1].date()} (TIP: {today.date()}) - SMA-Signal "
              f"stammt vom letzten verfügbaren Handelstag.\n")

    # --- Signal-Historie der letzten N Tage ---
    n = min(DISPLAY_LAST_N_DAYS, len(confirmed_position))
    sma_col = f"NDX-SMA{TREND_SMA_DAYS}"
    print(f"Signal-Historie der letzten {n} Handelstage:")
    header = (f"{'Datum':<10} | {'TIP-Momentum':^19} | {sma_col:^21} | {'Regime':<9}")
    print(header)
    print("".join("+" if ch == "|" else "-" for ch in header))
    for date in confirmed_position.index[-n:]:
        print(f"{date.date()!s:<10} | {canary_mom.loc[date]:>8.2%}  "
              f"{tip_confirmed.loc[date]:<9} | "
              f"{trend_gap.loc[date]:>+10.2%}  {trend_conf.loc[date]:<9} | "
              f"{confirmed_position.loc[date]:<9}")

    print(f"\nAktuell bestätigtes Regime (Stand Schlusskurs {today.date()}): {today_regime}")

    # --- Gehaltenes Asset, heutiger Spitzenreiter und Momentum-Übersicht ---
    if today_regime == RISK:
        ticker, _, method = chosen
        leader = top_today[0]
        print(f"Gehalten (Wahl zum Phasenbeginn): {ticker} | {ALL_TICKER_NAMES[ticker]}")
        print(f"Heute vorn: {leader} | {ALL_TICKER_NAMES[leader]}")
        n_phase_days = int(((confirmed_position.index >= phase_start)).sum())
        since = f"seit {phase_start.date()} ({n_phase_days} Handelstag(e))"
        if phase_from_history_start:
            since = f"mindestens {since}"
        print(f"Risk-Phase {since}. Die Auswahl wird zum Phasenbeginn getroffen und bis zum "
              f"Phasenende gehalten (Methode: {method}).")
        markers = {ticker: "gehalten (Wahl zum Phasenbeginn)"}
        markers[leader] = ("gehalten (Wahl zum Phasenbeginn) und heute vorne" if leader == ticker else "heute vorne")
        title = f"Momentum der Risk-Kandidaten heute ({today.date()})"
        if phase_from_history_start:
            title += " (Phasenbeginn nicht bestimmbar, ersatzweise Grundlage der Auswahl)"
        print_momentum_table(title, RISK_TICKERS, moms_today, markers)
        if leader != ticker:
            print(f"\nHinweis: Der heutige Spitzenreiter ({leader}) ist nur eine Information. "
                  f"Gehalten wird {ticker}: Die Auswahl zum Phasenbeginn gilt bis zum Ende "
                  f"der Risk-Phase.")
    else:
        print("Empfehlung: Tagesgeld")
        if moms_today:
            leader = top_today[0]
            # bewusst nicht "Heute vorn:" (diese Zeile wertet ntfy_push.py nur im Regime RISK aus)
            print(f"Momentum-Spitzenreiter heute (nur Information): {leader} | {ALL_TICKER_NAMES[leader]}")
            print_momentum_table(f"Momentum der Risk-Kandidaten heute ({today.date()}, nur Information)",
                                 RISK_TICKERS, moms_today, {leader: "heute vorne"})
            print("\nHinweis: Im Regime DEFENSIVE wird nichts gekauft. Wechselt das Regime zu RISK, wird der "
                  "Kandidat am Tag des bestätigten Wechsels ausgewählt - das Ranking kann sich bis dahin ändern.")

    # --- Hinweis auf im Aufbau befindlichen Regimewechsel ---
    tip_pending = None
    if pending_candidate is not None:
        tip_pending = (pending_candidate, pending_count,
                       CONFIRMATION_B if pending_candidate == RISK else CONFIRMATION_A)
    trend_pending = None
    if trend_pending_candidate is not None:
        trend_pending = (trend_pending_candidate, trend_pending_count,
                         TREND_CONFIRMATION_B if trend_pending_candidate == RISK
                         else TREND_CONFIRMATION_A)
    scenarios = regime_change_scenarios(today_regime, tip_state, trend_state,
                                        tip_pending, trend_pending)

    for sc in scenarios:
        parts = []
        if "TIP" in sc["signals"]:
            parts.append(f"das TIP-Rohsignal zeigt seit {tip_pending[1]} Handelstag(en) in "
                         f"Folge '{tip_pending[0]}' (bestätigt: '{tip_state}')")
        if "SMA" in sc["signals"]:
            parts.append(f"das {TREND[TREND_TICKER]}-SMA-Signal zeigt seit {trend_pending[1]} "
                         f"Handelstag(en) in Folge '{trend_pending[0]}' (bestätigt: '{trend_state}')")
        text = " und ".join(parts)
        print(f"\n[Hinweis] {text[0].upper() + text[1:]}. Bei {sc['remaining']} weiterer/n "
              f"Bestätigung(en) in Folge würde das Hybrid-Regime von '{today_regime}' zu "
              f"'{sc['new']}' wechseln - ggf. lohnt sich morgen ein erneuter Lauf dieses "
              f"Skripts, bevor du handelst.")

    # --- Fazit ---
    print("\n" + "=" * 60)
    print("FAZIT")
    print("=" * 60)
    print(f"Regime: {today_regime}   (Hybrid: RISK, sobald mindestens ein Signal RISK meldet)")

    def signal_line(label: str, state: str, detail: str,
                    pending: tuple[str, int, int] | None) -> str:
        line = f"  {label:<14}{state:<10}{detail}"
        if pending is not None:
            line += (f"  [Wechsel zu '{pending[0]}' im Aufbau: {pending[1]} von "
                     f"{pending[2]} Bestätigung(en)]")
        return line

    print(signal_line("TIP-Canary:", tip_state,
                      f"(13612U {canary_mom.loc[today]:+.2%})", tip_pending))
    gap = trend_gap.loc[today]
    print(signal_line(f"NDX-SMA{TREND_SMA_DAYS}:", trend_state,
                      f"(Kurs {abs(gap):.2%} {'über' if gap > 0 else 'unter'} SMA)", trend_pending))

    tip_risk, trend_risk = tip_state == RISK, trend_state == RISK
    if tip_risk and trend_risk:
        print("\nBeide Signale melden RISK. Das Regime wechselt erst, wenn beide "
              "nicht mehr RISK melden.")
    elif tip_risk:
        print(f"\nNur das TIP-Signal trägt RISK (der NDX liegt unter seinem SMA{TREND_SMA_DAYS}). "
              f"Kippt das TIP-Signal ({CONFIRMATION_A} Bestätigungstag(e)), wechselt das "
              f"Regime zu DEFENSIVE, solange der NDX nicht über die SMA zurückkehrt.")
    elif trend_risk:
        print(f"\nNur das SMA-Signal trägt RISK (das TIP-Signal ist nicht RISK). Fällt der NDX "
              f"unter seine SMA{TREND_SMA_DAYS} ({TREND_CONFIRMATION_A} Bestätigungstag(e)), "
              f"wechselt das Regime zu DEFENSIVE, solange das TIP-Signal nicht RISK meldet.")
    else:
        print(f"\nBeide Signale melden nicht RISK. Zurück zu RISK, sobald eines davon bestätigt "
              f"RISK meldet (TIP {CONFIRMATION_B} Tag(e), SMA {TREND_CONFIRMATION_B} Tag(e)).")

    if scenarios:
        print("\n[Beachte den Hinweis oben zum im Aufbau befindlichen Regimewechsel.]")


if __name__ == "__main__":
    main()
    if sys.stdin.isatty():  # nur bei interaktivem Start (nicht in der Cloud/Pipe) warten
        input("\nFertig - Enter zum Beenden drücken...")
