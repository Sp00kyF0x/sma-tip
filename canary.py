"""
TIP-Canary-Signal: Aktuelle Lage & Handlungsempfehlung
========================================================

Kein Backtest, keine Steuer-/Performance-Simulation, keine Plots/CSV-
Exporte. Das Script:

  1. Lädt die aktuellen Kursdaten für das Canary-Asset (TIP) sowie
     beliebig viele Risk- und Defensiv-Kandidaten-Ticker - beschränkt
     auf das tatsächlich benötigte Zeitfenster (siehe "Umfang der
     abgefragten Kursdaten"). Der Abruf inkl. Konsens-Abfrage,
     Kalender-Vollständigkeitsprüfung und Kurssprung-Korrektur läuft
     über yf_data.py (siehe dortiger Docstring).
  2. Berechnet das TIP-13612U-Momentum (Handelstage-Methode) und das
     NDX-SMA200-Trendsignal, filtert beide getrennt (Whipsaw) und
     kombiniert sie zur Hybrid-Logik (siehe unten) zum Regime
     RISK / DEFENSIVE / CASH.
  3. Wählt bei jedem Lauf automatisch den Kandidaten mit dem besten
     Momentum aus der zum aktuellen Regime passenden Ticker-Liste.
  4. Zeigt die Signal-Historie der letzten 10 Handelstage (TIP-Signal,
     Abstand des NDX-Kurses zur SMA200, SMA-Signal, Hybrid-Regime).
  5. Gibt am Ende ein kurzes Fazit: das aktuell bestätigte Regime, welche
     der beiden Signale es tragen, und ein Hinweis, falls ein Regime-
     Wechsel im Aufbau ist.

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
  die Defensiv-Seite: DEFENSIVE oder CASH, wie bisher entschieden über den
  besten Defensiv-Score (> 0 -> DEFENSIVE, sonst CASH). Das entspricht dem
  Modus "hybrid" in backtest.py.

Mehrere Kandidaten pro Seite (RISK_TICKERS / DEFENSIVE_TICKERS):
  Beide Listen können einen oder mehrere Ticker enthalten. Das
  Makro-Regime (RISK vs. "Defensiv-Seite", d.h. Defensiv-ETF oder Cash)
  wird ausschließlich von den Makro-Signalen (TIP-Canary und Trend-SMA,
  siehe Hybrid-Logik) bestimmt - die Kandidaten
  selbst haben keinen Einfluss darauf. Erst INNERHALB des aktiven
  Regimes wird nach derselben Methode für beide Seiten ausgewählt (siehe
  select_best_candidate()): der Kandidat der jeweiligen Liste mit dem
  höchsten Momentum (reine relative Auswahl, kein Schwellenwert).
  Die Momentum-Länge wird absteigend geprüft (13612U, 136U, 13U, 1U):
  Hat mindestens ein Kandidat der Liste einen Wert der jeweiligen Länge
  (13612U erst ab 252 Handelstagen Historie), gewinnt unter den
  Kandidaten MIT Wert der höchste; Kandidaten mit zu kurzer Historie
  nehmen am Vergleich dann nicht teil (bleiben aber in der Tabelle
  sichtbar). Hat kein Kandidat einen Wert, wird die nächstkürzere Länge
  geprüft. Geht auch 1U für keinen Kandidaten, wird der Kandidat mit der
  LÄNGSTEN verfügbaren Kurshistorie gewählt (kein Momentum-Vergleich
  mehr möglich).
    Die Momentum-Tabellen sortieren die Kandidaten nach derselben Logik:
  zuerst alle mit 13612U-Wert (absteigend nach 13612U), darunter die mit
  136U-Wert (absteigend nach 136U), dann 13U, dann 1U; Kandidaten ganz
  ohne Wert stehen am Ende. Der gewählte Kandidat steht damit oben.
    Ob überhaupt die Defensiv-Seite (statt CASH) aktiv ist, wird
  getrennt entschieden: der nach derselben Methode ermittelte beste
  Score aller Defensiv-Kandidaten wird je Tag gegen 0 geprüft (siehe
  raw_target_position(), defensive_mom_best) - nur bei einem positiven
  besten Score gilt die Defensiv-Seite als aktiv, sonst CASH.
    Die Kandidatenauswahl ist nicht an eine Regime-Phase gebunden,
  sondern folgt bei jedem Lauf den heutigen Momentum-Werten. Ob und wann
  tatsächlich umgeschichtet wird, liegt vollständig beim Nutzer.

13612U-Momentum - Handelstage-Methode (Canary, Risk- und Defensiv-
Kandidaten):
  Score(t) = 1/4 * [ (P0/P1-1) + (P0/P3-1) + (P0/P6-1) + (P0/P12-1) ],
  wobei P1/P3/P6/P12 die Kurse 21/63/126/252 Handelstage ZUVOR in der
  EIGENEN Kurshistorie des jeweiligen Tickers sind (Series.shift(n),
  keine Kalenderlogik). Fallback bei zu kurzer Historie: 136U-Momentum,
  also dieselbe Formel mit den Komponenten 1/3/6 Monate (21/63/126
  Handelstage), siehe momentum_136u(). Die Momentum-Übersichtstabellen
  zeigen zusätzlich die Teilkomponenten 1U und 13U (1- bzw. 1+3-Monats-
  Momentum); diese dienen ebenfalls als weitere Fallback-Stufen der
  Kandidatenauswahl (13612U -> 136U -> 13U -> 1U -> längste Historie).

Kalender:
  Das Canary-Signal (Momentum, Rohsignal, Bestätigungsfilter) läuft
  vollständig auf dem eigenen Handelskalender von TIP (NYSE). Die
  Momentum-Werte der Risk- und Defensiv-Kandidaten werden auf deren
  eigenem Kalender berechnet und anschließend auf den TIP-Kalender
  vorwärtsgefüllt: an einem Tag, an dem die Börse eines Kandidaten
  geschlossen ist, gilt sein zuletzt bekannter Wert.

Whipsaw-/Bestätigungsfilter (Makro-Regime):
  Ein neuer Rohsignal-Wert wird erst nach mehreren aufeinanderfolgenden
  Handelstagen mit demselben (abweichenden) Wert als "bestätigt"
  übernommen - mit zwei getrennten Fenstern je Richtung:
    CONFIRMATION_A = 1  - Handelstage, die nötig sind für einen Wechsel
                          WEG von RISK (zu DEFENSIVE oder CASH)
    CONFIRMATION_B = 2  - Handelstage, die nötig sind für einen Wechsel
                          HIN ZU RISK
  Für einen Wechsel zwischen DEFENSIVE und CASH gilt ebenfalls
  CONFIRMATION_A, da auch dieser Wechsel nicht "hin zu RISK" führt (siehe
  apply_confirmation_filter()). Für das Trend-Signal gelten die eigenen
  Fenster TREND_CONFIRMATION_A / TREND_CONFIRMATION_B (1 / 1). Die
  Signal-Tabelle zeigt das bestätigte Signal beider Zweige sowie das
  daraus kombinierte Regime je Tag. Zusätzlich
  wird ausgegeben, falls sich ein Regimewechsel im Aufbau befindet (z.B.
  "seit 1 Tag abweichend, noch 1 weitere Bestätigung nötig"). Ein im
  Aufbau befindlicher Signalwechsel, der das Hybrid-Regime nicht ändern
  würde (das andere Signal hält RISK), löst keinen Regime-Hinweis aus, wird
  aber im Fazit beim jeweiligen Signal vermerkt.

Timing:
  Das mit dem HEUTIGEN Schlusskurs bestätigte Regime ist die
  Handlungsgrundlage für die Order am heutigen Abend: das Script wird
  nach Börsenschluss ausgeführt, der heutige Schlusskurs ist dann bekannt
  (siehe "Sicherer Auswertungszeitpunkt").

Umfang der abgefragten Kursdaten:
    - Für die 13612U-Formel werden maximal 252 Handelstage Historie VOR
      dem jeweiligen Bewertungstag benötigt (LOOKBACK_DAYS[-1]); der
      SMA200 des Trend-Signals braucht 200 Handelstage (inkl. heute).
    - Zusätzlich sollen die letzten DISPLAY_LAST_N_DAYS=10 Handelstage
      in der Signal-Historie mit vollständigem Momentum gezeigt werden.
    - Zusammen sind das TRADING_DAYS_NEEDED = 252 + 10 = 262
      Handelstage, die großzügig (siehe CALENDAR_DAYS_PER_TRADING_DAY)
      in Kalendertage umgerechnet und als Download-Startdatum verwendet
      werden (siehe DOWNLOAD_LOOKBACK_CALENDAR_DAYS).
  Als Enddatum der Abfrage gilt (siehe compute_query_end_date()):
    - HEUTE (Berliner Kalendertag), falls SAFE_EVALUATION_TIME_BERLIN
      bereits erreicht ist,
    - sonst der letzte Handelstag VOR heute (i.d.R. der Vortag).

Sicherer Auswertungszeitpunkt (yfinance liefert am selben Tag VOR
Börsenschluss einen unfertigen Intraday-Stand statt des Schlusskurses):
  Der reguläre Handelsschluss von NYSE/Nasdaq (TIP) liegt bei 16:00 Uhr
  US-Ostküstenzeit, das entspricht je nach Sommer-/Winterzeit-Lage ca.
  21:00-22:00 Uhr deutscher Zeit. SAFE_EVALUATION_TIME_BERLIN = 22:15 Uhr
  ist ein Sicherheitspuffer. Wird das Script davor
  ausgeführt, wird als Abfrage-Enddatum der letzte VOLLSTÄNDIGE
  Handelstag verwendet (siehe compute_query_end_date()). Zusätzlich
  verwirft load_prices() eine ggf. dennoch gelieferte unfertige heutige
  Kurszeile. Die Regel gilt einheitlich für ALLE Ticker, auch für
  Xetra-ETFs mit früherem Handelsschluss - das ist für diese unnötig
  konservativ (ihre heutige Zeile wird erst am Folgeabend berücksichtigt),
  aber harmlos und hält die Logik einheitlich.

Währung:
  Es werden ausschließlich EUR-notierte Risk- und Defensiv-Ticker
  konfiguriert, eine Währungsumrechnung ist daher nicht nötig. Für das
  Canary-Asset TIP (USD) ist die Währung irrelevant, da nur das
  Kursverhältnis P0/Pn in die Momentum-Formel eingeht. Gleiches gilt für
  den Trend-Index ^NDX (USD): nur das Verhältnis Kurs/SMA zählt.

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
    SAFE_EVALUATION_TIME_BERLIN,
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
    "L8I7.DE": "Amundi Nasdaq-100 (2x)",
    "XDEM.DE": "Xtrackers MSCI World Momentum",
}
DEFENSIVE_TICKERS = {
    "FTGB.SG": "First Trust FactorFX",
    "FXEU.AS": "First Trust FactorFX (EUR hedged)",
    "LYOR.DE": "Amundi Smart Overnight Return",
}

# Ticker -> Anzeigename über alle konfigurierten Ticker (nur Ausgabe).
ALL_TICKER_NAMES: dict[str, str] = {CANARY_TICKER: CANARY[CANARY_TICKER],
                                    TREND_TICKER: TREND[TREND_TICKER],
                                    **RISK_TICKERS, **DEFENSIVE_TICKERS}

# Lookbacks (Handelstage) für den 13612U-Score (Canary, Risk- und
# Defensiv-Kandidaten) sowie den 136U-Fallback bei zu kurzer Historie.
LOOKBACK_DAYS = (21, 63, 126, 252)
LOOKBACK_136U_DAYS = (21, 63, 126)

# Whipsaw-/Bestätigungsfenster (Handelstage) des TIP-Canary-Makrosignals,
# getrennt je Wechselrichtung (siehe Modul-Docstring).
CONFIRMATION_A = 1  # weg von RISK (-> DEFENSIVE/CASH)
CONFIRMATION_B = 2  # hin zu RISK

# Trend-Signal (SMA) der Hybrid-Logik: SMA-Länge in Handelstagen und
# eigene Bestätigungsfenster (gleiche Bedeutung wie oben).
TREND_SMA_DAYS = 200
TREND_CONFIRMATION_A = 1  # weg von RISK
TREND_CONFIRMATION_B = 1  # hin zu RISK

# Anzahl der zuletzt angezeigten Tage in der Signal-Historie.
DISPLAY_LAST_N_DAYS = 10

# Umfang der abgefragten Kursdaten (siehe Docstring): 252 Handelstage
# Lookback für die 13612U-Formel (bzw. die SMA-Länge, falls größer) +
# DISPLAY_LAST_N_DAYS Handelstage, damit auch für die angezeigte
# Signal-Historie überall ein vollständiges Momentum bzw. ein SMA-Wert
# vorliegt. Großzügig (Faktor 1.6 + Puffer) in Kalendertage umgerechnet,
# um Wochenenden/Feiertage abzudecken.
TRADING_DAYS_NEEDED = max(LOOKBACK_DAYS[-1], TREND_SMA_DAYS) + DISPLAY_LAST_N_DAYS  # 262
CALENDAR_DAYS_PER_TRADING_DAY = 1.6
DOWNLOAD_LOOKBACK_CALENDAR_DAYS = int(TRADING_DAYS_NEEDED * CALENDAR_DAYS_PER_TRADING_DAY) + 30

# Maximale Breite der Namensspalte in den Momentum-Tabellen; längere
# Namen werden mit "…" gekürzt.
MOM_TABLE_NAME_COL_MAX = 34


# ----------------------------------------------------------------------
# Kursdaten je Ticker laden (begrenztes Zeitfenster, siehe Docstring)
# ----------------------------------------------------------------------
def load_ticker(ticker: str, query_end_date: pd.Timestamp) -> dict:
    """Lädt die Kurshistorie eines Tickers für das Zeitfenster
    DOWNLOAD_LOOKBACK_CALENDAR_DAYS über yf_data.load_prices() (inkl.
    Konsens-Abfrage, Vollständigkeitsprüfung gegen den Börsenkalender
    und Verwerfen eines unfertigen heutigen Kurses)."""
    start_date = query_end_date - pd.Timedelta(days=DOWNLOAD_LOOKBACK_CALENDAR_DAYS)
    safe, dropped = load_prices(ticker, start_date, query_end_date)
    return {"ticker": ticker, "prices": safe, "dropped_today": dropped}


# ----------------------------------------------------------------------
# Momentum-Berechnung
# ----------------------------------------------------------------------
def momentum_13612u(adj_close: pd.Series, lookback_days: tuple[int, ...] = LOOKBACK_DAYS) -> pd.Series:
    """13612U-Score in Handelstagen (Series.shift(n)) - Canary sowie
    primäre Methode für Risk- und Defensiv-Kandidaten. Über
    `lookback_days` wird dieselbe Formel auch für die 1U-/13U-
    Teilkomponenten der Momentum-Tabellen genutzt."""
    components = [adj_close / adj_close.shift(n) - 1.0 for n in lookback_days]
    return sum(components) / len(components)


def momentum_136u(adj_close: pd.Series, lookback_days: tuple[int, ...] = LOOKBACK_136U_DAYS) -> pd.Series:
    """136U-Score (ohne 12-Monats-Komponente) - Fallback für Kandidaten
    mit zu kurzer Historie für die volle 13612U-Formel, siehe
    select_best_candidate()."""
    return momentum_13612u(adj_close, lookback_days)


# ----------------------------------------------------------------------
# Whipsaw-/Bestätigungsfilter (Makro-Regime)
# ----------------------------------------------------------------------
def raw_target_position(canary_mom: pd.Series, defensive_mom_best: pd.Series) -> pd.Series:
    """Tägliches Rohsignal (ohne Bestätigungsfilter):
      Score(Canary) > 0                               -> "RISK"
      Score(Canary) <= 0 und bestes Defensiv-Mom > 0   -> "DEFENSIVE"
      sonst                                             -> "CASH"
    `defensive_mom_best` = je Tag der Score des nach select_best_
    candidate() besten DEFENSIVE_TICKERS-Kandidaten, oder NaN, falls
    sich an diesem Tag kein Score ermitteln lässt (dann CASH, da
    NaN > 0 stets False ist)."""
    position = pd.Series("CASH", index=canary_mom.index, dtype=object)
    risk_on = canary_mom > 0
    defensive_on = (~risk_on) & (defensive_mom_best > 0)
    position[risk_on] = "RISK"
    position[defensive_on] = "DEFENSIVE"
    return position


def apply_confirmation_filter(raw_position: pd.Series, a: int, b: int) -> tuple[pd.Series, str | None, int]:
    """
    Whipsaw-Filter mit zwei getrennten Bestätigungsfenstern je
    Wechselrichtung (siehe Modul-Docstring): ein neuer Zustand wird erst
    übernommen, wenn das rohe Tagessignal mehrere aufeinanderfolgende
    Handelstage denselben neuen Wert `s` zeigt - wie viele, hängt vom
    ZIEL-Wert ab:
      s == "RISK"  -> `b` Handelstage nötig (Wechsel HIN ZU Risk)
      s != "RISK"  -> `a` Handelstage nötig (Wechsel WEG von Risk,
                      inkl. DEFENSIVE <-> CASH)
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
            required = b if s == "RISK" else a
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
    (Gleichstand: defensiv, wie beim TIP-Score = 0). Tage ohne SMA-Wert
    entfallen. Rückgabe: (Rohsignal, SMA-Serie auf dem vollen Kalender)."""
    sma = trend_prices.rolling(sma_days).mean()
    raw = pd.Series(np.where(trend_prices > sma, "RISK", "DEFENSIVE"),
                    index=trend_prices.index, dtype=object)[sma.notna()]
    return raw, sma


def combine_state(tip_state: str, trend_state: str) -> str:
    """Hybrid-Verknüpfung für einen einzelnen Zustand: "RISK", sobald
    mindestens eines der beiden Signale "RISK" meldet; sonst der
    Defensiv-Zustand des TIP-Zweigs ("DEFENSIVE" oder "CASH")."""
    return "RISK" if "RISK" in (tip_state, trend_state) else tip_state


def combine_regime(tip_state: pd.Series, trend_state: pd.Series) -> pd.Series:
    """Wie combine_state(), für zwei Zeitreihen gleichen Index."""
    risk = (tip_state == "RISK") | (trend_state == "RISK")
    return tip_state.mask(risk, "RISK")


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
# Auswahl des besten Kandidaten innerhalb einer Ticker-Liste - für Risk-
# und Defensiv-Kandidaten identisch. select_best_candidate() gilt für
# einen einzelnen Tag (das heutige Datum), best_score_series() liefert
# den besten Score für jeden Tag (Makro-Entscheidung DEFENSIVE vs. CASH).
# ----------------------------------------------------------------------
# Momentum-Längen in der Reihenfolge, in der sie für die Kandidatenauswahl
# geprüft werden: (Schlüssel in side_momenta(), Klartext).
SELECTION_METHODS = (("13612u", "13612U"), ("136u", "136U"), ("13u", "13U"), ("1u", "1U"))


def select_best_candidate(tickers: list[str],
                           price_data: dict[str, dict],
                           moms: dict[str, dict[str, pd.Series]],
                           date: pd.Timestamp) -> tuple[str, float | None, str]:
    """Wählt den Kandidaten aus `tickers` mit dem höchsten Momentum an
    `date` (reine relative Auswahl, kein Schwellenwert). Die Momentum-
    Länge wird absteigend geprüft (SELECTION_METHODS: 13612U, 136U, 13U,
    1U): Hat mindestens ein Kandidat an diesem Datum einen Wert der
    jeweiligen Länge, gewinnt unter den Kandidaten MIT Wert der höchste
    (Kandidaten ohne Wert, d.h. zu kurze Historie, scheiden aus dem
    Vergleich aus); sonst wird die nächstkürzere Länge geprüft. Hat auch
    für 1U kein Kandidat einen Wert, wird der Kandidat mit der längsten
    verfügbaren Kurshistorie (Stand `date`) gewählt. `moms` = Ausgabe von
    side_momenta() (Kennzahl -> Ticker -> Serie); `price_data` wird nur für
    den Historienlängen-Fallback gebraucht. Rückgabe: (Ticker, Score oder
    None, verwendete Methode als Klartext)."""
    for key, label in SELECTION_METHODS:
        mom_dict = moms[key]
        scores = {t: mom_dict[t].loc[date] for t in tickers
                  if date in mom_dict[t].index and pd.notna(mom_dict[t].loc[date])}
        if scores:
            best = max(scores, key=scores.get)
            return best, scores[best], label

    hist_len = {t: price_data[t]["prices"].loc[:date].dropna().shape[0] for t in tickers}
    best = max(hist_len, key=hist_len.get)
    return best, None, "längste Historie"


def best_score_series(tickers: list[str],
                       moms: dict[str, dict[str, pd.Series]],
                       dates: pd.DatetimeIndex) -> pd.Series:
    """Score des besten Kandidaten für JEDEN Tag in `dates`, nach
    derselben Regel wie select_best_candidate(): je Tag der höchste Score
    der längsten Momentum-Länge (SELECTION_METHODS), für die mindestens
    ein Kandidat einen Wert hat; NaN, wenn für keine Länge ein Wert
    vorliegt (der Historienlängen-Fallback liefert keinen Score). Die
    Momentum-Serien müssen auf `dates` ausgerichtet sein. Wird für die
    Makro-Entscheidung DEFENSIVE vs. CASH gebraucht (siehe
    raw_target_position())."""
    def best_of(mom_dict: dict[str, pd.Series]) -> pd.Series:
        frame = pd.DataFrame({t: mom_dict[t] for t in tickers}).reindex(dates)
        return frame.max(axis=1)          # überspringt NaN; alle NaN -> NaN

    scores = best_of(moms[SELECTION_METHODS[0][0]])
    for key, _ in SELECTION_METHODS[1:]:
        scores = scores.fillna(best_of(moms[key]))
    return scores.astype(float)


def sort_candidates(tickers: list[str],
                    moms: dict[str, dict[str, pd.Series]],
                    date: pd.Timestamp) -> list[str]:
    """Sortiert `tickers` für die Momentum-Tabellen: nach der längsten
    Momentum-Länge (SELECTION_METHODS), für die der Kandidat an `date`
    einen Wert hat - Kandidaten mit 13612U-Wert zuerst, dann die mit
    136U-Wert usw. - und innerhalb derselben Länge absteigend nach diesem
    Wert. Kandidaten ohne jeden Wert stehen am Ende (Reihenfolge der
    Konfiguration bleibt erhalten, da sorted() stabil ist)."""
    def key(t: str) -> tuple[int, float]:
        for rank, (mkey, _) in enumerate(SELECTION_METHODS):
            series = moms[mkey][t]
            if date in series.index and pd.notna(series.loc[date]):
                return rank, -float(series.loc[date])
        return len(SELECTION_METHODS), 0.0
    return sorted(tickers, key=key)


# ----------------------------------------------------------------------
# Hilfsfunktionen für main()
# ----------------------------------------------------------------------
def _on_calendar(series_by_ticker: dict[str, pd.Series], calendar: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Richtet jede Serie per Vorwärtsfüllung auf `calendar` aus."""
    return {t: s.reindex(calendar, method="ffill") for t, s in series_by_ticker.items()}


def _from_date(series_by_ticker: dict[str, pd.Series], start: pd.Timestamp) -> dict[str, pd.Series]:
    """Schneidet jede Serie ab `start` (inklusive) zu."""
    return {t: s.loc[s.index >= start] for t, s in series_by_ticker.items()}


def _mom_table_name(name: str, name_col: int) -> str:
    if len(name) > name_col:
        return name[: name_col - 1] + "…"
    return name


def print_momentum_table(title: str,
                         tickers: dict[str, str],
                         moms: dict[str, dict[str, pd.Series]],
                         today: pd.Timestamp,
                         chosen_ticker: str | None) -> None:
    """Gibt die Momentum-Übersicht (1U/13U/136U/13612U) der Kandidaten
    einer Seite aus. `moms` enthält je Kennzahl ("1u", "13u", "136u",
    "13612u") das Ticker -> Serie-Dict. `chosen_ticker` wird als
    "heute gewählt" markiert (None: keine Markierung). Die Zeilen sind
    nach sort_candidates() sortiert (längste verfügbare Momentum-Länge
    zuerst, darin absteigend nach Wert). Feste
    Spaltenbreiten, damit die Tabellen bei unterschiedlich langen Namen
    nicht verrutschen; die Namensspalte richtet sich nach dem längsten
    Namen, höchstens aber MOM_TABLE_NAME_COL_MAX."""
    print(f"\n{title} (Stand {today.date()}):")
    ticker_col = max(10, max(len(t) for t in tickers) + 1)
    name_col = min(MOM_TABLE_NAME_COL_MAX, max(len(n) for n in tickers.values()))
    header = (f"  {'Ticker':<{ticker_col}}{'Name':<{name_col}}  "
              f"{'1U':>8}{'13U':>8}{'136U':>8}{'13612U':>8}")
    print(header)
    print("-" * len(header))

    def value(series: pd.Series) -> float:
        return series.loc[today] if today in series.index and pd.notna(series.loc[today]) else float("nan")

    for t in sort_candidates(list(tickers), moms, today):
        v1u, v13u, v136u, v13612u = (value(moms[key][t]) for key in ("1u", "13u", "136u", "13612u"))
        marker = " <- heute gewählt" if t == chosen_ticker else ""
        print(f"  {t:<{ticker_col}}"
              f"{_mom_table_name(tickers[t], name_col):<{name_col}}  "
              f"{v1u:>8.2%}{v13u:>8.2%}{v136u:>8.2%}{v13612u:>8.2%}{marker}")


def side_momenta(data: dict[str, dict], calendar: pd.DatetimeIndex) -> dict[str, dict[str, pd.Series]]:
    """Berechnet je Ticker die Momentum-Kennzahlen 1U/13U/136U/13612U auf
    dessen eigenem Kalender und richtet sie auf `calendar` aus."""
    native = {
        "1u": {t: momentum_13612u(d["prices"], lookback_days=(21,)) for t, d in data.items()},
        "13u": {t: momentum_13612u(d["prices"], lookback_days=(21, 63)) for t, d in data.items()},
        "136u": {t: momentum_136u(d["prices"]) for t, d in data.items()},
        "13612u": {t: momentum_13612u(d["prices"]) for t, d in data.items()},
    }
    return {key: _on_calendar(series, calendar) for key, series in native.items()}


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    now_berlin = datetime.now(BERLIN_TZ)
    cutoff_str = SAFE_EVALUATION_TIME_BERLIN.strftime("%H:%M")
    print(f"Aktuelle Zeit (Berlin): {now_berlin.strftime('%Y-%m-%d %H:%M:%S')}")

    query_end_date = compute_query_end_date(now_berlin)
    if now_berlin.time() < SAFE_EVALUATION_TIME_BERLIN:
        print(f"[warn] Es ist noch vor {cutoff_str} Uhr deutscher Zeit - es werden nur "
              f"Kurse bis {query_end_date.date()} (letzter vollständiger Handelstag) "
              f"abgefragt.")
    else:
        print(f"[info] Nach {cutoff_str} Uhr deutscher Zeit - es werden Kurse bis "
              f"heute ({query_end_date.date()}) abgefragt, falls bereits verfügbar.")
    print()

    # --- Daten laden ---
    canary = load_ticker(CANARY_TICKER, query_end_date)
    trend = load_ticker(TREND_TICKER, query_end_date)
    risk_data = {t: load_ticker(t, query_end_date) for t in RISK_TICKERS}
    defensive_data = {t: load_ticker(t, query_end_date) for t in DEFENSIVE_TICKERS}

    if canary["dropped_today"]:
        print(f"[info] {ALL_TICKER_NAMES[CANARY_TICKER]}: heutiger (unfertiger) Kurs "
              f"verworfen, letzter berücksichtigter Handelstag: "
              f"{canary['prices'].index[-1].date()}")
    for t, d in {TREND_TICKER: trend, **risk_data, **defensive_data}.items():
        if d["dropped_today"]:
            print(f"[info] {ALL_TICKER_NAMES[t]}: heutiger Kurs verworfen "
                  f"(Sicherheitsregel, siehe Docstring), letzter berücksichtigter "
                  f"Handelstag: {d['prices'].index[-1].date()}")
    print()

    # --- Momentum je Ticker auf dem eigenen Kalender berechnen und auf
    #     den TIP-Kalender ausrichten (siehe Docstring "Kalender") ---
    master_calendar = canary["prices"].index
    canary_mom = momentum_13612u(canary["prices"])
    risk_mom = side_momenta(risk_data, master_calendar)
    defensive_mom = side_momenta(defensive_data, master_calendar)

    # Makro-Entscheidung DEFENSIVE vs. CASH: je Tag der Score des besten
    # Defensiv-Kandidaten (13612U, sonst 136U, sonst kein Score).
    defensive_mom_best = best_score_series(
        list(DEFENSIVE_TICKERS), defensive_mom, master_calendar)

    # Trend-Signal (SMA): Rohsignal und Bestätigungsfilter auf dem eigenen
    # Kalender des Index, danach vorwärtsgefüllt auf den TIP-Kalender.
    trend_raw_native, trend_sma_native = trend_raw_position(trend["prices"], TREND_SMA_DAYS)
    if trend_raw_native.empty:
        raise ValueError(f"Zu wenig Historie für den SMA{TREND_SMA_DAYS} von {TREND_TICKER} - "
                          f"ggf. DOWNLOAD_LOOKBACK_CALENDAR_DAYS erhöhen.")
    trend_conf_native, trend_pending_candidate, trend_pending_count = apply_confirmation_filter(
        trend_raw_native, TREND_CONFIRMATION_A, TREND_CONFIRMATION_B)
    trend_raw = trend_raw_native.reindex(master_calendar, method="ffill")
    trend_conf = trend_conf_native.reindex(master_calendar, method="ffill")
    trend_gap = (trend["prices"] / trend_sma_native - 1.0).reindex(master_calendar, method="ffill")

    valid_mask = canary_mom.notna() & defensive_mom_best.notna() & trend_conf.notna()
    if not valid_mask.any():
        raise ValueError("Zu wenig gemeinsame Historie für die gewählten Lookbacks - "
                          "ggf. DOWNLOAD_LOOKBACK_CALENDAR_DAYS erhöhen.")
    first_valid_date = master_calendar[valid_mask][0]

    canary_mom = canary_mom.loc[canary_mom.index >= first_valid_date]
    defensive_mom_best = defensive_mom_best.loc[defensive_mom_best.index >= first_valid_date]
    trend_raw = trend_raw.loc[trend_raw.index >= first_valid_date]
    trend_conf = trend_conf.loc[trend_conf.index >= first_valid_date]
    trend_gap = trend_gap.loc[trend_gap.index >= first_valid_date]
    risk_mom = {key: _from_date(series, first_valid_date) for key, series in risk_mom.items()}
    defensive_mom = {key: _from_date(series, first_valid_date) for key, series in defensive_mom.items()}

    # --- Rohsignal + Bestätigungsfilter (TIP), Hybrid-Verknüpfung mit SMA ---
    raw_position = raw_target_position(canary_mom, defensive_mom_best)
    tip_confirmed, pending_candidate, pending_count = apply_confirmation_filter(
        raw_position, CONFIRMATION_A, CONFIRMATION_B)
    confirmed_position = combine_regime(tip_confirmed, trend_conf)

    today = confirmed_position.index[-1]
    today_regime = confirmed_position.iloc[-1]
    tip_state = tip_confirmed.iloc[-1]
    trend_state = trend_conf.iloc[-1]

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

    # --- Zielauswahl anhand der heutigen Momentum-Werte ---
    target_ticker = None
    if today_regime == "RISK":
        target_ticker, _, _ = select_best_candidate(
            list(RISK_TICKERS), risk_data, risk_mom, today)
    elif today_regime == "DEFENSIVE":
        target_ticker, _, _ = select_best_candidate(
            list(DEFENSIVE_TICKERS), defensive_data, defensive_mom, today)

    print(f"\nAktuell bestätigtes Regime (Stand Schlusskurs {today.date()}): {today_regime}")

    # --- Momentum-Übersicht der Risk- und Defensiv-Kandidaten ---
    print_momentum_table("Momentum der Risk-Kandidaten", RISK_TICKERS, risk_mom, today,
                         target_ticker if today_regime == "RISK" else None)
    print_momentum_table("Momentum der Defensiv-Kandidaten", DEFENSIVE_TICKERS, defensive_mom, today,
                         target_ticker if today_regime == "DEFENSIVE" else None)

    # --- Hinweis auf im Aufbau befindlichen Regimewechsel ---
    tip_pending = None
    if pending_candidate is not None:
        tip_pending = (pending_candidate, pending_count,
                       CONFIRMATION_B if pending_candidate == "RISK" else CONFIRMATION_A)
    trend_pending = None
    if trend_pending_candidate is not None:
        trend_pending = (trend_pending_candidate, trend_pending_count,
                         TREND_CONFIRMATION_B if trend_pending_candidate == "RISK"
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

    tip_risk, trend_risk = tip_state == "RISK", trend_state == "RISK"
    if tip_risk and trend_risk:
        print("\nBeide Signale melden RISK. Das Regime wechselt erst, wenn beide "
              "nicht mehr RISK melden.")
    elif tip_risk:
        print(f"\nNur das TIP-Signal trägt RISK (der NDX liegt unter seinem SMA{TREND_SMA_DAYS}). "
              f"Kippt das TIP-Signal ({CONFIRMATION_A} Bestätigungstag(e)), wechselt das "
              f"Regime zu DEFENSIVE/CASH, solange der NDX nicht über die SMA zurückkehrt.")
    elif trend_risk:
        print(f"\nNur das SMA-Signal trägt RISK (das TIP-Signal ist nicht RISK). Fällt der NDX "
              f"unter seine SMA{TREND_SMA_DAYS} ({TREND_CONFIRMATION_A} Bestätigungstag(e)), "
              f"wechselt das Regime zu DEFENSIVE/CASH, solange das TIP-Signal nicht RISK meldet.")
    else:
        print(f"\nBeide Signale melden nicht RISK. Zurück zu RISK, sobald eines davon bestätigt "
              f"RISK meldet (TIP {CONFIRMATION_B} Tag(e), SMA {TREND_CONFIRMATION_B} Tag(e)).")

    if scenarios:
        print("\n[Beachte den Hinweis oben zum im Aufbau befindlichen Regimewechsel.]")


if __name__ == "__main__":
    main()
    if sys.stdin.isatty():  # nur bei interaktivem Start (nicht in der Cloud/Pipe) warten
        input("\nFertig - Enter zum Beenden drücken...")
