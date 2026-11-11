"""
Backtest: Hybrid-Strategie (TIP-Canary + Nasdaq-100-SMA200), rein synthetisch
==============================================================================

Das Script rechnet DURCHGEHEND mit einem synthetischen S&P-500-Asset (SPY in
EUR umgerechnet, ggf. gehebelt) - ohne reale ETF-Kurse und ohne Verkettung.
Grund: Europäische ETFs werden um 17:30 (Xetra) bewertet, das Signal entsteht
aber zum US-Schluss (~22:00 MEZ); die Kalibrierung (kalibrierung_hebel.py, gegen reale ETFs)
zeigt, dass am Xetra-Schluss nur ca. 60 % der US-Tagesbewegung eingepreist
sind. Backtests mit realen ETFs sind deshalb optimistisch; der synthetische
Kurs am US-Schluss entspricht einer Abend-Ausführung.

Strategien (je Risk-Asset-Variante, alle nach Steuern):
  Hybrid (maßgeblich)  Risk, wenn das TIP-Canary-Signal ODER das Nasdaq-100-
                       SMA-Signal auf Risk steht. Defensiv nur, wenn BEIDE
                       schlecht stehen. Ein TIP-Risk-Signal gilt immer; in
                       TIP-Defensiv-Phasen hält der Nasdaq-100 (^NDX) das
                       Risk-Asset, solange sein Schlusskurs STRIKT ÜBER dem
                       200-Tage-SMA liegt (Gleichstand zählt wie beim TIP-
                       Score = 0 als "nicht über", also defensiv).
  TIP-Canary           nur das TIP-Signal (Vergleich).
  NDX-SMA200           nur das Nasdaq-100-SMA-Signal (Vergleich).
  Buy & Hold           Referenz.
  In defensiven Phasen wird Tagesgeld gehalten (siehe unten), kein
  Defensiv-ETF. Wechsel = Wechsel zwischen Risk-Asset und Tagesgeld (jede
  Richtung einzeln).

Getestete Varianten:
  RISK_TICKERS enthält EINE oder MEHRERE Varianten (z.B. 2x- und 1x-Hebel).
  Für JEDE Variante werden die drei Strategien gerechnet und einer Buy & Hold-
  Kurve (nach Steuern) gegenübergestellt - diese Zahlen landen für ALLE
  Varianten im Gesamtvergleich (Kennzahlen-Tabelle) und in den beiden Plots.
  Die AUSFÜHRLICHEN Zusatz-Auswertungen (Zeitanteile/Steuern, Jahresvergleich,
  Defensiv-Phasen im Detail) werden dagegen NUR für die ERSTE Variante in
  RISK_TICKERS (Dictionary-Reihenfolge) erstellt.

Kostenmodell des synthetischen Assets (zeitvariabel, siehe build_synthetic_eur()):
  Tagesrendite = Brutto-Rendite - (fixe Kosten + (Hebel-1) * Zins(t)) / 252
  - fixe Kosten aus der Kalibrierung: 1x 0,25 % p.a. (SXR8-Niveau), 2x 1,20 % p.a.
    (18MF.DE, Hebel in EUR, Zins ECBDFR) bzw. 1,58 % p.a. (DBPG.DE, Hebel in USD,
    Zins DFF). Zinsreihen kommen von FRED über fred_data.py (Cache in yf_data/FRED_<ID>.csv).
  - LEVER_CURRENCY = "EUR": der Hebel wirkt auch auf den Wechselkurs (wie 18MF.DE,
    Hauptfall); "USD": Hebel nur auf den Aktienindex, Wechselkurs 1x (wie DBPG.DE).
  - Vor 2011 gibt es keine Kalibrierung; dieselben Parameter gelten als Annahme.
  - Der Hebel ist ein täglich zurückgesetzter Hebel (daily rebalancing) auf die
    Tagesrenditen, inkl. des dadurch entstehenden "Volatility-Decay"-Effekts.

Währungsumrechnung:
  SPY notiert in USD und wird mit dem Yahoo-Ticker EUR=X in EUR umgerechnet
  (EUR=X notiert "EUR JE 1 USD", typischerweise 0.6-1.3). EUR=X wird von
  eintägigen Datenfehlern bereinigt (siehe clean_fx_spikes(), inkl. der
  8.-des-Monats-Fehler von 2008); ein Wert außerhalb von [0.4, 2.0] löst eine
  Warnung aus (z.B. bei vertauschter Umrechnungsrichtung). Caveat: EUR=X wird
  wie jeder andere Ticker über yf_data.py geladen - dessen Börsenkalender-
  Vollständigkeitsprüfung kennt keinen speziellen FX-Kalender für "=X"-Ticker
  und ordnet ersatzweise den NYSE-Kalender zu. An US-Feiertagen, an denen der
  Devisenmarkt durchgehend handelt, kann das vereinzelt zu falsch-positiven
  "fehlender Handelstag"-Meldungen führen.

Basis-Strategie (TIP-Canary-Signal):
  - TIP (iShares TIPS Bond ETF) dient als "Canary Asset". Für TIP wird der
    13612U-Momentum-Score gebildet:
        Score = 1/4 * [ (P0/P1 - 1) + (P0/P3 - 1) + (P0/P6 - 1) + (P0/P12 - 1) ]
    mit P1/P3/P6/P12 = Kurse 21/63/126/252 HANDELSTAGE zuvor in TIPs eigener
    Kurshistorie (Series.shift(n), keine Kalenderlogik; LOOKBACK_DAYS_CANARY).
  - Score > 0 ("Risk-on"): Investition ins Risk-Asset. Score <= 0 ("Risk-off"):
    Tagesgeld.

Rebalancing / Whipsaw-Filter:
  Ein Wechsel der Position wird erst übernommen, wenn das rohe Tagessignal
  mehrere aufeinanderfolgende Handelstage dieselbe neue Position anzeigt
  ("Bestätigungsfenster"), getrennt je Wechselrichtung:
    CONFIRMATION_A = 1  - Handelstage für den Wechsel WEG von RISK
    CONFIRMATION_B = 2  - Handelstage für den Wechsel HIN ZU RISK
  Ein Fenster von 1 bedeutet: der Wechsel wird sofort übernommen (siehe
  apply_confirmation_filter()). Das SMA-Signal hat einen eigenen Filter
  (TREND_CONFIRMATION_A/B): A = Handelstage, die der Kurs UNTER der SMA bleiben
  muss, bevor das Signal auf "Defensiv" kippt, B = Handelstage über der SMA,
  bevor es zurück auf "Risk" kippt.

Kalender (Master-Kalender):
  Das Signal (Momentum, Rohsignal, Bestätigungsfilter) wird auf dem eigenen
  Handelskalender der Signalquelle (TIP bzw. ^NDX) berechnet. Ausführung und
  Renditen laufen auf einem einzigen Master-Kalender, dem Handelskalender des
  synthetischen Risk-Assets (SPY, NYSE). Für jeden Tag d des Master-Kalenders
  gilt die zuletzt bestätigte Signalposition des letzten Signal-Handelstags
  STRENG VOR d (kein Look-Ahead: das Signal vom Schlusskurs des Tages t wirkt
  auf die Rendite ab der nächsten Zeile). Vor dem ersten Signaltag gilt
  "DEFENSIVE".

Startdatum:
  Da die Lookbacks (insb. 12 Monate/252 Handelstage) eine Vorlaufzeit brauchen,
  beginnt der Backtest am frühestmöglichen Tag des Master-Kalenders mit
  vollständigem TIP-Signal.

Tagesgeld (Risk-off):
  In defensiven Phasen wird Tagesgeld gehalten: Zins = max(Zins(t) - Abschlag, 0)
  (TAGESGELD_RATE, TAGESGELD_ABSCHLAG; nie negativ), täglich NACH Abgeltungsteuer
  gutgeschrieben (ohne Teilfreistellung). Kein Spread, keine Vorabpauschale,
  kein Verkaufsgewinn. TAGESGELD_RATE = None: Cash mit 0 %.

Besteuerung:
  Das Script zeigt ausschließlich Ergebnisse NACH deutscher Kapitalertrag-
  besteuerung an. Berücksichtigt werden:
    - Kapitalertragsteuer (Abgeltungsteuer + Soli, nach Abzug der Teilfrei-
      stellung des Risk-Assets nach § 20 InvStG, siehe "teilfreistellung" in
      RISK_TICKERS) auf realisierte Gewinne bei jedem Positionswechsel.
    - Die jährliche Vorabpauschale (siehe
      https://de.wikipedia.org/wiki/Vorabpauschale) für die über einen
      Jahresende gehaltene Fondsposition (abgezogen am letzten Handelstag des
      Jahres, im selben Jahr), ebenfalls mit der Teilfreistellung. Für den
      Basiszins wird bewusst ein fester, zukunftsgerichteter Wert von 2,5 %
      angenommen (siehe BASISZINS). Details siehe apply_taxes().
    - Spread: "spread" je Variante = voller Geld-Brief-Spread relativ zur Mitte.
      Bei jedem Wechsel fällt die Hälfte des Spreads der verkauften und der
      gekauften Position an (Tagesgeld 0); steuerlich wie real (siehe
      apply_taxes(), Punkt 3). SPREAD_SCALE skaliert alle Werte (0 = aus,
      2 = Krisenaufschlag). Nicht abgebildet: Lücke zwischen Signalschluss und
      Orderausführung (Slippage), Kirchensteuer, Sparer-Pauschbetrag.

Kursdaten kommen von Yahoo Finance über das gemeinsame Modul yf_data.py, es
wird der "Adj Close" (Adjusted Close) verwendet - inklusive Vollständigkeits-
prüfung gegen den echten Börsenkalender, Auffüllen bereits bekannter, aber
diesmal fehlender Handelstage aus einer persistenten lokalen Historie sowie
Korrektur bekannter, bestätigter Kurssprünge - siehe dortiger Docstring.

Ergebnisse (Vergleichstabelle, Zusatzkennzahlen, Jahresübersicht) werden sowohl
auf der Konsole ausgegeben als auch gesammelt in eine einzelne Textdatei
geschrieben (siehe OUTPUT_DIR/main()), zusätzlich zu den beiden Plots
(Strategievergleich, Drawdown-Verlauf).

Abhängigkeiten:
    pip install -r requirements.txt
"""


from __future__ import annotations

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

from fred_data import FRED_CACHE_DIR, FredUnavailableError, load_fred_rate   # noqa: F401
from yf_data import (
    BERLIN_TZ,
    compute_query_end_date,
    load_prices,
)


# ----------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------
# Canary-Asset: liefert nur das Signal (13612U-Momentum), wird nicht gehalten.
CANARY_TICKER = "TIP"   # iShares TIPS Bond ETF

# EINE oder MEHRERE Risk-Asset-Varianten (siehe Modul-Docstring "Getestete
# Varianten") - NUR die ERSTE Variante (Dictionary-Reihenfolge) bekommt die
# ausführlichen Zusatz-Tabellen.
#   Der Dictionary-KEY ist ein FREI WÄHLBARER, eindeutiger Varianten-Name
#   (KEIN Yahoo-Ticker).
#   "ticker": Yahoo-Ticker der Basis (SPY, notiert in USD, wird nach EUR
#     umgerechnet). Mehrere Varianten dürfen denselben "ticker" teilen - die
#     Rohkurse werden nur EINMAL abgerufen.
#   "name": Anzeigename (nur Ausgabe).
#   "teilfreistellung": Satz nach § 20 InvStG (0.30 = Aktienfonds, mind. 51 %
#     Aktienquote; 0.15 = Mischfonds; 0.0 = sonstige Fonds) - KEIN Default,
#     siehe _teilfreistellung().
#   "leverage": synthetischer Hebel (1.0 = ungehebelt), siehe build_synthetic_eur().
#   "lever_currency", "fixed_cost_pa", "funding_rate": Kostenmodell (siehe
#     Modul-Docstring): Währung, in der der Hebel wirkt, fixe Kosten p.a. und
#     FRED-Zinsreihe der Finanzierung (None bei 1x).
#   "spread": voller Geld-Brief-Spread des Risk-Assets (relativ zur Mitte, z.B.
#     0.002 = 0,2 %), optional, Standard 0. Pro Kauf/Verkauf fällt die HÄLFTE an,
#     siehe apply_taxes().
# Hebelwährung des 2x-Assets: "EUR" = Hebel wirkt auch auf den Wechselkurs (wie
# 18MF.DE, Hauptfall; Finanzierung zum Euro-Zins), "USD" = Hebel nur auf den
# Aktienindex, Wechselkurs 1x (wie DBPG.DE; Finanzierung zum US-Zins).
LEVER_CURRENCY = "EUR"
# Kalibrierte Parameter (kalibrierung_hebel.py, gegen reale ETFs, Lauf vom 2026-10-20): fixe Kosten
# p.a. bei Zinsdurchleitung 100 % und die FRED-Zinsreihe der Hebel-Finanzierung.
LEVER_PARAMS = {
    "EUR": {"fixed_cost_pa": 0.0120, "funding_rate": "ECBDFR"},
    "USD": {"fixed_cost_pa": 0.0158, "funding_rate": "DFF"},
}
FIXED_COST_1X = 0.0025        # SXR8 gegen SPY (SPY-TER 0,09 % ist schon im Kurs)
# Tagesgeld in defensiven Phasen: Zins = max(EZB-Einlagensatz - Abschlag, 0),
# täglich gutgeschrieben NACH Abgeltungsteuer (ohne Teilfreistellung, Sparer-
# Pauschbetrag bleibt wie überall unberücksichtigt). Kein Spread, keine
# Vorabpauschale, kein Verkaufsgewinn. TAGESGELD_RATE = None -> Cash mit 0 %.
TAGESGELD_RATE = "ECBDFR"
TAGESGELD_ABSCHLAG = 0.0025   # Prozentpunkte unter dem Einlagensatz (0,25 %)
RISK_TICKERS = {
    "SP500_2x": {"ticker": "SPY", "name": "S&P 500", "teilfreistellung": 0.30,
                 "leverage": 2.0,
                 "lever_currency": LEVER_CURRENCY,
                 "fixed_cost_pa": LEVER_PARAMS[LEVER_CURRENCY]["fixed_cost_pa"],
                 "funding_rate": LEVER_PARAMS[LEVER_CURRENCY]["funding_rate"],
                 "spread": 0.002},
    "SP500_1x": {"ticker": "SPY", "name": "S&P 500", "teilfreistellung": 0.30,
                 "leverage": 1.0,
                 "lever_currency": "EUR", "fixed_cost_pa": FIXED_COST_1X,
                 "funding_rate": None,
                 "spread": 0.0005},
}

# Yahoo-Finance-Ticker für den EUR/USD-Wechselkurs, notiert als "EUR JE
# 1 USD" (siehe Modul-Docstring "Währungsumrechnung", load_eur_per_usd()).
FX_TICKER = "EUR=X"

# Ausführliche Risk-Phasen-Tabelle (Start, Ende, Tage, Asset, Rendite je Phase)
# in der Auswertung ausgeben? Standard: aus - die Defensiv-Phasen-Tabelle
# ist der aussagekräftige Teil.
SHOW_RISK_PHASES = False

OUTPUT_DIR = Path("backtest")
OUTPUT_DIR.mkdir(exist_ok=True)

# Lookbacks in HANDELSTAGEN für den 13612U-Score des Canary-Assets
# (TIP): 1M/3M/6M/12M = 21/63/126/252 Handelstage, gezählt in TIPs
# eigener Kurshistorie.
LOOKBACK_DAYS_CANARY = (21, 63, 126, 252)

# Whipsaw-/Bestätigungsfenster (in Handelstagen) des TIP-Canary-
# Signals, GETRENNT je Wechselrichtung (siehe Modul-Docstring
# "Rebalancing / Whipsaw-Filter").
CONFIRMATION_A = 1  # Risk -> Defensiv
CONFIRMATION_B = 2  # Defensiv -> Risk

# Nasdaq-100-SMA-Signal, eigener Whipsaw-Filter (getrennt vom TIP). Signalquelle:
# Preisindex ^NDX (USD, nur Signal - es wird nicht gehandelt, daher keine
# Währungsumrechnung).
TREND_TICKER = "^NDX"
TREND_SMA_DAYS = 200
TREND_CONFIRMATION_A = 1  # SMA-Signal: Risk -> Defensiv (Kurs unter SMA)
TREND_CONFIRMATION_B = 2  # SMA-Signal: Defensiv -> Risk (Kurs über SMA)

# Anzeigenamen der Strategien (Reihenfolge = Ausgabe-Reihenfolge)
STRATEGY_NAMES = {"hybrid": "TIPxSMA", "tip": "TIP", "sma": "SMA"}

TRADING_DAYS_PER_YEAR = 252

# Deutsche Kapitalertragsteuer auf realisierte Gewinne beim Verkauf von
# Wertpapieren (Abgeltungsteuer 25% + Solidaritätszuschlag 5,5% darauf
# = 25% * 1,055 = 26,375%, unreduzierter Satz vor Teilfreistellung).
# Kirchensteuer ist NICHT berücksichtigt.
ABGELTUNGSTEUER_BASISSATZ = 0.26375
APPLY_CAPITAL_GAINS_TAX = True


def _teilfreistellung(variant: str) -> float:
    """Teilfreistellung der Risk-Asset-Variante `variant` (Schlüssel in
    RISK_TICKERS) nach § 20 InvStG. KEIN Default: ein stiller Fallback-Wert
    würde bei einem vergessenen Eintrag eine falsche Steuerannahme
    verschleiern statt sie sichtbar zu machen."""
    try:
        return RISK_TICKERS[variant]["teilfreistellung"]
    except KeyError:
        raise KeyError(
            f"{variant}: keine Teilfreistellung hinterlegt - bitte in RISK_TICKERS "
            f"mit \"teilfreistellung\" eintragen.") from None


def capital_gains_tax_rate_for_ticker(ticker: str) -> float:
    """Effektiver Kapitalertragsteuersatz für `ticker`, nach Abzug
    seiner individuellen Teilfreistellung (siehe ABGELTUNGSTEUER_BASISSATZ,
    _teilfreistellung())."""
    return ABGELTUNGSTEUER_BASISSATZ * (1.0 - _teilfreistellung(ticker))


def vorabpauschale_faktor_for_ticker(ticker: str) -> float:
    """Faktor (1 - Teilfreistellung), mit dem der Vorabpauschale-
    Basisertrag für `ticker` multipliziert wird (siehe apply_taxes())."""
    return 1.0 - _teilfreistellung(ticker)


# Spread (Geld-Brief-Spanne): Skalierer auf alle "spread"-Angaben in
# RISK_TICKERS (0 = ausschalten, 2 = doppelte Spreads, z.B. als
# Krisenaufschlag/Sensitivität). Siehe apply_taxes().
SPREAD_SCALE = 1.0


def spread_for_ticker(ticker: str) -> float:
    """Voller Geld-Brief-Spread (relativ zur Mitte) für die Variante `ticker`,
    schon mit SPREAD_SCALE multipliziert. Fehlt die Angabe (oder ist `ticker`
    keine Variante, z.B. "CASH"), gilt 0."""
    return SPREAD_SCALE * RISK_TICKERS.get(ticker, {}).get("spread", 0.0)


# Vorabpauschale (jährliche Vorwegbesteuerung thesaurierender/nicht
# ausschüttender Fondsanteile, siehe
# https://de.wikipedia.org/wiki/Vorabpauschale).
BASISZINS = 0.025
APPLY_VORABPAUSCHALE = True


# ----------------------------------------------------------------------
# Kursdaten laden (Download und Vollständigkeitsprüfung gegen den echten
# Börsenkalender kommen aus yf_data.py, siehe dortiger Docstring)
# ----------------------------------------------------------------------

# Anker-Startdatum, um die komplette verfügbare Historie eines Tickers anzufragen. yf_data.py erkennt
# beim Download automatisch, ab wann ein Ticker tatsächlich notiert
# (Börsengang/Listing, über Yahoo-Metadaten bzw. ersatzweise über die
# gelieferten Daten selbst erkannt - siehe dortiger Docstring), sodass
# ein so früh gewähltes Ankerdatum nicht fälschlich als fehlende Daten
# gewertet wird.
EARLIEST_POSSIBLE_DATE = pd.Timestamp("1990-01-01")


def get_adj_close(ticker: str, query_end_date: pd.Timestamp) -> pd.Series:
    """Lädt die komplette verfügbare Kurshistorie eines Tickers (siehe
    EARLIEST_POSSIBLE_DATE) über das gemeinsame Modul, inklusive
    Vollständigkeitsprüfung gegen den echten Börsenkalender und des
    Sicherheits-Cutoffs für einen ggf. noch unfertigen heutigen Kurs
    (beides läuft vollständig innerhalb von load_prices() in
    yf_data.py, siehe dortiger Docstring)."""
    series, dropped = load_prices(ticker, EARLIEST_POSSIBLE_DATE, query_end_date)
    if dropped:
        print(f"[info]     {ticker}: heutiger Kurs verworfen (Sicherheitsregel, siehe "
              f"yf_data.py), letzter berücksichtigter Handelstag: "
              f"{series.index[-1].date()}")
    return series


# ----------------------------------------------------------------------
# Währungsumrechnung (siehe Modul-Docstring "Währungsumrechnung")
# ----------------------------------------------------------------------
def load_eur_per_usd(query_end_date: pd.Timestamp) -> pd.Series:
    """Lädt die EUR/USD-Wechselkurshistorie über denselben Weg wie alle
    anderen Kursdaten (get_adj_close()/yf_data.py, siehe dortiger
    Docstring sowie den Caveat zum FX-Kalender im Modul-Docstring
    dieses Skripts). FX_TICKER = "EUR=X" notiert EUR JE 1 USD - eine
    Kursreihe in USD wird durch Multiplikation mit diesem Faktor nach
    EUR umgerechnet (siehe convert_to_eur())."""
    series = get_adj_close(FX_TICKER, query_end_date)
    series, glitches = clean_fx_spikes(series)
    if glitches:
        print(f"[info]     {FX_TICKER}: {len(glitches)} eintägige(r) Ausreißer bereinigt: "
              + ", ".join(f"{d.date()} ({r1:+.1%}/{r2:+.1%})" for d, r1, r2 in glitches))
    # Plausibilitäts-Check statt eines harten Asserts: EUR/USD lag seit
    # Einführung des Euro durchgehend zwischen 0.6 und 1.3 - ein Wert
    # weit außerhalb würde auf eine vertauschte Umrechnungsrichtung
    # (z.B. versehentlich USD je EUR statt EUR je USD) oder auf
    # fehlerhafte Kursdaten hindeuten.
    implausible = ~series.between(0.4, 2.0)
    if implausible.any():
        bad = series.loc[implausible]
        print(f"[warn]     {FX_TICKER}: {len(bad)} Kurswert(e) außerhalb des "
              f"plausiblen Bereichs [0.4, 2.0] - bitte Wechselkurs-Daten prüfen "
              f"(z.B. {bad.index[0].date()}: {bad.iloc[0]:.4f}).")
    return series


# ----------------------------------------------------------------------
# Synthetisches S&P 500 (SPY in EUR), zeitvariable Kosten
# ----------------------------------------------------------------------
FX_SPIKE_THRESHOLD = 0.04        # eintägige Bewegung, die am Folgetag zurückläuft
FX_SPIKE_THRESHOLD_DAY8 = 0.02   # am 8. eines Monats (bekannte Yahoo-Fehler 2008) strenger


def clean_fx_spikes(fx: pd.Series) -> tuple[pd.Series, list[tuple]]:
    """Ersetzt eintägige Ausreißer des Wechselkurses durch den Vortageswert. Ein
    Ausreißer ist eine Tagesbewegung > FX_SPIKE_THRESHOLD (am 8. eines Monats
    schon > FX_SPIKE_THRESHOLD_DAY8, dort liefert Yahoo 2008 mehrfach Fehlwerte),
    die am Folgetag zu mehr als der Hälfte zurückläuft. Rückgabe: (bereinigte
    Reihe, [(Datum, Bewegung, Gegenbewegung)])."""
    values = fx.to_numpy(dtype=float).copy()
    found = []
    for i in range(1, len(values) - 1):
        r1 = values[i] / values[i - 1] - 1.0
        thr = FX_SPIKE_THRESHOLD_DAY8 if fx.index[i].day == 8 else FX_SPIKE_THRESHOLD
        if abs(r1) <= thr:
            continue
        r2 = values[i + 1] / values[i] - 1.0
        if r1 * r2 < 0 and abs(values[i + 1] / values[i - 1] - 1.0) < 0.5 * abs(r1):
            found.append((fx.index[i], r1, r2))
            values[i] = values[i - 1]
    return pd.Series(values, index=fx.index), found


def build_synthetic_eur(spy_usd: pd.Series, eur_per_usd: pd.Series, leverage: float,
                        fixed_cost_pa: float, rate_pct: pd.Series | None,
                        lever_currency: str) -> tuple[pd.Series, str]:
    """Synthetisches S&P 500 in EUR auf dem SPY-Kalender (US-Schluss, daher ohne
    Xetra-Zeitversatz). Tagesrendite = Brutto - (fixe Kosten + (Hebel-1) * Zins(t)) / 252.
    Brutto bei Hebel in EUR: L * ((1+r_SPY)(1+r_FX) - 1); bei Hebel in USD:
    (1 + L * r_SPY)(1 + r_FX) - 1 (Wechselkurs 1x). `rate_pct`: Zins in Prozent p.a.
    (nötig bei Hebel != 1). Rückgabe: (Reihe, Beschreibung)."""
    if lever_currency not in ("EUR", "USD"):
        raise ValueError(f"lever_currency muss 'EUR' oder 'USD' sein, nicht {lever_currency!r}.")
    if leverage == 0:
        raise ValueError("leverage darf nicht 0 sein.")
    spy = spy_usd.loc[spy_usd.index >= eur_per_usd.index.min()]
    fx = eur_per_usd.reindex(spy.index, method="ffill")
    if fx.isna().any():
        raise ValueError("build_synthetic_eur: Wechselkurs-Lücke am Anfang der Reihe.")
    r_spy = spy.pct_change().fillna(0.0)
    r_fx = fx.pct_change().fillna(0.0)
    if lever_currency == "EUR":
        gross = leverage * ((1.0 + r_spy) * (1.0 + r_fx) - 1.0)
    else:
        gross = (1.0 + leverage * r_spy) * (1.0 + r_fx) - 1.0
    cost = pd.Series(fixed_cost_pa / TRADING_DAYS_PER_YEAR, index=spy.index)
    avg_rate_text = ""
    if leverage != 1.0:
        if rate_pct is None:
            raise ValueError("build_synthetic_eur: Zinsreihe fehlt (Hebel != 1).")
        rate = rate_pct.reindex(spy.index, method="ffill")
        if rate.isna().any():
            raise ValueError(f"Zinsreihe beginnt erst {rate_pct.index.min().date()} - nach SPY-Start.")
        funding = (leverage - 1.0) * rate / 100.0
        cost = cost + funding / TRADING_DAYS_PER_YEAR
        avg_rate_text = f", Finanzierung im Schnitt {funding.mean() * 100:+.2f}% p.a."
    r = (gross - cost).where(spy.index != spy.index[0], 0.0)
    series = (1.0 + r).cumprod() * float(spy.iloc[0] * fx.iloc[0])
    desc = (f"{leverage:g}x" + (f" Hebel in {lever_currency}" if leverage != 1.0 else "")
            + f", fixe Kosten {fixed_cost_pa * 100:.2f}% p.a." + avg_rate_text
            + f", {series.index[0].date()} bis {series.index[-1].date()}")
    return series, desc


def tagesgeld_net_daily_return(calendar: pd.DatetimeIndex, rate_pct: pd.Series | None,
                               abschlag: float = TAGESGELD_ABSCHLAG) -> pd.Series | None:
    """Tägliche Tagesgeld-Rendite NACH Abgeltungsteuer auf `calendar`:
    max(Zins/100 - abschlag, 0) / 252 * (1 - Steuersatz). `rate_pct`: Zinsreihe in
    Prozent p.a. (vorwärtsgefüllt). None -> None (Cash mit 0 %). Ohne
    APPLY_CAPITAL_GAINS_TAX entfällt der Steuerabzug."""
    if rate_pct is None:
        return None
    rate = rate_pct.reindex(calendar, method="ffill")
    if rate.isna().any():
        raise ValueError(f"Tagesgeld-Zinsreihe beginnt erst {rate_pct.index.min().date()} "
                         f"(Kalender ab {calendar[0].date()}).")
    gross = (rate / 100.0 - abschlag).clip(lower=0.0) / TRADING_DAYS_PER_YEAR
    tax = ABGELTUNGSTEUER_BASISSATZ if APPLY_CAPITAL_GAINS_TAX else 0.0
    return gross * (1.0 - tax)


# ----------------------------------------------------------------------
# Momentum-Berechnung (in Handelstagen, für das Canary-Asset)
# ----------------------------------------------------------------------
def momentum_13612u_trading_days(adj_close: pd.Series,
                                  lookback_days: tuple[int, ...]) -> pd.Series:
    """
    13612U-artiger Momentum-Score, in HANDELSTAGEN (statt kalendarisch)
    berechnet, für jeden Handelstag t in adj_close.index:
        Score(t) = 1/N * sum_n [ P(t)/P(t - n Handelstage) - 1 ]
    P(t - n Handelstage) ist dabei einfach der um n Zeilen zurück-
    liegende Kurs in adj_close (Series.shift(n)) - es wird also direkt
    in der eigenen Handelstage-Historie des Assets gezählt, ohne über
    ein Kalenderdatum zu gehen. Das vermeidet, dass durch Nichthandels-
    tage (Wochenenden, Feiertage) derselbe Vergleichskurs auf mehrere
    aufeinanderfolgende Handelstage fällt.

    Für die ersten `max(lookback_days)` Handelstage der Historie liefert
    das (mangels ausreichender Vorlaufzeit) NaN - das ist beabsichtigt
    und wird über first_valid_date in backtest_tip_canary() behandelt.
    """
    components = [adj_close / adj_close.shift(n) - 1.0 for n in lookback_days]
    score = sum(components) / len(components)
    return score


# ----------------------------------------------------------------------
# Whipsaw-/Bestätigungsfilter
# ----------------------------------------------------------------------
def raw_target_position(canary_mom: pd.Series) -> pd.Series:
    """Tägliches Rohsignal (ohne Bestätigungsfilter) der TIP-Canary-
    Makro-Strategie:
      Score(Canary) > 0  -> "RISK"
      sonst              -> "DEFENSIVE"
    "DEFENSIVE" bedeutet in diesem Script immer Tagesgeld (siehe
    backtest_tip_canary())."""
    risk_on = canary_mom > 0
    position = pd.Series("DEFENSIVE", index=canary_mom.index, dtype=object)
    position[risk_on] = "RISK"
    return position


def apply_confirmation_filter(raw_position: pd.Series, a: int, b: int) -> pd.Series:
    """
    Whipsaw-Filter mit getrennten Bestätigungsfenstern je
    Wechselrichtung (siehe Modul-Docstring "Rebalancing / Whipsaw-
    Filter"): ein neuer Zustand wird erst übernommen, wenn das rohe
    Tagessignal mehrere aufeinanderfolgende Handelstage denselben
    neuen Wert anzeigt - wie viele, hängt vom ZIEL-Wert `s` ab:
      s == "RISK"   -> `b` Handelstage nötig (Wechsel HIN ZU Risk)
      s != "RISK"   -> `a` Handelstage nötig (Wechsel WEG von Risk)
    a=1 bzw. b=1 bedeutet: dieser Wechsel wird sofort übernommen
    (keine Verzögerung).
    """
    if raw_position.empty:
        return raw_position.copy()

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

    return pd.Series(confirmed, index=raw_position.index)


# ----------------------------------------------------------------------
# Besteuerung: Kapitalertragsteuer bei Wechsel + jährliche Vorabpauschale
# ----------------------------------------------------------------------
def apply_taxes(daily_position: pd.Series,
                 returns_by_position: dict[str, pd.Series],
                 tax_rate_by_position: dict[str, float],
                 vorabpauschale_faktor_by_position: dict[str, float],
                 basiszins: float = BASISZINS,
                 apply_capital_gains_tax: bool = APPLY_CAPITAL_GAINS_TAX,
                 apply_vorabpauschale: bool = APPLY_VORABPAUSCHALE,
                 spread_by_position: dict[str, float] | None = None,
                 cash_return: pd.Series | None = None,
                 ) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Berechnet die Wertentwicklung NACH deutscher Besteuerung für eine
    beliebige, täglich gehaltene Position - egal wie viele
    unterschiedliche Wertpapier-Positionen `returns_by_position` enthält
    (hier: RISK / DEFENSIVE). Jeder Wechsel zwischen zwei
    unterschiedlichen Keys aus `returns_by_position` wird als Verkauf +
    Neukauf behandelt und entsprechend besteuert.

    `tax_rate_by_position`/`vorabpauschale_faktor_by_position` ordnen
    JEDER Position (denselben Keys wie `returns_by_position`) ihren
    EIGENEN, individuellen Steuersatz bzw. Vorabpauschale-Faktor zu
    (siehe capital_gains_tax_rate_for_ticker()/
    vorabpauschale_faktor_for_ticker()) - unterschiedliche Ticker haben
    nach § 20 InvStG unterschiedliche Teilfreistellungssätze (z.B. 30%
    für einen Aktienfonds, 0% für einen Renten-/Geldmarkt-/
    Devisenfonds), die Steuerlast ist also NICHT für jede gehaltene
    Position gleich hoch.

    Berücksichtigt werden zwei Steuerarten:

    1) Kapitalertragsteuer bei Verkauf (Positionswechsel):
       Steuerpflichtig ist ausschließlich der Verkauf eines
       Wertpapiers (jede Position, die als Key in
       `returns_by_position` vorkommt). Der Wechsel IN eine Position
       (Kauf) sowie das Halten von Cash (jede Position, die NICHT in
       `returns_by_position` enthalten ist, z.B. "CASH") lösen keine
       Steuer aus. "Gewinn" = Depotwert beim Wechsel minus Depotwert
       beim letzten Kauf/Wechsel in diese Position (inkl. ggf. bereits
       versteuerter Vorabpauschale-Beträge, siehe unten). Ein finaler
       Verkauf am Ende des Backtest-Zeitraums wird NICHT besteuert
       (Annahme: Position wird darüber hinaus weitergehalten).

    2) Vorabpauschale (siehe https://de.wikipedia.org/wiki/Vorabpauschale):
       Wird fällig für die Wertpapier-Position, die am Jahresende
       gehalten wird (Stichtag: Bestand am Jahresende, hier der letzte
       Handelstag des Jahres in den Kursdaten). Die Steuer wird
       vereinfachend an diesem Tag NACH der Tagesrendite im SELBEN Jahr
       abgezogen (real am ersten Werktag des Folgejahres), sodass sie
       in der Jahresrendite des Jahres steht, auf das sie sich bezieht. Vereinfachte Berechnung:
           Basisertrag = Wert zu Beginn der Haltedauer im betroffenen
                         Jahr * Basiszins * (1 - Teilfreistellung dieser
                         Position) * (volle Haltemonate im Jahr / 12)
           Vorabpauschale = max(0, min(Basisertrag, tatsächlicher
                                        Wertzuwachs im Jahr))
       Die Vorabpauschale wird mit demselben, positionsindividuellen
       Steuersatz besteuert wie reguläre Kapitalerträge und mindert
       direkt den Depotwert. Der besteuerte Betrag erhöht gleichzeitig
       die Anschaffungskosten (cost_basis), damit er bei einem
       späteren Verkauf/Wechsel nicht nochmals versteuert wird.

       Vereinfachungen ggü. der exakten gesetzlichen Berechnung:
         - Der Basiszins wird konstant mit `basiszins` angenommen.
         - Volle Haltemonate werden näherungsweise so gezählt, dass der
           Monat eines unterjährigen Kaufs bereits als voller Monat
           zählt.
         - Zwischenzeitliche Ausschüttungen werden nicht separat
           berücksichtigt.
         - Kirchensteuer und Sparer-Pauschbetrag bleiben unberücksichtigt.
       - Verluste werden NICHT mit künftigen Gewinnen verrechnet.

    3) Spread (optional, `spread_by_position`): voller Geld-Brief-Spread je
       Position (relativ zur Mitte). Bei JEDEM Wechsel fällt die Hälfte des
       Spreads der verkauften (Verkauf zum Geldkurs) und die Hälfte des
       Spreads der gekauften Position an (Kauf zum Briefkurs); Cash und
       nicht eingetragene Positionen kosten nichts. Steuerlich wirkt er wie
       real: Der Verkaufsabschlag mindert den Veräußerungserlös VOR der
       Gewinnberechnung, der Kaufaufschlag erhöht nicht die Anschaffungs-
       kosten (diese bleiben der gezahlte Betrag), sondern mindert den
       Mittelwert der neuen Position und damit späteren steuerpflichtigen
       Gewinn. Der Anfangskauf wird nicht belastet (wirkt auf Strategie und
       Buy & Hold gleich, und die Kurven werden ohnehin auf den ersten Tag
       normiert). Ein Verkauf am Ende des Zeitraums kostet nichts.

    Parameter:
      daily_position      - Serie mit der je Handelstag gehaltenen
                             Position (z.B. "RISK"/"DEFENSIVE"/"CASH").
      returns_by_position - dict: Positionswert -> zugehörige
                             Tagesrendite-Serie.
      spread_by_position  - dict: Positionswert -> voller Spread (optional).
      cash_return         - Serie: tägliche Tagesgeld-Rendite NACH Steuer, die an
                             Tagen mit einer Position außerhalb von
                             `returns_by_position` (CASH) gutgeschrieben wird
                             (optional, sonst 0). Die Zinsen sind damit schon
                             versteuert; sie lösen keine weitere Steuer aus.

    Rückgabe:
      equity_after_tax        - tägliche Wertentwicklung nach Steuern
                                 (Start = 1.0)
      capital_gains_tax_paid  - am jeweiligen Tag gezahlte
                                 Kapitalertragsteuer bei Wechsel/Verkauf
      vorabpauschale_tax_paid - am jeweiligen Tag gezahlte Steuer auf
                                 die Vorabpauschale
      spread_cost_paid        - am jeweiligen Tag durch den Spread
                                 verlorener Betrag (Wechsel)
    """
    dates = daily_position.index
    positions = daily_position.to_numpy()
    years = dates.year.to_numpy()

    # Tagesrenditen je Position als Array auf dem Kalender der Position.
    # Fehlt ein Datum in der Renditeserie, wird wie bei einem direkten
    # Index-Zugriff ein KeyError ausgelöst.
    return_arrays: dict[str, np.ndarray] = {}
    for key, ret in returns_by_position.items():
        idx = ret.index.get_indexer(dates)
        used = positions == key
        if (idx[used] < 0).any():
            raise KeyError(dates[used][idx[used] < 0][0])
        return_arrays[key] = ret.to_numpy(dtype=float)[np.maximum(idx, 0)]

    cash_array = (np.zeros(len(dates)) if cash_return is None
                  else cash_return.reindex(dates).fillna(0.0).to_numpy(dtype=float))
    equity_after_tax = np.empty(len(dates))
    capital_gains_tax_paid = np.zeros(len(dates))
    vorabpauschale_tax_paid = np.zeros(len(dates))
    spread_cost_paid = np.zeros(len(dates))
    half_spread = {k: 0.5 * v for k, v in (spread_by_position or {}).items()}

    current_equity = 1.0
    cost_basis = 1.0
    purchase_date = dates[0]
    value_at_year_start = 1.0
    prev_position = None

    for i, date in enumerate(dates):
        pos = positions[i]

        # --- 2) Positionswechsel: Verkaufsabschlag (Spread), Kapitalertrag-
        #     steuer auf Gewinn seit letztem Kauf/Wechsel, Kaufaufschlag ---
        if prev_position is not None and pos != prev_position:
            if prev_position in returns_by_position:
                fee = current_equity * half_spread.get(prev_position, 0.0)
                current_equity -= fee
                spread_cost_paid[i] += fee
                if apply_capital_gains_tax:
                    gain = current_equity - cost_basis
                    if gain > 0:
                        tax = gain * tax_rate_by_position[prev_position]
                        current_equity -= tax
                        capital_gains_tax_paid[i] = tax
            cost_basis = current_equity            # gezahlter Betrag
            purchase_date = date
            if pos in returns_by_position:
                fee = current_equity * half_spread.get(pos, 0.0)
                current_equity -= fee
                spread_cost_paid[i] += fee
            value_at_year_start = current_equity   # Wert zur Mitte

        # --- 3) Tagesrendite der aktuell gehaltenen Position anwenden ---
        r = return_arrays[pos][i] if pos in return_arrays else cash_array[i]
        current_equity *= (1.0 + r)

        # --- 4) Jahresende (letzter Handelstag des Jahres, nach der
        #     Tagesrendite): Vorabpauschale auf die an diesem Tag gehaltene
        #     Wertpapier-Position. Vereinfachend wird sie im SELBEN Jahr
        #     abgezogen (real gilt sie am ersten Werktag des Folgejahres als
        #     zugeflossen), damit die Steuer in der Jahresrendite landet, auf
        #     die sie sich bezieht. Der letzte Tag der Kursreihe ist kein
        #     Jahresende (das Jahr läuft noch). ---
        if (apply_vorabpauschale and i < len(dates) - 1
                and years[i + 1] != years[i]
                and pos in returns_by_position):
            start_of_year = pd.Timestamp(year=int(years[i]), month=1, day=1)
            period_start = max(purchase_date, start_of_year)
            full_months_held = min(max(12 - period_start.month + 1, 0), 12)

            basisertrag = (value_at_year_start * basiszins
                           * vorabpauschale_faktor_by_position[pos]
                           * full_months_held / 12.0)
            wertzuwachs = current_equity - value_at_year_start
            vorabpauschale = max(0.0, min(basisertrag, wertzuwachs))

            if vorabpauschale > 0:
                tax = vorabpauschale * tax_rate_by_position[pos]
                current_equity -= tax
                cost_basis += vorabpauschale
                vorabpauschale_tax_paid[i] = tax

            value_at_year_start = current_equity

        equity_after_tax[i] = current_equity
        prev_position = pos

    return (pd.Series(equity_after_tax, index=dates),
            pd.Series(capital_gains_tax_paid, index=dates),
            pd.Series(vorabpauschale_tax_paid, index=dates),
            pd.Series(spread_cost_paid, index=dates))


# ----------------------------------------------------------------------
# Backtest der TIP-Canary-Strategie (ein einzelnes, festes Risk-Asset)
# ----------------------------------------------------------------------
def trend_signal_position(trend_adj: pd.Series, sma_days: int, a: int, b: int) -> pd.Series:
    """SMA-Signal auf dem EIGENEN Kalender der Signalquelle (^NDX): Schlusskurs
    STRIKT ÜBER dem `sma_days`-Tage-SMA (inkl. des aktuellen Schlusskurses) ->
    "RISK", sonst "DEFENSIVE" (Gleichstand wie TIP-Score = 0: defensiv), danach
    der asymmetrische Whipsaw-Filter `a`/`b` (siehe apply_confirmation_filter();
    a: weg von Risk, b: hin zu Risk). Tage ohne SMA-Wert entfallen."""
    sma = trend_adj.rolling(sma_days).mean()
    valid = sma.notna()
    raw = pd.Series(np.where(trend_adj > sma, "RISK", "DEFENSIVE"),
                    index=trend_adj.index, dtype=object)[valid]
    return apply_confirmation_filter(raw, a, b)


def signal_to_master_calendar(signal_position: pd.Series,
                               trading_calendar: pd.DatetimeIndex) -> pd.Series:
    """Legt eine bestätigte Signalposition (auf eigenem Kalender) auf den
    Master-Kalender: Zeile d erhält die Position des letzten Signaltags
    STRIKT VOR d (Signal vom Schlusskurs t wirkt ab der nächsten Zeile). Vor
    dem ersten Signaltag gilt "DEFENSIVE"."""
    last_idx = signal_position.index.searchsorted(trading_calendar, side="left") - 1
    values = signal_position.to_numpy(dtype=object)
    macro = np.where(last_idx >= 0, values[np.maximum(last_idx, 0)], "DEFENSIVE")
    return pd.Series(macro, index=trading_calendar, dtype=object)


def combine_macro(tip_state: pd.Series, trend_state: pd.Series, mode: str) -> pd.Series:
    """Kombiniert zwei RISK/DEFENSIVE-Serien gleichen Index je Strategie:
    "tip" nur TIP, "sma" nur SMA, "hybrid" Risk, wenn mindestens eines Risk meldet."""
    if mode == "tip":
        return tip_state
    if mode == "sma":
        return trend_state
    if mode == "hybrid":
        risk = (tip_state == "RISK") | (trend_state == "RISK")
        return pd.Series(np.where(risk, "RISK", "DEFENSIVE"), index=tip_state.index, dtype=object)
    raise ValueError(f"Unbekannte Strategie: {mode!r}")


def backtest_tip_canary(
    canary_adj: pd.Series,
    risky_adj: pd.Series,
    trend_adj: pd.Series,
    mode: str = "hybrid",
) -> dict:
    """
    Bestimmt für EINE Risk-Asset-Variante die täglich gehaltene Position:
    "RISK" (synthetisches Risk-Asset) oder "CASH" (Tagesgeld). Die
    Bestätigungsfenster sind CONFIRMATION_A/B (TIP) bzw.
    TREND_CONFIRMATION_A/B (SMA). `risky_adj` wird in EUR erwartet; sein
    Kalender ist der Master-Kalender (siehe Modul-Docstring "Kalender").

    Ablauf:
      1) Auf dem Handelskalender von `canary_adj`: 13612U-Score ->
         Rohsignal (Score > 0 -> RISK, sonst DEFENSIVE) -> Whipsaw-Filter
         -> bestätigte Signalposition (RISK/DEFENSIVE).
      2) Übertragung beider Signale (TIP, SMA) auf den Master-Kalender:
         jede Zeile d erhält die bestätigte Position des letzten
         Signaltags STRENG VOR d. Vor dem ersten Signaltag gilt DEFENSIVE.
      3) `mode` wählt TIP allein, SMA allein oder den Hybrid (siehe
         combine_macro()). RISK bleibt RISK, DEFENSIVE wird zu CASH.

    Rückgabe: dict mit
      daily_position       - gehaltene Position je Zeile des Master-Kalenders
                             (RISK oder CASH); bestimmt die Rendite dieser Zeile
      returns_by_position  - Tagesrenditen je Position für apply_taxes()
                             (nur RISK; CASH ist nicht enthalten)
      first_valid_date     - erster Tag mit vollständigem Signal
      tip_macro/trend_macro - die beiden Signale auf dem Master-Kalender
    """
    trading_calendar = risky_adj.index

    # --- Signal auf dem EIGENEN Kalender des Canary-Assets (TIP) ---
    # Momentum, Rohsignal und Whipsaw-Filter laufen ausschließlich auf den
    # Handelstagen von TIP - unabhängig vom Kalender des Risk-Assets.
    canary_mom = momentum_13612u_trading_days(canary_adj, LOOKBACK_DAYS_CANARY)
    signal_start = canary_mom.first_valid_index()
    if signal_start is None:
        raise ValueError("Zu wenig gemeinsame Historie für die gewählten Lookbacks.")
    canary_mom_signal = canary_mom.loc[canary_mom.index >= signal_start]
    raw_position = raw_target_position(canary_mom_signal)
    signal_position = apply_confirmation_filter(raw_position, CONFIRMATION_A, CONFIRMATION_B)

    # Erster Backtest-Tag: erste Zeile des Risk-Kalenders am oder nach dem
    # ersten Signaltag.
    first_idx = trading_calendar.searchsorted(signal_start)
    if first_idx >= len(trading_calendar):
        raise ValueError("Zu wenig gemeinsame Historie für die gewählten Lookbacks.")
    first_valid_date = trading_calendar[first_idx]

    # --- Übertragung auf den Ausführungskalender (Risk-Asset) ---
    # Für jede Zeile d des Risk-Kalenders gilt die bestätigte Position des
    # letzten Signaltags, der STRIKT vor d liegt (Signal vom Schlusskurs t
    # wirkt ab dem ersten Handelstag danach). Liegt t in einer Lücke des
    # Risk-Kalenders, wird zum letzten verfügbaren Kurs gewechselt. Gibt es
    # noch keinen früheren Signaltag, gilt DEFENSIVE.
    trend_signal = trend_signal_position(trend_adj, TREND_SMA_DAYS,
                                         TREND_CONFIRMATION_A, TREND_CONFIRMATION_B)
    tip_macro = signal_to_master_calendar(signal_position, trading_calendar)
    trend_macro = signal_to_master_calendar(trend_signal, trading_calendar)
    macro_daily_position = combine_macro(tip_macro, trend_macro, mode)

    # Defensiv = Tagesgeld ("CASH"); die Verzinsung steckt in apply_taxes()
    # (cash_return), "CASH" ist deshalb nicht in returns_by_position enthalten.
    daily_position = pd.Series(np.where(macro_daily_position == "RISK", "RISK", "CASH"),
                               index=trading_calendar, dtype=object)

    return {
        "daily_position": daily_position,
        "returns_by_position": {"RISK": risky_adj.pct_change().fillna(0.0)},
        "first_valid_date": first_valid_date,
        "tip_macro": tip_macro,
        "trend_macro": trend_macro,
    }


def _buy_and_hold_returns(adj_close: pd.Series, start_date: pd.Timestamp) -> pd.Series:
    """Tagesrenditen von `adj_close` ab `start_date` für die Buy & Hold-
    Rechnung. Ist start_date der allererste verfügbare Handelstag, gibt es
    keinen Vortageskurs, aus dem sich eine Rendite berechnen ließe - der erste
    Tag wird dann mit Rendite 0 behandelt (Kauf zum Schlusskurs dieses Tages,
    noch kein Wertzuwachs), statt NaN: NaN würde über die multiplikative
    Verkettung in apply_taxes() (ein einzelner, laufend multiplizierter
    Skalar - kein NaN-sicheres cumprod) die gesamte Equity-Kurve ab diesem
    Punkt auf NaN setzen."""
    returns_full = adj_close.pct_change()
    returns = returns_full.loc[returns_full.index >= start_date].copy()
    if len(returns) > 0 and pd.isna(returns.iloc[0]):
        returns.iloc[0] = 0.0
    return returns


def buy_and_hold_after_tax(adj_close: pd.Series, ticker: str,
                            start_date: pd.Timestamp) -> pd.Series:
    """Buy & Hold-Kurve NACH Steuern (Vorabpauschale zum Jahresende; da nie verkauft wird, fällt keine Kapitalertragsteuer an -
    wohl aber die jährliche Vorabpauschale, siehe apply_taxes()).
    `ticker` bestimmt die individuelle Teilfreistellung (siehe
    _teilfreistellung())."""
    returns = _buy_and_hold_returns(adj_close, start_date)
    if returns.isna().any():
        bad_dates = returns.index[returns.isna()]
        raise ValueError(
            f"buy_and_hold_after_tax: unerwartete NaN-Rendite(n) am "
            f"{', '.join(d.date().isoformat() for d in bad_dates[:5])} - Kursdaten prüfen."
        )
    daily_position = pd.Series("RISK", index=returns.index)
    equity_after_tax, _, _, _ = apply_taxes(
        daily_position, {"RISK": returns},
        tax_rate_by_position={"RISK": capital_gains_tax_rate_for_ticker(ticker)},
        vorabpauschale_faktor_by_position={"RISK": vorabpauschale_faktor_for_ticker(ticker)},
    )
    return equity_after_tax / equity_after_tax.iloc[0]


# ----------------------------------------------------------------------
# Performance-Kennzahlen
# ----------------------------------------------------------------------
def performance_stats(equity: pd.Series,
                       periods_per_year: int = TRADING_DAYS_PER_YEAR) -> dict[str, float]:
    returns = equity.pct_change().dropna()

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    n_years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / n_years) - 1.0 if n_years > 0 else np.nan

    ann_vol = returns.std() * np.sqrt(periods_per_year)
    ann_return = returns.mean() * periods_per_year
    sharpe = ann_return / ann_vol if ann_vol > 0 else np.nan

    # Sortino Ratio (rf=0, MAR=0): wie Sharpe, aber im Nenner nur die
    # "Downside-Volatilität" (Streuung der negativen Tagesrenditen)
    # statt der gesamten Volatilität. Positive Ausreißer nach oben
    # werden also nicht bestraft.
    downside_returns = returns.clip(upper=0.0)
    downside_dev = np.sqrt((downside_returns ** 2).mean()) * np.sqrt(periods_per_year)
    sortino = ann_return / downside_dev if downside_dev > 0 else np.nan

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = drawdown.min()

    # Ulcer Index: Wurzel aus dem mittleren QUADRIERTEN Drawdown über
    # den GESAMTEN Zeitraum (nicht nur der Tiefpunkt wie bei Max
    # Drawdown) - bestraft sowohl Tiefe als auch Dauer von
    # Drawdown-Phasen. Ein einzelner extremer Ausreißer (z.B. ein
    # Crash, den beide verglichenen Strategien gleichermaßen erwischt)
    # dominiert zwar weiterhin mit, aber viele kleinere, häufigere
    # Drawdowns schlagen sich anders als bei Max Drawdown zusätzlich in
    # der Kennzahl nieder.
    ulcer_index = np.sqrt((drawdown ** 2).mean())

    # Längste Phase unter Wasser: größter Abstand (in Kalendertagen) zwischen zwei
    # Höchstständen der Kurve - bei noch laufender Phase bis zum letzten
    # Datum. Zeigt, wie lange man maximal auf ein neues Hoch warten musste.
    is_peak = (equity >= running_max).to_numpy()
    last_peak = pd.Series(equity.index.where(is_peak), index=equity.index).ffill()
    longest_underwater_days = int((equity.index.to_series() - last_peak).dt.days.max())

    return {
        "Start": equity.index[0].date(),
        "Ende": equity.index[-1].date(),
        "Rendite": total_return,
        "CAGR": cagr,
        "Vola.": ann_vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max DD": max_dd,
        "Ulcer": ulcer_index,
        "Max UW": longest_underwater_days,
    }


def isolated_yearly_returns(daily_position: pd.Series,
                            returns_by_position: dict[str, pd.Series],
                            tax_rate_by_position: dict[str, float],
                            vorabpauschale_faktor_by_position: dict[str, float],
                            spread_by_position: dict[str, float] | None = None,
                            cash_return: pd.Series | None = None,
                            ) -> dict[int, float]:
    """Rendite je Kalenderjahr NACH Steuern, jedes Jahr ISOLIERT gerechnet:
    als hätte man erst am 1.1. des Jahres mit dem Investieren begonnen
    (Anschaffungskosten = Wert am 1.1.). Kapitalertragsteuer fällt nur auf
    Gewinne an, die seit dem 1.1. entstanden sind (Positionswechsel im Jahr);
    die Vorabpauschale des Jahres ist enthalten (Abzug am letzten Handelstag
    des Jahres, siehe apply_taxes()). Steuer auf Gewinne aus früheren Jahren
    taucht in der Jahresrendite NICHT auf - sie steckt nur in der echten
    Gesamtrendite (Differenz = "Steuerverschiebung").

    Das erste Jahr der Reihe startet mit dem Wert nach
    dem ersten Handelstag. Zur Berechnung des Vorabpauschale-Abzugs am
    Jahresende wird der erste Handelstag des Folgejahres mitgeführt."""
    dates = daily_position.index
    years = dates.year.to_numpy()
    first_year = int(years[0])
    result: dict[int, float] = {}
    for y in sorted(set(years.tolist())):
        idx = np.flatnonzero(years == y)
        first, last = int(idx[0]), int(idx[-1])
        stop = min(last + 2, len(dates))        # + erster Handelstag des Folgejahres
        pos = daily_position.iloc[first:stop]
        rets = {k: v.loc[pos.index[0]:pos.index[-1]] for k, v in returns_by_position.items()}
        eq, _, _, _ = apply_taxes(pos, rets, tax_rate_by_position, vorabpauschale_faktor_by_position,
                                  spread_by_position=spread_by_position,
                                  cash_return=cash_return)
        end_eq = float(eq.iloc[last - first])
        start_eq = float(eq.iloc[0]) if int(y) == first_year else 1.0
        result[int(y)] = end_eq / start_eq - 1.0
    return result


def buy_and_hold_yearly_returns(adj_close: pd.Series, ticker: str,
                                start_date: pd.Timestamp) -> dict[int, float]:
    """Isolierte Jahresrenditen (siehe isolated_yearly_returns()) für Buy & Hold;
    gleiche Renditebasis wie buy_and_hold_after_tax()."""
    returns = _buy_and_hold_returns(adj_close, start_date)
    daily_position = pd.Series("RISK", index=returns.index)
    return isolated_yearly_returns(
        daily_position, {"RISK": returns},
        {"RISK": capital_gains_tax_rate_for_ticker(ticker)},
        {"RISK": vorabpauschale_faktor_for_ticker(ticker)})


# Unterhalb dieser Rendite-Differenz (0,05 Prozentpunkte) gilt ein Jahr als
# Gleichstand.
TIE_TOLERANCE = 0.0005


def _signed_pct(v: float) -> str:
    """Prozent mit Vorzeichen, eine Nachkommastelle; Werte unter
    TIE_TOLERANCE im Betrag werden ohne Vorzeichen als "0.0%" gezeigt
    (kein "+0.0%"/"-0.0%" durch Rundungsrauschen)."""
    if pd.isna(v):
        return "n/a"
    return "0.0%" if abs(v) < TIE_TOLERANCE else f"{v:+.1%}"


def format_yearly_comparison_table(canary_equity: pd.Series, bh_equity: pd.Series,
                                    name: str,
                                    canary_year_returns: dict[int, float],
                                    bh_year_returns: dict[int, float]) -> str:
    """Listet pro Kalenderjahr zunächst die Rendite der Strategie
    (`name`-Rend.) und Buy&Hold (B&H-Rend.) selbst, gefolgt von deren
    DIFFERENZ (Δ Rendite = Strategie minus Buy&Hold), plus einer
    Gewinner-Spalte. Ein positives Delta ist ein Vorteil für die Strategie
    (höhere Rendite als B&H) in diesem Jahr. Die Gewinner-Spalte richtet
    sich entsprechend nach dieser Rendite-Differenz.

    GLEICHSTAND ("="): Liegt die Rendite-Differenz unter TIE_TOLERANCE
    (0,05 Prozentpunkte, also die halbe Anzeigestelle bei einer
    Nachkommastelle), gilt das Jahr als Gleichstand - Rundungs- und
    Gleitkomma-Rauschen (z.B. -0,0 %) erzeugt keinen "Gewinner".

    Eine abschließende "Gesamt"-Zeile zeigt bei Δ Rendite NICHT die
    Summe der einzelnen Jahreswerte (das wäre wegen des
    Zinseszinseffekts irreführend), sondern die Differenz der
    GESAMTZEIT-Rendite aus performance_stats() über den kompletten
    Backtest-Zeitraum - also dieselbe Gesamtzahl, die bereits weiter
    oben in der Kennzahlen-Tabelle steht. Die Rend.-Spalten zeigen in
    dieser Zeile entsprechend ebenfalls die jeweilige Gesamtrendite
    statt einer Summe der Jahresrenditen. Die Gewinner-Spalte zählt
    weiterhin, in wie vielen EINZELNEN Jahren die Strategie bzw. B&H
    vorne lag - das ist unabhängig von der (zinseszins-bereinigten)
    Gesamtbetrachtung eine eigene, ergänzende Information.

    Die Durchschnittszeile ("Durchschnitt p.a. (echt)") zeigt die jährliche
    Wachstumsrate (CAGR) der echten Gesamtrendite - nicht den Mittelwert der
    Jahreswerte. Auf einen Median wird bewusst verzichtet: bei einer
    Regime-Strategie wie dieser stammt die Outperformance typischerweise aus
    wenigen dominanten Phasen, wodurch der Median eher irreführend als
    aussagekräftig wäre.

    Die Jahreswerte (`canary_year_returns`/`bh_year_returns`, siehe
    isolated_yearly_returns()) sind ISOLIERT gerechnet (Steuerbasis jeweils
    der 1.1.); sie ergeben nicht die Gesamtrendite, und ein Erklärtext unter
    der Tabelle weist darauf hin."""
    years = sorted(set(canary_year_returns) & set(bh_year_returns))
    W = 26     # Breite der ersten Spalte (längstes Label: "Durchschnitt p.a. (echt)")

    _fmt_pct = _signed_pct

    lines = ["\nJahresweise Kennzahlen:"]
    header = (f"  {'Jahr':<{W}}"
              f"{name + '-Rend.':>14}{'B&H-Rend.':>14}"
              f"{'Δ Rendite':>16}{'Gewinner':>28}")
    lines.append(header)
    lines.append("-" * len(header))
    n_tip = n_bh = n_tie = 0
    for y in years:
        c, b = canary_year_returns[y], bh_year_returns[y]
        d_return = c - b
        if abs(d_return) < TIE_TOLERANCE:
            winner = "="
            n_tie += 1
        elif d_return > 0:
            winner = name
            n_tip += 1
        else:
            winner = "B&H"
            n_bh += 1
        lines.append(f"  {y:<{W}}"
                      f"{_fmt_pct(c):>14}{_fmt_pct(b):>14}"
                      f"{_fmt_pct(d_return):>16}"
                      f"{winner:>28}")

    # Gesamt-Zeile: Differenz der GESAMTZEIT-Rendite (siehe Docstring),
    # nicht die Summe der Jahreswerte.
    tip_total = performance_stats(canary_equity)
    bh_total = performance_stats(bh_equity)
    total_d_return = tip_total["Rendite"] - bh_total["Rendite"]

    lines.append("-" * len(header))
    lines.append(f"  {'Gesamt (echt)':<{W}}"
                  f"{_fmt_pct(tip_total['Rendite']):>14}{_fmt_pct(bh_total['Rendite']):>14}"
                  f"{_fmt_pct(total_d_return):>16}"
                  f"{f'{n_tip} {name} / {n_bh} B&H' + (f' / {n_tie} =' if n_tie else ''):>28}")

    # Durchschnitt: auf Basis der ECHTEN Gesamtrendite (geometrisch, p.a. = CAGR),
    # nicht der arithmetische Mittelwert der (isolierten) Jahreswerte.
    n_years = max((canary_equity.index[-1] - canary_equity.index[0]).days / 365.25, 1e-9)
    cagr_tip = (1.0 + tip_total["Rendite"]) ** (1.0 / n_years) - 1.0
    cagr_bh = (1.0 + bh_total["Rendite"]) ** (1.0 / n_years) - 1.0
    if years:
        lines.append(f"  {'Durchschnitt p.a. (echt)':<{W}}"
                      f"{_fmt_pct(cagr_tip):>14}{_fmt_pct(cagr_bh):>14}"
                      f"{_fmt_pct(cagr_tip - cagr_bh):>16}")
    lines.append("")
    lines.append(
        "  Die Jahreswerte sind isoliert gerechnet: Steuerbasis jeweils der 1.1. (Kapitalertragsteuer nur\n"
        "  auf Gewinne seit Jahresbeginn, Vorabpauschale des Jahres enthalten). Sie ergeben deshalb nicht\n"
        "  die Gesamtrendite. \"Gesamt (echt)\" und \"Durchschnitt p.a. (echt)\" (jährliche Wachstumsrate,\n"
        "  CAGR) beruhen auf dem durchgehenden Verlauf nach Steuern und enthalten auch die Steuer auf\n"
        "  Gewinne aus früheren Jahren.")
    return "\n".join(lines)


def signal_stats(daily_position: pd.Series) -> dict[str, float]:
    """Kennzahlen zur Signal-Nutzung: Zeitanteile im Risk-Asset und in Cash
    (Tagesgeld), gemessen an Handelstagen von `daily_position`."""
    total_days = len(daily_position)
    counts = daily_position.value_counts()
    return {
        "Zeit im Risk-Asset": counts.get("RISK", 0) / total_days if total_days else np.nan,
        "Zeit in Cash": counts.get("CASH", 0) / total_days if total_days else np.nan,
    }


def _monthly_returns(equity: pd.Series) -> pd.Series:
    """Monatsrenditen aus Monatsend-Werten der Equity-Kurve (der erste
    Monat startet beim ersten Wert der Kurve)."""
    month_end = equity.groupby(equity.index.to_period("M")).last()
    return month_end / month_end.shift(1, fill_value=equity.iloc[0]) - 1.0


def capture_ratios(strategy_equity: pd.Series, benchmark_equity: pd.Series) -> dict[str, float]:
    """Up-/Downside-Capture nach Morningstar-Methode auf Monatsbasis:
      Upside Capture   = annualisierte geometrische Rendite der Strategie
                         in den Monaten mit Benchmark-Rendite > 0, geteilt
                         durch die der Benchmark in diesen Monaten.
      Downside Capture = dasselbe für Monate mit Benchmark-Rendite < 0.
    Annualisierung: (Produkt der (1+r))^(12/n) - 1 über die n Monate.
    "Caught Downs" = Downside Capture (mitgenommener Anteil der Verluste);
    die "Missed Ups" (1 - Upside Capture) werden nicht gesondert ausgewiesen.
    Capture Ratio = Upside / Downside Capture (> 1 gut)."""
    s_ret, b_ret = _monthly_returns(strategy_equity), _monthly_returns(benchmark_equity)
    common = s_ret.index.intersection(b_ret.index)
    s_ret, b_ret = s_ret.loc[common], b_ret.loc[common]

    def _ann(r: pd.Series) -> float:
        return float((1.0 + r).prod() ** (12.0 / len(r)) - 1.0) if len(r) else np.nan

    out: dict[str, float] = {}
    for key, mask in (("up", b_ret > 0), ("down", b_ret < 0)):
        bench_ann = _ann(b_ret[mask])
        out[key] = _ann(s_ret[mask]) / bench_ann if pd.notna(bench_ann) and bench_ann != 0 else np.nan
        out[f"n_{key}"] = int(mask.sum())
    out["ratio"] = out["up"] / out["down"] if pd.notna(out["down"]) and out["down"] != 0 else np.nan
    return out


def format_stats_table(stats_by_strategy: dict[str, dict[str, float]]) -> str:
    df = pd.DataFrame(stats_by_strategy).T
    for col in ("Up-Cap", "Down-Cap"):
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.0%}" if pd.notna(x) else "n/a")
    fmt_cols = ["Rendite", "CAGR", "Vola.", "Max DD", "Ulcer"]
    for col in fmt_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "n/a")
    if "Max UW" in df.columns:
        df["Max UW"] = df["Max UW"].apply(lambda x: f"{x:d}" if pd.notna(x) else "n/a")
    for col in ("Sharpe", "Sortino"):
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "n/a")
    if "Wechsel" in df.columns:
        df["Wechsel"] = df["Wechsel"].apply(lambda x: f"{int(x):d}" if pd.notna(x) else "n/a")
    if "Ø/Jahr" in df.columns:
        df["Ø/Jahr"] = df["Ø/Jahr"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "n/a")
    return "\n" + df.to_string()


# ----------------------------------------------------------------------
# Backtest-Lauf (festes Risk-Asset)
# ----------------------------------------------------------------------
def run_single_backtest(canary_adj: pd.Series,
                         risky_adj: pd.Series,
                         risky_ticker: str,
                         trend_adj: pd.Series,
                         mode: str = "hybrid",
                         cash_net_return: pd.Series | None = None) -> dict:
    """Führt einen kompletten Backtest (inkl. Steuern) für ein festes
    Risk-Asset durch und liefert Kennzahlen + Equity-Kurve NACH Steuern
    zurück. `risky_ticker` ist der Varianten-Name (Schlüssel in
    RISK_TICKERS) und bestimmt Teilfreistellung und Spread."""
    result = backtest_tip_canary(canary_adj, risky_adj, trend_adj=trend_adj, mode=mode)

    tax_rate_by_position = {"RISK": capital_gains_tax_rate_for_ticker(risky_ticker)}
    vorabpauschale_faktor_by_position = {"RISK": vorabpauschale_faktor_for_ticker(risky_ticker)}

    start = result["first_valid_date"]

    # Steuern erst AB `start` simulieren (wie Buy & Hold, das ebenfalls am
    # Starttag mit Anschaffungskosten = Startwert beginnt). Würde die
    # Strategie schon vorher gehalten (z.B. über das SMA-Signal vor dem ersten
    # TIP-Signal), flössen Vorabpauschale und Anschaffungskosten aus dieser
    # Vorlaufzeit verzerrend in den Vergleich ein.
    daily_position_from_start = result["daily_position"].loc[result["daily_position"].index >= start]
    returns_from_start = {label: ret.loc[ret.index >= start]
                          for label, ret in result["returns_by_position"].items()}
    spread_by_position = {"RISK": spread_for_ticker(risky_ticker)}
    equity_after_tax, capgains_tax, vorab_tax, spread_cost = apply_taxes(
        daily_position_from_start, returns_from_start,
        tax_rate_by_position=tax_rate_by_position,
        vorabpauschale_faktor_by_position=vorabpauschale_faktor_by_position,
        spread_by_position=spread_by_position,
        cash_return=cash_net_return,
    )
    equity_after_tax = equity_after_tax / equity_after_tax.iloc[0]

    perf = performance_stats(equity_after_tax)
    sig = signal_stats(daily_position_from_start)

    # Wechsel zwischen Risk-Asset und Tagesgeld, gezählt auf der tatsächlich
    # gehaltenen Position ab `start`.
    in_risk = daily_position_from_start == "RISK"
    n_switches = max(int((in_risk != in_risk.shift(1)).sum() - 1), 0)
    span_years = (daily_position_from_start.index[-1] - daily_position_from_start.index[0]).days / 365.25
    switches_per_year = n_switches / span_years if span_years > 0 else np.nan

    return {
        "switches": n_switches,
        "switches_per_year": switches_per_year,
        "equity_after_tax": equity_after_tax,
        "perf": perf,
        "sig": sig,
        "kapitalertragsteuer_kumuliert": capgains_tax.sum(),
        "vorabpauschale_steuer_kumuliert": vorab_tax.sum(),
        "spread_kumuliert": spread_cost.sum(),
        "tip_macro": result["tip_macro"].loc[result["tip_macro"].index >= start],
        "trend_macro": result["trend_macro"].loc[result["trend_macro"].index >= start],
        "daily_position": daily_position_from_start,
        "common_start_used": start,
        "tax_inputs": {
            "daily_position": daily_position_from_start,
            "returns_by_position": returns_from_start,
            "tax_rate_by_position": tax_rate_by_position,
            "vorabpauschale_faktor_by_position": vorabpauschale_faktor_by_position,
            "spread_by_position": spread_by_position,
            "cash_return": cash_net_return,
        },
    }


def format_extra_metrics(r: dict, capture: dict[str, float] | None = None) -> str:
    """Baut die Kennzahlen der Strategie, die über den reinen Rendite-/
    Risiko-Vergleich hinausgehen (Zeitanteile je Regime, Anzahl Wechsel,
    kumulierte Steuern) als eigenen Textblock - diese Werte haben für eine
    reine Buy&Hold-Position keine sinnvolle Entsprechung (die hält immer zu
    100% das Risk-Asset, ohne Wechsel) und werden deshalb separat von der
    Gesamtzeit-Vergleichstabelle ausgewiesen. "Zeit in Cash" ist der
    Zeitanteil im Tagesgeld (siehe signal_stats())."""
    sig = r["sig"]

    def _pct(v: float) -> str:
        return f"{v:.1%}" if pd.notna(v) else "n/a"

    # Feste Label-Spaltenbreite fuer die ganze Tabelle, damit die
    # Prozent-/Zahlenwerte immer in derselben Spalte stehen.
    LABEL_WIDTH = 40

    def _row(label: str, value: str, indent: int = 2) -> str:
        prefix = " " * indent + label
        return f"{prefix:<{LABEL_WIDTH}}{value:>8}"

    share_risk = sig["Zeit im Risk-Asset"]
    lines = ["\nZusätzliche Kennzahlen:",
             _row("Zeit im Risk-Asset:", _pct(share_risk))]
    if pd.notna(share_risk) and share_risk > 0:
        lines.append(_row("davon synthetisch:", _pct(share_risk), indent=4))
    lines += [_row("Zeit in Cash:", _pct(sig['Zeit in Cash'])),
              _row("Wechsel (gesamt):", str(r['switches'])),
              _row("Wechsel pro Jahr (Ø):", f"{r['switches_per_year']:.1f}"),
              _row("Kapitalertragsteuer (kum.):", f"{r['kapitalertragsteuer_kumuliert']:.4f}"),
              _row("Vorabpauschale-Steuer (kum.):", f"{r['vorabpauschale_steuer_kumuliert']:.4f}"),
              _row("Spread-Kosten (kum.):", f"{r['spread_kumuliert']:.4f}")]
    if capture is not None:
        lines += ["\nCapture-Kennzahlen gegen Buy & Hold (monatlich, Morningstar-Methode):",
                  _row("Upside Capture:", _pct(capture['up'])),
                  _row("Downside Capture:", _pct(capture['down'])),
                  _row("Capture Ratio:", f"{capture['ratio']:.2f}"),
                  _row("Monate (Up / Down):", f"{capture['n_up']} / {capture['n_down']}")]
    return "\n".join(lines)


def identify_position_episodes(daily_position: pd.Series, target: str) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Zerlegt `daily_position` in zusammenhängende Zeitfenster
    ("Phasen"/"Episoden"), in denen der Wert durchgehend `target` war
    (z.B. alle am Stück gehaltenen DEFENSIVE-Phasen). Gibt eine Liste
    von (Anfang, Ende)-Tupeln zurück (jeweils inklusive, chronologisch
    sortiert). Eine einzelne isoliert gehaltene Phase (ein Tag) ergibt
    ein Tupel mit identischem Anfang und Ende."""
    mask = daily_position == target
    if not mask.any():
        return []
    # Jede Änderung von mask (True<->False) beginnt eine neue Gruppe -
    # cumsum darüber liefert eine fortlaufende Gruppen-ID je Tag.
    group_id = (mask != mask.shift()).cumsum()
    episodes = []
    for _, dates in daily_position.index[mask.values].to_series().groupby(group_id[mask]):
        episodes.append((dates.iloc[0], dates.iloc[-1]))
    return episodes


def _defensive_phase_rows(risky_adj: pd.Series,
                           daily_position: pd.Series,
                           risk_spread: float = 0.0,
                           cash_net_return: pd.Series | None = None) -> list[dict]:
    """Baut die rohe, chronologisch sortierte Liste der Cash-Phasen (Start,
    Ende, Dauer, Rendite des Tagesgelds sowie die Rendite des Risk-Assets in
    genau dieser Phase) auf.

    Anker-Tag: Eine Phase wird ab dem Schlusskurs des Vortags des ersten
    Phasentags gemessen (bei der ersten Zeile des Kalenders: ab dem Starttag
    selbst), "Tage" ist die Zahl der Handelstage seit diesem Anker.

    Spread: `risk_spread` ist der volle Spread des Risk-Assets. Die Cash-Seite
    zahlt beim Einstieg (Risk verkaufen) und beim Ausstieg (Risk kaufen)
    jeweils den halben Spread; Tagesgeld selbst hat keinen Spread. Die
    Tagesgeld-Rendite (nach Steuer, `cash_net_return`) wird um diese Kosten
    gemindert."""
    idx = risky_adj.index
    round_trip = (1.0 - 0.5 * risk_spread) ** 2
    rows = []
    for start, end in identify_position_episodes(daily_position, "CASH"):
        pos = idx.get_loc(start)
        anchor = idx[pos - 1] if pos > 0 else start
        n_days = idx.get_loc(end) - idx.get_loc(anchor)
        if cash_net_return is not None:
            days = cash_net_return.reindex(idx).fillna(0.0).loc[anchor:end].iloc[1:]
            gross_return = float((1.0 + days).prod() - 1.0)
        else:
            gross_return = 0.0
        cash_return = (1.0 + gross_return) * round_trip - 1.0
        risky_return = risky_adj.loc[end] / risky_adj.loc[anchor] - 1.0
        delta = cash_return - risky_return
        winner = "Def" if delta > 0 else ("Risk" if delta < 0 else ("=" if pd.notna(delta) else "n/a"))
        rows.append({
            "start": start, "end": end, "n_days": n_days,
            "asset_ticker": "CASH",
            "asset_return": cash_return, "risky_return": risky_return,
            "asset_return_gross": gross_return,
            "delta": delta, "winner": winner,
        })
    return rows


def format_defensive_phase_detail_table(risky_adj: pd.Series,
                                         daily_position: pd.Series,
                                         risk_spread: float = 0.0,
                                         cash_net_return: pd.Series | None = None) -> str:
    """Listet JEDE einzelne Cash-Phase (Defensiv-Regime) einzeln auf (Start,
    Ende, Dauer, Tagesgeld-Rendite (Def-Rend.) sowie die Rendite des
    Risk-Assets in genau dieser Phase (Risk-Rend.), gefolgt vom DELTA daraus)
    - analog zu format_yearly_comparison_table(): ein positives Delta heißt,
    Tagesgeld hat sich in dieser Phase gelohnt, ein negatives, dass man mit
    Risk besser gefahren wäre.

    Die "Gesamt"-Zeile ist wie bei format_yearly_comparison_table() NICHT
    die (zinseszins-verzerrende) Summe der einzelnen Phasen-Deltas,
    sondern verkettet (compoundet) Def-Rend. und Risk-Rend. über ALLE
    Phasen hinweg zu je einer Gesamtrendite - Δ Rendite in dieser Zeile ist
    die Differenz dieser beiden Gesamtrenditen. Die Gewinner-Spalte zählt
    davon unabhängig, in wie vielen EINZELNEN Phasen Def bzw. Risk vorne lag.
    Die Durchschnittszeile bildet den Mittelwert je Phase. (Auf einen Median
    wird bewusst verzichtet: die Outperformance stammt typischerweise aus
    wenigen dominanten Phasen.) NaN-Deltas ("n/a"-Zeilen) werden von
    Verkettung, Zählung und Mittelwerten ausgeschlossen.

    Spread: "Def-Rend." ist NACH den Spread-Kosten für Ein- und Ausstieg (siehe
    _defensive_phase_rows()) und inkl. Tagesgeld-Zins nach Steuer."""
    rows = _defensive_phase_rows(risky_adj, daily_position,
                                 risk_spread=risk_spread, cash_net_return=cash_net_return)

    _pct = _signed_pct

    asset_col = 11
    lines = ["\nDefensiv-Phasen im Detail:"]
    header = (f"  {'Start':<12}{'Ende':<12}{'Tage':>6}{'Def-Asset':>{asset_col}}"
              f"{'Def-Rend.':>14}{'Risk-Rend.':>14}{'Δ Rendite':>13}"
              f"{'Gewinner':>18}")
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        lines.append(f"  {row['start'].date().isoformat():<12}{row['end'].date().isoformat():<12}"
                      f"{row['n_days']:>6}"
                      f"{row['asset_ticker']:>{asset_col}}"
                      f"{_pct(row['asset_return']):>14}"
                      f"{_pct(row['risky_return']):>14}"
                      f"{_pct(row['delta']):>13}"
                      f"{row['winner']:>18}")

    lines.append("-" * len(header))
    valid_rows = [row for row in rows if pd.notna(row["delta"])]
    if valid_rows:
        total_def = 1.0
        total_risk = 1.0
        for row in valid_rows:
            total_def *= 1.0 + row["asset_return"]
            total_risk *= 1.0 + row["risky_return"]
        total_def -= 1.0
        total_risk -= 1.0
        total_delta = total_def - total_risk
    else:
        total_def = total_risk = total_delta = float("nan")
    sum_days = sum(row["n_days"] for row in rows)
    n_def = sum(1 for row in rows if row["winner"] == "Def")
    n_risk = sum(1 for row in rows if row["winner"] == "Risk")
    lines.append(f"  {'Gesamt':<12}{'':<12}{sum_days:>6}{'':>{asset_col}}"
                 f"{_pct(total_def):>14}{_pct(total_risk):>14}"
                 f"{_pct(total_delta):>13}"
                 f"{f'{n_def} Def / {n_risk} Risk':>18}")

    if valid_rows:
        avg_days = float(np.mean([row["n_days"] for row in valid_rows]))
        avg_def = float(np.mean([row["asset_return"] for row in valid_rows]))
        avg_risk = float(np.mean([row["risky_return"] for row in valid_rows]))
        avg_delta = float(np.mean([row["delta"] for row in valid_rows]))
        avg_days_str = f"{avg_days:.1f}"
    else:
        avg_def = avg_risk = avg_delta = float("nan")
        avg_days_str = "n/a"
    lines.append(f"  {'Durchschnitt':<12}{'':<12}{avg_days_str:>6}{'':>{asset_col}}"
                 f"{_pct(avg_def):>14}{_pct(avg_risk):>14}"
                 f"{_pct(avg_delta):>13}")
    return "\n".join(lines)


def format_risk_phase_detail_table(risky_adj: pd.Series,
                                    daily_position: pd.Series,
                                    name: str) -> str:
    """Listet JEDE einzelne Risk-Phase auf (Start, Ende, Dauer, gehaltenes
    Asset unter dem Varianten-Namen `name`, z.B. SP500_2x, und dessen
    Rendite) - analog zu format_defensive_phase_detail_table(). Anker-Tag und
    Dauer wie in _defensive_phase_rows(). Die "Gesamt"-Zeile verkettet
    (compoundet) die Phasenrenditen, die Durchschnittszeile bildet den
    Mittelwert je Phase."""
    idx = risky_adj.index
    rows = []
    for start, end in identify_position_episodes(daily_position, "RISK"):
        pos = idx.get_loc(start)
        anchor = idx[pos - 1] if pos > 0 else start
        rows.append({
            "start": start, "end": end,
            "n_days": idx.get_loc(end) - idx.get_loc(anchor),
            "held_return": risky_adj.loc[end] / risky_adj.loc[anchor] - 1.0,
        })

    def _pct(v: float) -> str:
        return f"{v:+.1%}" if pd.notna(v) else "n/a"

    asset_col = max(10, len(name) + 3)
    lines = ["\nRisk-Phasen im Detail:"]
    header = f"  {'Start':<12}{'Ende':<12}{'Tage':>6}{'Asset':>{asset_col}}{'Rendite':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in rows:
        lines.append(f"  {r['start'].date().isoformat():<12}{r['end'].date().isoformat():<12}"
                      f"{r['n_days']:>6}{name:>{asset_col}}"
                      f"{_pct(r['held_return']):>12}")
    lines.append("-" * len(header))
    if rows:
        total_held = float(np.prod([1.0 + r["held_return"] for r in rows]) - 1.0)
        avg_days = f"{np.mean([r['n_days'] for r in rows]):.1f}"
        avg_held = float(np.mean([r["held_return"] for r in rows]))
        lines.append(f"  {'Gesamt':<12}{'':<12}{sum(r['n_days'] for r in rows):>6}{'':>{asset_col}}"
                     f"{_pct(total_held):>12}")
        lines.append(f"  {'Durchschnitt':<12}{'':<12}{avg_days:>6}{'':>{asset_col}}"
                     f"{_pct(avg_held):>12}")
    return "\n".join(lines)


def format_trend_quadrant_table(risky_adj: pd.Series, tip_state: pd.Series,
                                 trend_state: pd.Series, sig_name: str) -> str:
    """Diagnose: Rendite des Risk-Assets (EUR, vor Steuern, ohne Kosten)
    getrennt nach den vier Kombinationen aus TIP-Regime und Trendsignal.
    Verwendet werden die Signalstände der jeweiligen Zeile (wie in der
    Strategie, also ohne Look-Ahead, inkl. Whipsaw-Filter). "Rendite p.a."
    und "Vola p.a." sind aus den Tagen der Gruppe hochgerechnet (die Tage
    sind nicht zusammenhängend, daher nur zum Vergleichen der Gruppen);
    "kumuliert" ist das Produkt aller Tagesrenditen der Gruppe."""
    idx = tip_state.index
    r = risky_adj.pct_change().fillna(0.0).reindex(idx).fillna(0.0)
    tip_lbl = pd.Series(np.where(tip_state == "RISK", "TIP Risk", "TIP Def "), index=idx)
    sig_lbl = pd.Series(np.where(trend_state.reindex(idx) == "RISK",
                                 f"{sig_name} über", f"{sig_name} unter"), index=idx)
    quad = tip_lbl + " | " + sig_lbl
    order = [f"TIP Risk | {sig_name} über", f"TIP Risk | {sig_name} unter",
             f"TIP Def  | {sig_name} über", f"TIP Def  | {sig_name} unter"]
    header = (f"  {'Gruppe':<26}{'Tage':>7}{'Zeit':>8}{'Phasen':>8}{'Rendite p.a.':>14}"
              f"{'Vola p.a.':>11}{'kumuliert':>12}")
    lines = ["\nDiagnose: Risk-Asset-Rendite nach TIP-Regime und Trendsignal "
             "(vor Steuern, ohne Kosten):", header, "-" * len(header)]
    for label in order:
        rg = r[quad == label]
        n = len(rg)
        if n == 0:
            lines.append(f"  {label:<26}{0:>7d}")
            continue
        growth = float((1.0 + rg).prod())
        ann = growth ** (TRADING_DAYS_PER_YEAR / n) - 1.0
        vol = float(rg.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if n > 1 else float("nan")
        episodes = len(identify_position_episodes(quad, label))
        lines.append(f"  {label:<26}{n:>7d}{n / len(r):>8.1%}{episodes:>8d}{ann:>14.1%}"
                     f"{vol:>11.1%}{growth - 1.0:>12.0%}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Plots
# ----------------------------------------------------------------------
def regime_phases(daily_position: pd.Series) -> tuple[list[tuple[pd.Timestamp, pd.Timestamp]],
                                                        list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """Zerlegt die TATSÄCHLICH gehaltene Position (daily_position, siehe
    backtest_tip_canary()) in zusammenhängende Risk- bzw. Defensiv-Phasen (siehe
    identify_position_episodes()), zur flächigen Hintergrund-Markierung
    in plot_strategy_comparison()/plot_drawdowns(). "RISK" ist dabei das
    eine Regime, JEDER andere Wert (DEFENSIVE oder CASH) zusammen das "Defensiv"-Regime - fürs Plotten interessiert nur
    der makro-seitige Risk/Defensiv-Zustand, nicht WELCHES konkrete
    defensive Asset/Cash gehalten wird (das zeigen die Detail-Tabellen
    bereits).
    Rückgabe: (risk_phases, defensive_phases) - je eine chronologisch
    sortierte Liste von (Anfang, Ende)-Tupeln (jeweils inklusive)."""
    if len(daily_position) == 0:
        return [], []
    macro = daily_position.where(daily_position == "RISK", "DEFENSIVE")
    risk_phases = identify_position_episodes(macro, "RISK")
    defensive_phases = identify_position_episodes(macro, "DEFENSIVE")
    return risk_phases, defensive_phases


# Sehr helle Flächenfarben für die Regime-Hintergrund-Markierung (siehe
# _shade_regime_phases()) - bewusst blass gewählt, damit die darüber
# gezeichneten Kurven trotz durchgehend eingefärbter Fläche weiterhin
# gut lesbar bleiben.
REGIME_PHASE_COLOR_RISK = "#e6f6e6"       # sehr helles Grün
REGIME_PHASE_COLOR_DEFENSIVE = "#fbe6e6"  # sehr helles Rot


def _shade_regime_phases(ax, risk_phases: list[tuple[pd.Timestamp, pd.Timestamp]],
                          defensive_phases: list[tuple[pd.Timestamp, pd.Timestamp]]) -> None:
    """Färbt den Plot-Hintergrund durchgehend über die gesamte Dauer
    jeder Phase ein (siehe regime_phases()) - HELLGRÜN für Risk-Phasen,
    HELLROT für Defensiv-Phasen. Jede Farbe bekommt genau EINEN
    Legenden-Eintrag (am ersten Vorkommen), nicht einen pro Phase -
    sonst würde die Legende bei vielen Regime-Wechseln unlesbar."""
    for i, (start, end) in enumerate(risk_phases):
        ax.axvspan(start, end, color=REGIME_PHASE_COLOR_RISK, zorder=0,
                   label="Risk-Phase" if i == 0 else None)
    for i, (start, end) in enumerate(defensive_phases):
        ax.axvspan(start, end, color=REGIME_PHASE_COLOR_DEFENSIVE, zorder=0,
                   label="Defensiv-Phase" if i == 0 else None)


def plot_strategy_comparison(curves: dict[str, pd.Series], title: str, filename: str,
                              risk_phases: list[tuple[pd.Timestamp, pd.Timestamp]] = (),
                              defensive_phases: list[tuple[pd.Timestamp, pd.Timestamp]] = ()) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    _shade_regime_phases(ax, risk_phases, defensive_phases)
    for label, series in curves.items():
        ax.plot(series.index, series.values, label=label, linewidth=1.3)
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_ylabel("Wertentwicklung (Start = 1, log)")
    ax.set_xlabel("Datum")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(True, which="both", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / filename, dpi=150)
    plt.close(fig)


def plot_drawdowns(curves: dict[str, pd.Series], filename: str,
                    risk_phases: list[tuple[pd.Timestamp, pd.Timestamp]] = (),
                    defensive_phases: list[tuple[pd.Timestamp, pd.Timestamp]] = ()) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    _shade_regime_phases(ax, risk_phases, defensive_phases)
    for label, series in curves.items():
        dd = series / series.cummax() - 1.0
        ax.plot(dd.index, dd.values * 100, label=label, linewidth=1.1)
    ax.set_title("Drawdown-Verlauf")
    ax.set_ylabel("Drawdown in %")
    ax.set_xlabel("Datum")
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / filename, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------
# Hauptprogramm
# ----------------------------------------------------------------------
def _leverage_suffix(info: dict) -> str:
    leverage = info["leverage"]
    return "" if leverage == 1.0 else f" [synth. {leverage:g}x]"


def load_market_data() -> dict:
    """Lädt alle Marktdaten und baut die synthetischen Risk-Assets (SPY ggf.
    gehebelt, in EUR, siehe build_synthetic_eur()) sowie den Tagesgeld-Zins.
    Wird von main() und von backtest_sparplan.py genutzt."""
    now_berlin = datetime.now(BERLIN_TZ)
    query_end_date = compute_query_end_date(now_berlin)
    print(f"Aktuelle Zeit (Berlin): {now_berlin.strftime('%Y-%m-%d %H:%M:%S')} "
          f"- Kurse werden bis {query_end_date.date()} abgefragt.\n")

    canary_adj = get_adj_close(CANARY_TICKER, query_end_date)
    trend_adj = get_adj_close(TREND_TICKER, query_end_date)

    # EUR/USD-Wechselkurs EINMALIG laden (siehe "Währungsumrechnung" im
    # Modul-Docstring).
    eur_per_usd = load_eur_per_usd(query_end_date)

    # Synthetische Risk-Assets bauen. Rohkurse je Yahoo-Ticker nur einmal abrufen.
    raw_adj_by_yahoo_ticker: dict[str, pd.Series] = {}

    def _raw(yahoo_ticker: str) -> pd.Series:
        if yahoo_ticker not in raw_adj_by_yahoo_ticker:
            raw_adj_by_yahoo_ticker[yahoo_ticker] = get_adj_close(yahoo_ticker, query_end_date)
        return raw_adj_by_yahoo_ticker[yahoo_ticker]

    rate_cache: dict[str, pd.Series] = {}
    cost_text_by_variant: dict[str, str] = {}
    risky_adj_by_ticker: dict[str, pd.Series] = {}
    for variant, info in RISK_TICKERS.items():
        rate_pct = None
        if info["leverage"] != 1.0:
            rid = info["funding_rate"]
            if rid not in rate_cache:
                rate_cache[rid] = load_fred_rate(
                    rid, needed_from=max(_raw(info["ticker"]).index.min(), eur_per_usd.index.min()))
            rate_pct = rate_cache[rid]
        risky_adj_by_ticker[variant], cost_text_by_variant[variant] = build_synthetic_eur(
            _raw(info["ticker"]), eur_per_usd, info["leverage"], info["fixed_cost_pa"],
            rate_pct, info["lever_currency"])

    # Tagesgeld-Zins für Cash-Phasen (nach Steuer), auf dem Kalender des Risk-Assets.
    # Dieselbe Reihe (z. B. ECBDFR) dient auch als Finanzierungszins: nicht erneut abrufen.
    cash_calendar = next(iter(risky_adj_by_ticker.values())).index
    cash_rate = None
    if TAGESGELD_RATE is not None:
        if TAGESGELD_RATE not in rate_cache:
            rate_cache[TAGESGELD_RATE] = load_fred_rate(TAGESGELD_RATE, needed_from=cash_calendar[0])
        cash_rate = rate_cache[TAGESGELD_RATE]
    cash_net_return = tagesgeld_net_daily_return(cash_calendar, cash_rate)

    return {"canary_adj": canary_adj, "trend_adj": trend_adj,
            "risky_adj_by_ticker": risky_adj_by_ticker,
            "cost_text_by_variant": cost_text_by_variant,
            "cash_net_return": cash_net_return}


def main() -> None:
    # Nur der ERSTE Eintrag in RISK_TICKERS bekommt die ausführlichen
    # Zusatz-Tabellen (siehe Modul-Docstring "Getestete Varianten").
    primary_ticker = next(iter(RISK_TICKERS))

    data = load_market_data()
    canary_adj, trend_adj = data["canary_adj"], data["trend_adj"]
    risky_adj_by_ticker = data["risky_adj_by_ticker"]
    cost_text_by_variant = data["cost_text_by_variant"]
    cash_net_return = data["cash_net_return"]

    # --- Backtest je Variante und Strategie ---
    results_by_label: dict[str, dict[str, dict]] = {
        variant: {
            mode: run_single_backtest(
                canary_adj, risky_adj_by_ticker[variant], variant,
                trend_adj=trend_adj, mode=mode,
                cash_net_return=cash_net_return,
            )
            for mode in STRATEGY_NAMES
        }
        for variant in RISK_TICKERS
    }

    # --- Buy & Hold-Referenzen (nach Steuern), je Variante, ab demselben
    #     Startdatum wie der TIP-Canary-Lauf dieser Variante ---
    strategy_stats_by_label = {}
    stats_labels_by_variant: dict[str, list[str]] = {}
    curves = {}
    capture_by_variant: dict[str, dict[str, float]] = {}
    for variant, info in RISK_TICKERS.items():
        risky_adj = risky_adj_by_ticker[variant]
        # Alle Strategien teilen denselben Start (TIP-Signalstart).
        common_start = results_by_label[variant]["hybrid"]["common_start_used"]
        bh_equity = buy_and_hold_after_tax(risky_adj, variant, start_date=common_start)

        lev_prefix = f"{info['leverage']:g}x "
        bh_label = f"{lev_prefix}B&H"
        for mode, mode_name in STRATEGY_NAMES.items():
            result = results_by_label[variant][mode]
            label = f"{lev_prefix}{mode_name}"
            if label in strategy_stats_by_label:
                raise ValueError(
                    f"RISK_TICKERS: die Varianten \"{variant}\" und eine vorherige ergeben dasselbe "
                    f"Anzeige-Label \"{label}\" (identischer Name + identischer Hebel) - "
                    f"bitte in RISK_TICKERS prüfen, ob hier versehentlich dieselbe Variante doppelt "
                    f"mit denselben Parametern eingetragen wurde."
                )
            capture = capture_ratios(result["equity_after_tax"], bh_equity)
            if mode == "hybrid":
                capture_by_variant[variant] = capture
            strategy_stats_by_label[label] = {
                **result["perf"], "Up-Cap": capture["up"], "Down-Cap": capture["down"],
                "Wechsel": result["switches"], "Ø/Jahr": result["switches_per_year"]}
            curves[label] = result["equity_after_tax"]
            stats_labels_by_variant.setdefault(variant, []).append(label)
        strategy_stats_by_label[bh_label] = {
            **performance_stats(bh_equity), "Up-Cap": 1.0, "Down-Cap": 1.0,
            "Wechsel": 0, "Ø/Jahr": 0.0}
        curves[bh_label] = bh_equity
        stats_labels_by_variant[variant].append(bh_label)

    # --- Textauswertung: wird gleichzeitig ausgegeben und gesammelt,
    #     um sie am Ende in EINE Textdatei zu schreiben ---
    report_lines: list[str] = [
        "=" * 70,
        "Backtest-Auswertung (SYNTHETISCH): TIPxSMA (TIP-Canary + Nasdaq-100-SMA), S&P 500 aus SPY in EUR",
        f"Erstellt: {datetime.now(BERLIN_TZ).strftime('%Y-%m-%d %H:%M:%S')} (Berlin)",
        "=" * 70,
    ]

    def emit(text: str, tight: bool = False) -> None:
        # Abschnitte beginnen mit einer Leerzeile; eine weitere davor ergibt
        # ZWEI Leerzeilen zwischen zwei Tabellen. tight=True: Text gehört
        # inhaltlich zur vorherigen Ausgabe (Überschrift + Tabelle) -> nur eine.
        if text.startswith("\n") and not tight:
            text = "\n" + text
        print(text)
        report_lines.append(text)

    def _variant_label(variant: str, info: dict) -> str:
        primary_marker = " [ausführliche Auswertung]" if variant == primary_ticker else ""
        return (f"({info['ticker']}) {info['name']}{_leverage_suffix(info)}{primary_marker}"
                f"\n    Kosten: {cost_text_by_variant[variant]}")

    risk_assets_str = "\n  ".join(_variant_label(v, info) for v, info in RISK_TICKERS.items())
    bh_info_lines = [f"  {v}: rein synthetisch ({cost_text_by_variant[v]})." for v in RISK_TICKERS]
    cash_text = (f"\nCash-Phasen: Tagesgeld zu max({TAGESGELD_RATE} - {TAGESGELD_ABSCHLAG * 100:.2f}%, 0), "
                 f"täglich nach {ABGELTUNGSTEUER_BASISSATZ:.3%} Steuer gutgeschrieben."
                 if TAGESGELD_RATE else "")
    emit(f"\nRisk-Asset-Varianten (rein synthetisch, Kosten zeitvariabel):\n  {risk_assets_str}"
         f"{cash_text}"
         f"\nTIPxSMA: Risk, wenn TIP (a={CONFIRMATION_A}/b={CONFIRMATION_B}) ODER {TREND_TICKER} über "
         f"seiner SMA{TREND_SMA_DAYS} (Filter a={TREND_CONFIRMATION_A}/b={TREND_CONFIRMATION_B}) "
         f"Risk meldet; Defensiv nur, wenn beide schlecht stehen."
         f"\nBuy & Hold-Referenz:\n" + "\n".join(bh_info_lines))

    # --- Gesamtübersicht: je Variante (1x/2x) eine eigene Tabelle, jeweils
    #     absteigend nach der erzielten Rendite sortiert ---
    for variant, info in RISK_TICKERS.items():
        variant_stats = {lbl: strategy_stats_by_label[lbl] for lbl in stats_labels_by_variant[variant]}
        ordered = sorted(variant_stats, key=lambda lbl: variant_stats[lbl]["Rendite"], reverse=True)
        emit(f"\n{info['leverage']:g}x: TIPxSMA, TIP und SMA (NDX-SMA200) vs. B&H "
             f"(jeweils nach Steuern, sortiert nach Rendite; "
             f"Wechsel = Risk-Asset <-> Defensiv/Cash):")
        emit(format_stats_table({lbl: variant_stats[lbl] for lbl in ordered}), tight=True)

    # --- Ab hier NUR für die primäre Variante (Referenz-Strategie "hybrid") ---
    primary_result = results_by_label[primary_ticker]["hybrid"]
    primary_risky_adj = risky_adj_by_ticker[primary_ticker]
    primary_daily_position = primary_result["daily_position"]

    # Zusätzliche Kennzahlen (Zeitanteile, Wechsel, Steuern, Capture)
    emit(format_extra_metrics(primary_result, capture_by_variant[primary_ticker]))

    # Diagnose: Risk-Asset-Rendite nach TIP-Regime x Trendsignal
    emit(format_trend_quadrant_table(primary_risky_adj, primary_result["tip_macro"],
                                      primary_result["trend_macro"], f"SMA{TREND_SMA_DAYS}"))

    # Jahresweise Kennzahlen
    primary_label = f"{RISK_TICKERS[primary_ticker]['leverage']:g}x "
    emit(format_yearly_comparison_table(
        curves[primary_label + STRATEGY_NAMES["hybrid"]], curves[primary_label + "B&H"],
        name=STRATEGY_NAMES["hybrid"],
        canary_year_returns=isolated_yearly_returns(**primary_result["tax_inputs"]),
        bh_year_returns=buy_and_hold_yearly_returns(
            primary_risky_adj, primary_ticker, start_date=primary_result["common_start_used"])))

    # Jede Cash-Phase (Defensiv-Regime) einzeln aufgelistet
    emit(format_defensive_phase_detail_table(primary_risky_adj, primary_daily_position,
                                              risk_spread=spread_for_ticker(primary_ticker),
                                              cash_net_return=cash_net_return))

    # Jede Risk-Phase einzeln aufgelistet (optional)
    if SHOW_RISK_PHASES:
        emit(format_risk_phase_detail_table(primary_risky_adj, primary_daily_position,
                                             name=primary_ticker))

    results_path = OUTPUT_DIR / "backtest_ergebnis.txt"
    results_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # --- Plots (Regime-Phasen-Hintergrund: hellgrün = Risk-Phase,
    #     hellrot = Defensiv-Phase - aus der gehaltenen Position der
    #     PRIMÄREN Variante, siehe regime_phases()) ---
    risk_phases, defensive_phases = regime_phases(primary_daily_position)
    # Grafik nur für die gehebelten Varianten (die 1x-Varianten stehen in der
    # Textauswertung); gibt es keine, werden alle gezeichnet.
    plot_variants = [v for v, info in RISK_TICKERS.items() if info["leverage"] != 1.0] or list(RISK_TICKERS)
    plot_curves = {lbl: curves[lbl] for v in plot_variants for lbl in stats_labels_by_variant[v]}
    plot_leverage = ", ".join(dict.fromkeys(f"{RISK_TICKERS[v]['leverage']:g}x" for v in plot_variants))
    plot_strategy_comparison(
        plot_curves,
        title=f"TIPxSMA / TIP / SMA vs. B&H ({plot_leverage}) - jeweils nach Steuern",
        filename="01_strategie_vergleich.png",
        risk_phases=risk_phases,
        defensive_phases=defensive_phases,
    )
    plot_drawdowns(plot_curves, filename="02_drawdowns.png",
                    risk_phases=risk_phases, defensive_phases=defensive_phases)

    print(f"\nTextauswertung und Plots gespeichert in: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except FredUnavailableError as err:
        print(f"\n[Abbruch] {err}")
        input("\nEnter zum Beenden dr\u00fccken...")
        raise SystemExit(1)
    input("\nFertig - Enter zum Beenden drücken...")
