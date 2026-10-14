"""
Depotkonto-Auswertung: Eigene Strategie vs. Buy&Hold-Referenzen
=================================================================

Wertet CSV-Exporte von Depotkonto-Aktionen (Kauf/Verkauf/Steuer) aus.
Für jede CSV-Datei im Unterordner "stats" (relativ zum Skript-
Verzeichnis, siehe CSV_SUBDIR) wird eine EIGENE, unabhängige
Auswertung erzeugt:

  1. Liest die Transaktionen (buy/sell/tax) ein und rekonstruiert
     daraus je Ticker den Bestand an Anteilen (Shares) über die Zeit.
  2. Lädt die Kurshistorie aller beteiligten Ticker sowie aller
     konfigurierten Referenz-Ticker - GEMEINSAM für ALLE CSV-Dateien
     in einem Rutsch (siehe main()): jeder benötigte Ticker wird dafür
     nur EIN einziges Mal abgefragt, mit einem Zeitfenster, das ab dem
     frühesten Transaktionsdatum über ALLE CSV-Dateien hinweg beginnt.
     Das vermeidet wiederholte Abfragen dann, wenn mehrere CSV-Dateien
     denselben Ticker verwenden (z.B. alle REFERENCE_TICKERS, oder ein
     Ticker, der in mehreren Depots vorkommt). Für die Auswertung einer
     einzelnen CSV-Datei wird die jeweilige Ticker-Kursreihe danach nur
     noch auf deren tatsächlich benötigtes (i.d.R. späteres) Startdatum
     zurechtgeschnitten.
  3. Berechnet den täglichen Depotwert der EIGENEN Strategie sowie
     das netto investierte Kapital (siehe "Renditeberechnung" unten).
  4. Simuliert für jeden konfigurierten Referenz-Ticker eine
     Buy&Hold-Strategie mit denselben Netto-Kapitalflüssen (siehe
     "Referenzvergleich (Buy&Hold)" unten), inklusive jährlicher
     Vorabpauschale-Besteuerung (siehe "Vorabpauschale" unten).
  5. Schreibt eine Textauswertung (Investiert, Depotstand, Rendite als
     Summe & Prozent - jeweils insgesamt und pro Jahr, sowie die
     aktuell gehaltenen Shares je Ticker) für die eigene Strategie in
     "results.txt". Als Vergleich wird dort zusätzlich - nur als
     Rendite (%), sowohl insgesamt als auch pro Jahr - die jeweilige
     Buy&Hold-Rendite jedes Referenz-Tickers mit ausgegeben.
  6. Erstellt zwei matplotlib-Plots: den Depotverlauf in EUR
     (logarithmische y-Achse; eigene Strategie, investiertes Kapital
     sowie jeder Referenz-Ticker - Dateiname "deposit.png") sowie den
     Verlauf der absoluten Rendite (Rendite (Summe) in EUR, lineare
     y-Achse; eigene Strategie und jeder Referenz-Ticker - Dateiname
     "return.png"). In beiden Plots ist die eigene Strategie
     durchgehend (dickere Linie), die Referenz-Ticker (Buy&Hold)
     gestrichelt und dünner dargestellt.
  Textauswertung und Plots landen jeweils in einem eigenen, nach der
  CSV-Datei benannten Unterordner innerhalb von "stats", z.B.
  "stats/MeinDepot/results.txt" für "stats/MeinDepot.csv" (wird bei
  Bedarf angelegt) - die Ausgabedateien selbst brauchen deshalb kein
  Dateinamen-Präfix.

CSV-Format (Semikolon-getrennt, deutsches Dezimalkomma):
  date;action;ticker;shares;sum
  15.08.2025;buy;WEBN.DE;76,07455;800,00
  21.04.2026;sell;WEBN.DE;1698,00000;20005,12
  01.08.2026;tax;;;333,33
  - action "buy":  `shares` Anteile von `ticker` für `sum` EUR gekauft.
  - action "sell": `shares` Anteile von `ticker` für `sum` EUR verkauft
    (`sum` = tatsächlich erhaltener Betrag, ggf. bereits inkl. von der
    Bank einbehaltener Kapitalertragsteuer - siehe "Steuern" unten).
  - action "tax": `sum` EUR Steuerzahlung ABSEITS eines Kauf/Verkaufs
    (z.B. Vorabpauschale-Nachzahlung), `ticker`/`shares` bleiben leer.

Renditeberechnung (eigene Strategie):
  "Investiertes Kapital" (netto) = kumulierte Kauf-Summen minus
  kumulierte Verkaufs-Summen plus kumulierte "tax"-Zahlungen. Das
  bildet ab, wie viel EIGENES Geld netto ins Depot geflossen ist -
  wird ein Verkaufserlös direkt wieder investiert (wie im Beispiel:
  WEBN.DE komplett verkauft, Erlös in XDEM.DE angelegt), bleibt das
  investierte Kapital dadurch praktisch unverändert (Kauf und Verkauf
  heben sich auf), statt fälschlich doppelt gezählt zu werden.
    Rendite (Summe), gesamt = aktueller Depotwert - investiertes
      Kapital (aktuell).
    Rendite (%), gesamt = Rendite (Summe) / investiertes Kapital
      (aktuell).
    Rendite p.a. (%), gesamt (vereinfachte Annualisierung, ebenfalls
      ohne Geldgewichtung): (1 + Rendite (%), gesamt) ^ (365,25 /
      Anzahl Kalendertage im Betrachtungszeitraum) - 1. Wie bei der
      Gesamtrendite (%) fließen Zeitpunkt und Höhe der einzelnen
      Kapitalzuflüsse NICHT gewichtet ein - für eine grobe p.a.-Angabe
      ausreichend, aber kein exaktes Geldgewichtungsverfahren
      (IRR/XIRR).
    Rendite pro Jahr (vereinfachte Berechnung, ohne untermonatliche
      Zeitgewichtung): für Jahr Y werden Depotwert und investiertes
      Kapital jeweils am letzten Handelstag VOR Jahresbeginn sowie am
      letzten verfügbaren Handelstag des Jahres bestimmt.
        Netto-Kapitalzufluss(Y) = investiertes Kapital(Jahresende) -
          investiertes Kapital(Jahresanfang)
        Rendite (Summe, Y) = Depotwert(Jahresende) -
          Depotwert(Jahresanfang) - Netto-Kapitalzufluss(Y)
        Rendite (%, Y) = Rendite (Summe, Y) / (Depotwert(Jahresanfang)
          + Netto-Kapitalzufluss(Y))
      Das ist eine vereinfachte ("Modified Dietz"-ähnliche) Näherung
      ohne Gewichtung nach dem genauen Tag der Kapitalzuflüsse
      innerhalb des Jahres - für eine grobe Jahresrendite ausreichend,
      aber kein exaktes Geldgewichtungsverfahren (IRR/XIRR).

Referenzvergleich (Buy&Hold):
  Für jeden in REFERENCE_TICKERS konfigurierten Ticker wird simuliert,
  was eine reine Buy&Hold-Strategie mit denselben NETTO-Kapitalflüssen
  erwirtschaftet hätte. Dazu werden alle "buy"/"sell"-Aktionen der
  eigenen Strategie (OHNE die separaten "tax"-Zahlungen, siehe unten)
  je Kalendertag zu einem Netto-Kapitalfluss aufsummiert:
    - Netto-Kapitalfluss > 0 an einem Tag (mehr gekauft als verkauft,
      bzw. reiner Kauf): wird als Kauf von Referenz-Ticker-Anteilen
      zum Kurs dieses Tages nachgebildet.
    - Netto-Kapitalfluss < 0 an einem Tag (per Saldo mehr verkauft als
      gekauft, z.B. echte Entnahme aus dem Depot): wird als Verkauf
      von Referenz-Ticker-Anteilen (FIFO, älteste zuerst) im selben
      Gegenwert nachgebildet - das ist eine Abweichung von "reinem"
      Buy&Hold, aber nötig, um die Kapitalbindung zwischen eigener
      Strategie und Referenz vergleichbar zu halten. In den mitgelie-
      ferten Beispieldaten kommt das praktisch nicht vor (Verkauf und
      Rückkauf am selben Tag ergeben zusammen einen kleinen positiven
      Saldo). Auf eine etwaige Kapitalertragsteuer für einen solchen
      simulierten Verkauf (jenseits der Vorabpauschale) wird bewusst
      NICHT eingegangen (weiterer, dokumentierter Vereinfachungs-
      schritt).
  Referenz-Ticker, die erst NACH dem ersten Kapitalfluss notiert wurden:
  Wurde ein Referenz-Ticker erst im Laufe der Investmenthistorie
  eingeführt (Erstnotiz = erster Handelstag seiner Kursreihe liegt NACH
  dem ersten Kauf/Verkauf der CSV), wäre ein Buy&Hold in diesem Ticker
  davor gar nicht möglich gewesen. Als realistischer Vorgänger dient
  deshalb die EIGENE Strategie:
    - Bis zur Erstnotiz stimmen Depotwert und investiertes Kapital der
      Referenz mit der eigenen Strategie überein (inkl. deren realen
      "tax"-Zeilen).
    - Am ersten Handelstag des Tickers wird der dann aktuelle Depotwert
      der eigenen Strategie vollständig in den Referenz-Ticker
      umgeschichtet (Kauf zum Schlusskurs dieses Tages, als ein Lot). Die
      Umschichtung wird nicht besteuert (wie die simulierten Verkäufe
      oben). Kapitalflüsse bis einschließlich dieses Tages sind darin
      bereits enthalten, spätere Kapitalflüsse laufen wie gewohnt.
    - Das investierte Kapital der Referenz übernimmt den Stand der
      eigenen Strategie zu diesem Tag und wird danach nur noch durch die
      Netto-Kapitalflüsse und die eigene hypothetische Vorabpauschale
      fortgeschrieben.
    - Kennzahlen (Gesamtzeitraum, pro Jahr) beziehen sich auf den
      gesamten Zeitraum der eigenen Strategie; Jahre vor der Erstnotiz
      entsprechen daher der eigenen Strategie. In der Textauswertung ist
      ein solcher Ticker mit "*" markiert.
    - In den Plots wird die Referenz erst ab der Erstnotiz gezeichnet
      (davor wäre die Linie identisch mit der eigenen Strategie) und
      geht dort aus der Linie der eigenen Strategie hervor.
  "tax"-Zahlungen der eigenen Strategie fließen bewusst NICHT in die
  Referenz-Kapitalflüsse ein: sie sind eine reale Eigenschaft der
  eigenen Strategie (z.B. bereits gezahlte Vorabpauschale/Steuer des
  tatsächlich gehaltenen Fonds) und werden für jeden Referenz-Ticker
  separat und individuell berechnet (siehe "Vorabpauschale" unten).
  Beide Steuerlasten bleiben damit strikt getrennt: die investierte-
  Kapital-Reihe der eigenen Strategie enthält NUR die tatsächlichen
  "tax"-Zeilen der CSV, die investierte-Kapital-Reihe jedes Referenz-
  Tickers enthält NUR dessen eigene, hypothetische Vorabpauschale -
  keine Vermischung der beiden. Das ist beabsichtigt, damit beide
  Strategien jeweils ihre eigene, für sie realistische Steuerlast
  tragen und die Rendite (%) fair vergleichbar bleibt.

Vorabpauschale (siehe https://de.wikipedia.org/wiki/Vorabpauschale):
  Für jeden Referenz-Ticker wird zum Jahreswechsel eine Vorabpauschale
  ermittelt und - nach Anwendung der konfigurierten Teilfreistellung
  sowie Abzug des VOLLEN Sparer-Pauschbetrags (SPARER_PAUSCHBETRAG_JAHR)
  - als zusätzlicher, externer Kapitalabfluss (wie eine "tax"-Aktion)
  in die investierte-Kapital-Reihe des jeweiligen Referenz-Tickers
  eingebucht:
    Basisertrag = 0,7 * Basiszins(Jahr) * Wert der Anteile zum
      Jahresanfang (bzw. bei unterjährig erworbenen Anteilen: zum
      Kaufkurs, anteilig gemindert um 1/12 je vollem Monat vor dem
      Erwerb).
    Vorabpauschale = max(0, min(Basisertrag, Wertsteigerung im
      Kalenderjahr)) - bei Kursverlust im Jahr fällt keine
      Vorabpauschale an.
    Steuerpflichtiger Betrag = Vorabpauschale * (1 - Teilfreistellung)
      (Teilfreistellung konfigurierbar je Ticker, siehe unten -
      Standard 30% für Aktienfonds mit >= 51% Aktienquote).
    Steuer = max(0, Steuerpflichtiger Betrag - SPARER_PAUSCHBETRAG_JAHR)
      * KAPITALERTRAGSTEUERSATZ.
  WICHTIG: Jeder Referenz-Ticker ist ein eigenständiges, unabhängiges
  "was-wäre-wenn ich AUSSCHLIESSLICH in diesen einen Ticker investiert
  hätte"-Szenario und erhält den Sparer-Pauschbetrag deshalb jeweils
  VOLL für sich (nicht anteilig mit anderen Referenz-Tickern geteilt,
  und unabhängig vom tatsächlichen, ggf. bereits anderweitig
  ausgeschöpften Freibetrag der eigenen Strategie).
  WICHTIG: Die Basiszinssätze (BASISZINSSATZ_VORABPAUSCHALE) müssen
  selbst gepflegt werden (siehe Konfiguration unten) - es wird bewusst
  NICHT recherchiert oder automatisch nachgeladen. Fehlt der Basiszins
  für ein Jahr, wird die Vorabpauschale für dieses Jahr ausgelassen
  und eine Warnung ausgegeben.
  Die eigene Strategie ist von alldem NICHT betroffen: dort werden
  Steuern ausschließlich über die tatsächlichen CSV-Zeilen (bereits
  von der Bank verrechnete Verkaufs-Steuer bzw. explizite
  "tax"-Aktionen) abgebildet.

Kursdaten-Abruf (kein Datei-Cache, siehe yf_data.py):
  Jeder Lauf lädt frisch von Yahoo Finance - aber je benötigtem Ticker
  nur EIN EINZIGES MAL für den gesamten Lauf (siehe Punkt 2 oben und
  main()), unabhängig davon, in wie vielen CSV-Dateien der Ticker
  vorkommt. yf_data.py selbst führt zusätzlich eine persistente,
  tickerweise lokale Historie (Regressions-Schutz und Lückenfüller
  über mehrere Skript-LÄUFE hinweg) - siehe dortiger Docstring für die
  Details, das ist kein CSV-Auswertungs-spezifisches Verhalten.

Sicherer Auswertungszeitpunkt:
  Vor SAFE_EVALUATION_TIME_NY (16:05 Uhr New Yorker Zeit, 5 Minuten
  nach dem US-Handelsschluss) wird als Abfrage-Ende nur der letzte
  VOLLSTÄNDIGE Handelstag verwendet (statt eines unfertigen
  Intraday-Standes), zusätzlich abgesichert durch
  drop_unsafe_todays_bar() auf jeder geladenen Kursreihe.

Hinweis zu den konfigurierten Tickern:
  Keine Recherche zu den Tickern, kein Zugriff auf Yahoo-Finanzdaten
  und kein Test mit synthetischen Daten im Rahmen der Skripterstellung
  - bitte selbst prüfen, dass Ticker, Basiszinssätze und
  Teilfreistellungen korrekt konfiguriert sind.

Abhängigkeiten:
    pip install -r requirements.txt
"""

from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import pandas as pd
except ImportError as exc:
    print(f"Fehler: Benötigtes Paket nicht gefunden ({exc.name}).\n"
          f"Bitte einmalig ausführen: pip install -r requirements.txt")
    raise SystemExit(1) from None

from yf_data import (
    BERLIN_TZ,
    NEW_YORK_TZ,
    compute_query_end_date,
    load_prices,
)

# ----------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------

# Referenz-Ticker für den Buy&Hold-Vergleich (siehe Docstring
# "Referenzvergleich"). Ticker -> {"name": Anzeigename, "teilfreistellung":
# ...}. Der Ticker (Dictionary-Key) wird weiterhin für die yf-Abfrage
# verwendet, "name" ausschließlich für die Ausgabe/Plots - als
# Platzhalter zunächst der Tickername selbst, bitte anschließend durch
# den vollständigen ETF-Namen ersetzen. "teilfreistellung" ist die
# Teilfreistellung für die Vorabpauschale (0.30 = 30%, üblich für
# Aktienfonds mit einer Aktienquote von mindestens 51% - bitte je nach
# Fonds prüfen/anpassen, z.B. 0.15 für Mischfonds mit 25-50%
# Aktienquote oder 0.0, falls keine Teilfreistellung greift).
REFERENCE_TICKERS: dict[str, dict] = {
    "XDEM.DE": {"name": "Xtrackers MSCI World Momentum", "teilfreistellung": 0.30},
    "SCWX.DE": {"name": "Scalable MSCI AC World", "teilfreistellung": 0.30},
    "SC2X.DE": {"name": "Scalable MSCI AC World (2x)", "teilfreistellung": 0.30},
}

# Basiszinssatz für die Vorabpauschale je Kalenderjahr (siehe
# https://de.wikipedia.org/wiki/Vorabpauschale) - MUSS selbst gepflegt
# werden (keine automatische Recherche, siehe Docstring). Fehlt ein
# Jahr, wird die Vorabpauschale für dieses Jahr ausgelassen.
BASISZINSSATZ_VORABPAUSCHALE: dict[int, float] = {
    # Jahr: Basiszins, z.B. 2024: 0.0229  -- BITTE SELBST ERGÄNZEN!
    2024: 0.0229,
    2025: 0.0253,
    2026: 0.0320,
}

# Kapitalertragsteuersatz inkl. Solidaritätszuschlag (25% * 1,055),
# ohne Kirchensteuer. Bei Bedarf anpassen.
KAPITALERTRAGSTEUERSATZ = 0.26375

# Sparer-Pauschbetrag pro Kalenderjahr, der auf den steuerpflichtigen
# Vorabpauschale-Betrag JEDES Referenz-Tickers EINZELN und VOLL
# angerechnet wird (jeder Referenz-Ticker ist ein unabhängiges
# Szenario, siehe Docstring "Vorabpauschale").
SPARER_PAUSCHBETRAG_JAHR = 1000.0

# SAFE_EVALUATION_TIME_NY, NEW_YORK_TZ und BERLIN_TZ kommen aus yf_data.py
# (gemeinsam mit canary.py und backtest.py, siehe dortiger Docstring).
# Es gibt keinen Datei-Cache - jeder Lauf lädt frisch.

RESULTS_FILENAME = "results.txt"
PLOT_FILENAME_DEPOSIT = "deposit.png"
PLOT_FILENAME_RETURN = "return.png"

# Unterordner (relativ zum Skript-Verzeichnis), in dem die CSV-Dateien
# erwartet werden. Je CSV-Datei wird darin ein eigener, nach der Datei
# benannter Unterordner mit den Ergebnisdateien angelegt, z.B.
# "stats/MeinDepot/results.txt" für "stats/MeinDepot.csv" - die
# Ausgabedateien brauchen deshalb kein Dateinamen-Präfix.
CSV_SUBDIR = "stats"


def output_path(csv_path: Path, filename: str) -> Path:
    """Zielpfad für eine Ausgabedatei zu `csv_path`, im nach der
    CSV-Datei benannten Unterordner (wird bei Bedarf angelegt)."""
    out_dir = csv_path.parent / csv_path.stem
    out_dir.mkdir(exist_ok=True)
    return out_dir / filename


# ----------------------------------------------------------------------
# Handelskalender-Hilfsfunktionen, sicherer Auswertungszeitpunkt und
# der Kurs-Download selbst kommen aus yf_data.py (gemeinsam mit
# canary.py und backtest.py).
# ----------------------------------------------------------------------

# Börsenkalender-Vollständigkeitsprüfung und der Sicherheits-Cutoff
# für einen ggf. noch unfertigen heutigen Kurs laufen vollständig
# innerhalb von load_prices() (siehe yf_data.py, calendar_for_ticker()/
# GERMAN_EXCHANGE_CALENDAR_BY_SUFFIX dort) - dieses Skript übergibt
# dafür nur noch Ticker und Zeitfenster. Gilt sowohl für die
# konfigurierten Referenz-Ticker als auch für own_tickers (aus der
# CSV).


# ----------------------------------------------------------------------
# Hilfsfunktionen für den Handelskalender
# ----------------------------------------------------------------------
def first_trading_day_on_or_after(price_series: pd.Series, date: pd.Timestamp) -> pd.Timestamp | None:
    idx = price_series.index[price_series.index >= date]
    return idx[0] if len(idx) else None


def last_trading_day_on_or_before(price_series: pd.Series, date: pd.Timestamp) -> pd.Timestamp | None:
    idx = price_series.index[price_series.index <= date]
    return idx[-1] if len(idx) else None


def price_near(price_series: pd.Series, date: pd.Timestamp) -> float | None:
    """Kurs am letzten Handelstag <= `date`; existiert keiner (z.B.
    weil der Ticker zu diesem Zeitpunkt noch nicht gehandelt wurde),
    ersatzweise der erste verfügbare Kurs > `date`. None, falls die
    Kursreihe komplett leer ist."""
    d = last_trading_day_on_or_before(price_series, date)
    if d is not None:
        return float(price_series.loc[d])
    d = first_trading_day_on_or_after(price_series, date)
    return float(price_series.loc[d]) if d is not None else None


def build_calendar(*series: pd.Series) -> pd.DatetimeIndex:
    """Vereinigung der Handelskalender mehrerer Kursreihen."""
    all_dates: set[pd.Timestamp] = set()
    for s in series:
        all_dates.update(s.index)
    return pd.DatetimeIndex(sorted(all_dates))


def step_series_to_calendar(events: list[tuple[pd.Timestamp, float]],
                             calendar: pd.DatetimeIndex) -> pd.Series:
    """Baut aus (Datum, kumulierter-Wert)-Ereignissen eine
    Treppenfunktion auf `calendar` (vorwärts fortgeschrieben, vor dem
    ersten Ereignis = 0)."""
    if not events:
        return pd.Series(0.0, index=calendar)
    ev = pd.Series({d: v for d, v in events}).sort_index()
    ev = ev[~ev.index.duplicated(keep="last")]
    full_index = ev.index.union(calendar)
    s = ev.reindex(full_index).sort_index().ffill().fillna(0.0)
    return s.reindex(calendar).ffill().fillna(0.0)


# ----------------------------------------------------------------------
# CSV-Parsing
# ----------------------------------------------------------------------
def parse_transactions(csv_path: Path) -> pd.DataFrame:
    """Liest eine Depotkonto-CSV (Semikolon-getrennt, deutsches
    Dezimalkomma, deutsches Datumsformat) ein und gibt einen nach
    Datum sortierten DataFrame mit Spalten date/action/ticker/shares/sum
    zurück (shares/sum als float, NaN bei leeren Feldern)."""
    df = pd.read_csv(csv_path, sep=";", dtype=str, keep_default_na=False)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"date", "action", "ticker", "shares", "sum"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path.name}: fehlende Spalte(n) {sorted(missing)}")

    def to_float(s: str) -> float:
        s = s.strip()
        if not s:
            return float("nan")
        return float(s.replace(".", "").replace(",", "."))

    df["date"] = pd.to_datetime(df["date"].str.strip(), format="%d.%m.%Y")
    df["action"] = df["action"].str.strip().str.lower()
    df["ticker"] = df["ticker"].str.strip()
    df["shares"] = df["shares"].apply(to_float)
    df["sum"] = df["sum"].apply(to_float)

    unknown_actions = sorted(set(df["action"]) - {"buy", "sell", "tax"})
    if unknown_actions:
        raise ValueError(f"{csv_path.name}: unbekannte Aktion(en) {unknown_actions}")

    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    return df


def aggregate_net_flow(tx: pd.DataFrame, include_tax: bool) -> dict[pd.Timestamp, float]:
    """Aggregiert Kauf (+sum) / Verkauf (-sum) je Kalendertag zu einem
    Netto-Kapitalfluss. `include_tax` steuert, ob "tax"-Zeilen
    (+sum) mit eingerechnet werden (siehe Docstring: für die eigene
    Strategie ja, für die Referenz-Kontributionen nein)."""
    sign = {"buy": 1.0, "sell": -1.0, "tax": 1.0}
    rows = tx if include_tax else tx[tx["action"] != "tax"]
    flow = rows.apply(lambda r: sign[r["action"]] * r["sum"], axis=1)
    grouped = pd.Series(flow.values, index=rows["date"]).groupby(level=0).sum()
    return grouped.to_dict()


# ----------------------------------------------------------------------
# Eigene Strategie: Bestände & investiertes Kapital
# ----------------------------------------------------------------------
def build_own_strategy(tx: pd.DataFrame, prices: dict[str, pd.Series]) -> dict:
    """Rekonstruiert für die eigene Strategie den Shares-Bestand je
    Ticker über die Zeit, daraus den täglichen Depotwert, sowie das
    netto investierte Kapital (Käufe - Verkäufe + Steuerzahlungen,
    siehe Docstring "Renditeberechnung")."""
    own_tickers = sorted(tx.loc[tx["action"].isin(["buy", "sell"]), "ticker"].unique())
    running_shares = {t: 0.0 for t in own_tickers}
    shares_events: list[tuple[pd.Timestamp, dict[str, float]]] = []

    for _, row in tx.iterrows():
        if row["action"] == "buy":
            running_shares[row["ticker"]] += row["shares"]
        elif row["action"] == "sell":
            running_shares[row["ticker"]] -= row["shares"]
        else:
            continue  # "tax" verändert keine Bestände
        shares_events.append((row["date"], dict(running_shares)))

    calendar = build_calendar(*(prices[t] for t in own_tickers))

    shares_df = pd.DataFrame(index=calendar, columns=own_tickers, dtype=float)
    for t in own_tickers:
        events_t = [(d, snap[t]) for d, snap in shares_events]
        shares_df[t] = step_series_to_calendar(events_t, calendar)

    price_df = pd.DataFrame({t: prices[t].reindex(calendar).ffill().fillna(0.0) for t in own_tickers})
    value_series = (shares_df * price_df).sum(axis=1)

    net_flow = aggregate_net_flow(tx, include_tax=True)
    invested_series = step_series_to_calendar(
        list(pd.Series(net_flow).sort_index().cumsum().items()), calendar)

    return {
        "tickers": own_tickers,
        "value_series": value_series,
        "invested_series": invested_series,
        "calendar": calendar,
        "current_shares": dict(running_shares),
    }


# ----------------------------------------------------------------------
# Referenzvergleich: Buy&Hold-Simulation + Vorabpauschale
# ----------------------------------------------------------------------
def simulate_reference_buy_hold(ref_ticker: str, net_flow_by_date: dict[pd.Timestamp, float],
                                 price_series: pd.Series, years: range,
                                 own_value: pd.Series | None = None,
                                 own_invested: pd.Series | None = None) -> dict:
    """Simuliert eine Buy&Hold-Strategie im Referenz-Ticker mit den
    gegebenen Netto-Kapitalflüssen (siehe Docstring
    "Referenzvergleich (Buy&Hold)"). Verkäufe (negativer Netto-Fluss
    an einem Tag) werden FIFO aus den ältesten Lots bedient. Gibt u.a.
    die Vorabpauschale je Jahr zurück (VOR Anwendung von Sparer-
    Pauschbetrag/Steuersatz - das erfolgt zentral in
    apply_sparer_pauschbetrag_and_tax()).

    Liegt die Erstnotiz des Tickers (erster Handelstag von
    `price_series`) NACH dem ersten Kapitalfluss und sind `own_value`/
    `own_invested` (Depotwert/investiertes Kapital der eigenen
    Strategie) angegeben, gilt bis zur Erstnotiz die eigene Strategie
    als Proxy (siehe Docstring "Referenz-Ticker, die erst NACH dem ersten
    Kapitalfluss notiert wurden"). "value_series" und
    "invested_series_pre_tax" decken dann den gesamten Zeitraum ab,
    "plot_start" ist der Tag der Erstnotiz (sonst None)."""
    if price_series.empty:
        raise RuntimeError(f"Keine Kursdaten für Referenz-Ticker {ref_ticker} geladen.")

    listing_date = price_series.index[0]
    proxy_used = (own_value is not None and own_invested is not None
                  and bool(net_flow_by_date) and min(net_flow_by_date) < listing_date)
    own_value_at_listing = own_invested_at_listing = 0.0
    if proxy_used:
        own_value_at_listing = float(own_value.asof(listing_date))
        own_invested_at_listing = float(own_invested.asof(listing_date))
        # Umschichtung des gesamten Depotwerts am Tag der Erstnotiz; die
        # bis dahin angefallenen Kapitalflüsse sind darin enthalten.
        net_flow_by_date = {listing_date: own_value_at_listing,
                            **{d: f for d, f in net_flow_by_date.items() if d > listing_date}}

    lots: list[dict] = []  # {"date": Timestamp, "price": float, "shares": float}
    shares_events: list[tuple[pd.Timestamp, float]] = []
    flow_events: list[tuple[pd.Timestamp, float]] = []
    year_start_snapshot: dict[int, dict[int, float]] = {}

    dates_sorted = sorted(net_flow_by_date.keys())
    total_shares = 0.0
    last_seen_year: int | None = None

    for date in dates_sorted:
        if last_seen_year is None:
            year_start_snapshot[date.year] = {}
        elif date.year != last_seen_year:
            for y in range(last_seen_year + 1, date.year + 1):
                year_start_snapshot[y] = {i: lot["shares"] for i, lot in enumerate(lots)}
        last_seen_year = date.year

        flow = net_flow_by_date[date]
        price_today = price_near(price_series, date)
        if price_today is None or price_today <= 0:
            print(f"[warn] {ref_ticker}: kein Kurs nahe {date.date()} verfügbar - "
                  f"Kapitalfluss von {flow:.2f} EUR an diesem Tag wird ausgelassen.")
            continue

        if flow > 0:
            shares_bought = flow / price_today
            lots.append({"date": date, "price": price_today, "shares": shares_bought})
            total_shares += shares_bought
        elif flow < 0:
            remaining = -flow / price_today
            i = 0
            while remaining > 1e-9 and i < len(lots):
                take = min(lots[i]["shares"], remaining)
                lots[i]["shares"] -= take
                remaining -= take
                total_shares -= take
                i += 1

        shares_events.append((date, total_shares))
        flow_events.append((date, flow))

    if last_seen_year is not None:
        for y in range(last_seen_year, max(years) + 2):
            year_start_snapshot.setdefault(y + 1, {i: lot["shares"] for i, lot in enumerate(lots)})

    calendar = price_series.index
    shares_ts = step_series_to_calendar(shares_events, calendar)
    invested_pre_tax = step_series_to_calendar(
        list(pd.Series(dict(flow_events)).sort_index().cumsum().items()) if flow_events else [],
        calendar)
    value_series = shares_ts * price_series.reindex(calendar).ffill()

    if proxy_used:
        # Investiertes Kapital: Stand der eigenen Strategie zum Zeitpunkt
        # der Umschichtung statt des umgeschichteten Depotwerts.
        invested_pre_tax = invested_pre_tax - own_value_at_listing + own_invested_at_listing
        before = own_value.index < listing_date
        value_series = pd.concat([own_value.loc[before], value_series])
        invested_pre_tax = pd.concat([own_invested.loc[own_invested.index < listing_date], invested_pre_tax])
        calendar = value_series.index

    # --- Vorabpauschale je Jahr (vor Sparer-Pauschbetrag/Steuersatz) ---
    vorab_by_year: dict[int, dict] = {}
    for y in years:
        basiszins = BASISZINSSATZ_VORABPAUSCHALE.get(y)
        if basiszins is None:
            print(f"[warn] {ref_ticker}: kein Basiszins für {y} konfiguriert - "
                  f"Vorabpauschale {y} wird ausgelassen.")
            continue
        start_td = first_trading_day_on_or_after(price_series, pd.Timestamp(year=y, month=1, day=1))
        end_td = last_trading_day_on_or_before(price_series, pd.Timestamp(year=y, month=12, day=31))
        if start_td is None or end_td is None or start_td > end_td:
            continue

        price_start = float(price_series.loc[start_td])
        price_end = float(price_series.loc[end_td])
        snap_end = year_start_snapshot.get(y + 1, {i: lot["shares"] for i, lot in enumerate(lots)})

        vorab_total = 0.0
        for i, lot in enumerate(lots):
            shares_end = snap_end.get(i, 0.0)
            if shares_end <= 1e-9 or lot["date"] > end_td:
                continue
            if lot["date"] < start_td:
                basis_price, factor = price_start, 1.0
            else:
                basis_price, factor = lot["price"], (13 - lot["date"].month) / 12.0
            basisertrag = shares_end * basis_price * basiszins * 0.7 * factor
            wertzuwachs = shares_end * max(0.0, price_end - basis_price) * factor
            vorab_total += max(0.0, min(basisertrag, wertzuwachs))

        vorab_by_year[y] = {"vorabpauschale": vorab_total, "end_date": end_td}

    return {
        "value_series": value_series,
        "invested_series_pre_tax": invested_pre_tax,
        "vorabpauschale_by_year": vorab_by_year,
        "calendar": calendar,
        "plot_start": listing_date if proxy_used else None,
    }


def apply_sparer_pauschbetrag_and_tax(ref_results: dict[str, dict],
                                       reference_tickers: dict[str, dict],
                                       years: range) -> None:
    """Wendet Teilfreistellung, den VOLLEN Sparer-Pauschbetrag
    (SPARER_PAUSCHBETRAG_JAHR) und den Kapitalertragsteuersatz separat
    je Referenz-Ticker auf dessen Vorabpauschale an (siehe Docstring
    "Vorabpauschale") und schreibt daraus je Ticker eine um die
    resultierende Steuer erhöhte "invested_series" (analog zu einer
    "tax"-Aktion). Jeder Referenz-Ticker ist ein eigenständiges
    "was-wäre-wenn"-Szenario (als hätte man ausschließlich in diesen
    einen Ticker investiert) und bekommt deshalb den Freibetrag jeweils
    vollständig für sich - nicht anteilig mit den anderen Referenz-
    Tickern geteilt. `reference_tickers` ist das REFERENCE_TICKERS-Dict
    (Ticker -> {"name": ..., "teilfreistellung": ...})."""
    for y in years:
        for t, r in ref_results.items():
            if "invested_series" not in r:
                r["invested_series"] = r["invested_series_pre_tax"].copy()
                r["steuer_by_year"] = {}

            info = r["vorabpauschale_by_year"].get(y)
            if not info:
                continue
            tf = reference_tickers.get(t, {}).get("teilfreistellung", 0.30)
            steuerpflichtig = info["vorabpauschale"] * (1.0 - tf)
            taxable_after_allowance = max(0.0, steuerpflichtig - SPARER_PAUSCHBETRAG_JAHR)
            steuer = taxable_after_allowance * KAPITALERTRAGSTEUERSATZ
            r["steuer_by_year"][y] = {"steuerpflichtig": steuerpflichtig, "steuer": steuer}
            if steuer > 0:
                end_date = info["end_date"]
                r_series = r["invested_series"]
                r["invested_series"] = r_series.where(r_series.index < end_date, r_series + steuer)


# ----------------------------------------------------------------------
# Kennzahlen (gesamt + pro Jahr), gemeinsam für eigene Strategie und
# Referenz-Ticker verwendbar
# ----------------------------------------------------------------------
def compute_performance(value_series: pd.Series, invested_series: pd.Series) -> dict:
    """Siehe Docstring "Renditeberechnung"."""
    if value_series.empty:
        return {"total": None, "yearly": {}}

    total_invested = float(invested_series.iloc[-1])
    current_value = float(value_series.iloc[-1])
    return_sum = current_value - total_invested
    return_pct = return_sum / total_invested if total_invested else float("nan")

    start_date = value_series.index[0]
    end_date = value_series.index[-1]
    n_years = (end_date - start_date).days / 365.25
    if n_years > 0 and pd.notna(return_pct) and (1.0 + return_pct) > 0:
        return_pct_pa = (1.0 + return_pct) ** (1.0 / n_years) - 1.0
    else:
        return_pct_pa = float("nan")

    total = {
        "start_date": start_date,
        "end_date": end_date,
        "invested": total_invested,
        "value": current_value,
        "return_sum": return_sum,
        "return_pct": return_pct,
        "return_pct_pa": return_pct_pa,
    }

    yearly = {}
    for y in sorted(set(value_series.index.year)):
        year_dates = value_series.index[value_series.index.year == y]
        start_date, end_date = year_dates[0], year_dates[-1]
        prior_dates = value_series.index[value_series.index < start_date]

        value_start = float(value_series.loc[prior_dates[-1]]) if len(prior_dates) else 0.0
        invested_start = float(invested_series.loc[prior_dates[-1]]) if len(prior_dates) else 0.0
        value_end = float(value_series.loc[end_date])
        invested_end = float(invested_series.loc[end_date])

        net_flow_year = invested_end - invested_start
        return_sum_y = value_end - value_start - net_flow_year
        denom = value_start + net_flow_year
        return_pct_y = return_sum_y / denom if denom else float("nan")

        yearly[y] = {
            "value_start": value_start, "value_end": value_end,
            "net_flow": net_flow_year,
            "return_sum": return_sum_y, "return_pct": return_pct_y,
        }

    return {"total": total, "yearly": yearly}


# ----------------------------------------------------------------------
# Text-Auswertung
# ----------------------------------------------------------------------
def fmt_eur(x: float) -> str:
    return f"{x:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(x: float) -> str:
    return f"{x:+.2%}" if pd.notna(x) else "n/a"


def write_own_perf_block(lines: list[str], perf: dict, ref_perf: dict[str, dict],
                          current_shares: dict[str, float],
                          reference_tickers: dict[str, dict],
                          ref_listing: dict[str, pd.Timestamp] | None = None) -> None:
    """Schreibt die Kennzahlen der eigenen Strategie (gesamt + pro
    Jahr), die aktuell gehaltenen Shares je Ticker, und stellt daneben
    - nur als Rendite (%) - die Referenz-Ticker (Buy&Hold) zum
    Vergleich dar. `reference_tickers` ist das REFERENCE_TICKERS-Dict
    (Ticker -> {"name": ..., ...}), dessen "name" hier ausschließlich
    für die Anzeige verwendet wird. `ref_listing` ordnet Referenz-
    Tickern, die erst nach dem ersten Kapitalfluss notiert wurden, ihre
    Erstnotiz zu (diese Ticker werden mit "*" markiert)."""
    ref_listing = ref_listing or {}
    title = "Eigene Strategie"
    lines.append(title)
    lines.append("-" * len(title))
    total = perf["total"]
    if total is None:
        lines.append("  Keine Daten verfügbar.\n")
        return

    lines.append(f"  Zeitraum: {total['start_date'].date()} - {total['end_date'].date()}")
    lines.append(f"  Investiertes Kapital (netto, aktuell): {fmt_eur(total['invested'])}")
    lines.append(f"  Aktueller Depotwert:                   {fmt_eur(total['value'])}")
    lines.append(f"  Rendite (Summe):                       {fmt_eur(total['return_sum'])}")
    lines.append(f"  Rendite (%):                            {fmt_pct(total['return_pct'])}")
    lines.append(f"  Rendite p.a. (%):                       {fmt_pct(total['return_pct_pa'])}")

    held = {t: sh for t, sh in current_shares.items() if abs(sh) > 1e-6}
    if held:
        lines.append("")
        lines.append("  Aktuell gehaltene Shares:")
        for t, sh in held.items():
            lines.append(f"    {t:<12}{sh:>18,.6f}")

    ref_tickers = list(ref_perf.keys())
    if ref_tickers:
        lines.append("")
        lines.append("  Zum Vergleich - Buy&Hold im Referenz-Ticker (gesamter Zeitraum, "
                      "siehe Docstring 'Referenzvergleich'):")

        # Feste Spaltenbreiten (Ticker | Name | Rendite (Summe) |
        # Rendite (%) | Rendite p.a. (%)), damit unterschiedlich lange
        # ETF-Namen nicht zu Spaltenverschiebungen zwischen den Zeilen
        # führen (analog zur Momentum-Tabelle in canary.py). Lange
        # Namen werden mit "…" gekürzt.
        cmp_ticker_col = max(10, max(len(t) for t in ref_tickers) + 1)
        cmp_name_col_max = 34
        cmp_name_col = min(cmp_name_col_max,
                            max(len(reference_tickers.get(t, {}).get("name", t))
                                for t in ref_tickers))

        def _cmp_name(name: str) -> str:
            if len(name) > cmp_name_col:
                return name[: cmp_name_col - 1] + "…"
            return name

        header = (f"    {'Ticker':<{cmp_ticker_col}}{'Name':<{cmp_name_col}}  "
                  f"{'Rendite (Summe)':>18}{'Rendite (%)':>14}{'Rendite p.a. (%)':>18}")
        lines.append(header)
        for t in ref_tickers:
            name = reference_tickers.get(t, {}).get("name", t)
            t_total = ref_perf[t]["total"]
            sum_str = fmt_eur(t_total["return_sum"]) if t_total else "n/a"
            pct = fmt_pct(t_total["return_pct"]) if t_total else "n/a"
            pct_pa = fmt_pct(t_total["return_pct_pa"]) if t_total else "n/a"
            lines.append(f"    {t:<{cmp_ticker_col}}{_cmp_name(name):<{cmp_name_col}}  "
                          f"{sum_str:>18}{pct:>14}{pct_pa:>18}" + (" *" if t in ref_listing else ""))
        for t, listing in ref_listing.items():
            lines.append(f"    * {t}: erst seit {listing.date()} notiert - bis dahin gilt die "
                          f"eigene Strategie als Proxy.")

    lines.append("")
    lines.append("  Pro Jahr:")
    header = (f"    {'Jahr':<6}{'Wert Jahresanf.':>18}{'Wert Jahresende':>18}"
              f"{'Netto-Zufluss':>16}{'Rendite (Summe)':>18}{'Rendite (%)':>14}")
    for t in ref_tickers:
        header += f"{('Ref. ' + t + ('*' if t in ref_listing else '') + ' (%)'):>18}"
    lines.append(header)

    for y, info in perf["yearly"].items():
        line = (f"    {y:<6}{info['value_start']:>18,.2f}{info['value_end']:>18,.2f}"
                f"{info['net_flow']:>16,.2f}{info['return_sum']:>18,.2f}"
                f"{fmt_pct(info['return_pct']):>14}")
        for t in ref_tickers:
            y_info = ref_perf[t]["yearly"].get(y)
            pct = fmt_pct(y_info["return_pct"]) if y_info else "n/a"
            line += f"{pct:>18}"
        lines.append(line)
    lines.append("")


def write_results_txt(csv_path: Path, own_perf: dict, ref_perf: dict[str, dict],
                       current_shares: dict[str, float],
                       reference_tickers: dict[str, dict],
                       ref_listing: dict[str, pd.Timestamp] | None = None) -> None:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"Depot-Auswertung: {csv_path.name}")
    lines.append(f"Erstellt: {datetime.now(BERLIN_TZ).strftime('%Y-%m-%d %H:%M:%S')} (Berlin)")
    lines.append("=" * 70)
    lines.append("")

    write_own_perf_block(lines, own_perf, ref_perf, current_shares, reference_tickers, ref_listing)

    if not BASISZINSSATZ_VORABPAUSCHALE:
        lines.append("[Hinweis] BASISZINSSATZ_VORABPAUSCHALE ist leer konfiguriert - die "
                      "Vorabpauschale wurde für KEIN Jahr berücksichtigt (wirkt sich auf "
                      "die Referenz-Renditen oben aus). Bitte im Skript die Basiszinssätze "
                      "der betroffenen Jahre ergänzen.")

    out_path = output_path(csv_path, RESULTS_FILENAME)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] Textauswertung geschrieben: {out_path}")


# ----------------------------------------------------------------------
# Plots
# ----------------------------------------------------------------------
def _return_abs_series(value_series: pd.Series, invested_series: pd.Series) -> pd.Series:
    """Absolute Rendite (Rendite (Summe) in EUR) über die Zeit:
    Depotwert - investiertes Kapital, je Handelstag - dieselbe
    Definition wie die in compute_performance() berechnete
    Gesamtrendite (Summe), nur für jeden Tag statt nur für das
    Periodenende. Im Gegensatz zu einer Rendite in % gibt es hier
    keinen Verwässerungseffekt durch neue Kapitalzuflüsse."""
    return value_series - invested_series


def _plot_slice(series: pd.Series, ref_result: dict) -> pd.Series:
    """Ab der Erstnotiz des Referenz-Tickers (falls die eigene Strategie
    davor als Proxy diente, siehe simulate_reference_buy_hold()),
    sonst die gesamte Serie."""
    plot_start = ref_result.get("plot_start")
    return series if plot_start is None else series.loc[series.index >= plot_start]


def _ref_label(t: str, name: str, ref_result: dict) -> str:
    plot_start = ref_result.get("plot_start")
    suffix = f" [ab {plot_start.date()}]" if plot_start is not None else ""
    return f"Buy & Hold: ({t}) {name}{suffix}"


def _plot_colors(reference_tickers: dict[str, dict],
                  ref_results: dict[str, dict]) -> tuple[str, str, dict[str, str]]:
    """Liefert feste Farben für 'Depotwert'/'Eigene Strategie',
    'Investiertes Kapital' sowie je Referenz-Ticker, damit deposit.png
    und return.png dieselbe Farbzuordnung verwenden - unabhängig davon,
    dass "Investiertes Kapital" nur im deposit-Plot vorkommt und die
    Farbvergabe sonst verschieben würde. Reihenfolge der Referenz-Ticker
    richtet sich nach `reference_tickers` (Konfigurationsreihenfolge),
    damit sie in beiden Plots identisch ist."""
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    own_color = colors[0]
    invested_color = colors[1]
    ordered_tickers = [t for t in reference_tickers if t in ref_results]
    ref_colors = {t: colors[(2 + i) % len(colors)] for i, t in enumerate(ordered_tickers)}
    return own_color, invested_color, ref_colors


def _render_deposit_plot(csv_path: Path, own: dict, ref_results: dict[str, dict],
                          reference_tickers: dict[str, dict]) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    own_color, invested_color, ref_colors = _plot_colors(reference_tickers, ref_results)

    ax.plot(own["value_series"].index, own["value_series"].values,
            label="Depotwert", linewidth=2, color=own_color)
    ax.plot(own["invested_series"].index, own["invested_series"].values,
            label="Investiertes Kapital", linewidth=1.5, color=invested_color)

    for t, r in ref_results.items():
        name = reference_tickers.get(t, {}).get("name", t)
        ref_value = _plot_slice(r["value_series"], r)
        ax.plot(ref_value.index, ref_value.values,
                label=_ref_label(t, name, r), linewidth=1.0, linestyle="--",
                alpha=0.85, color=ref_colors[t])

    ax.set_yscale("log")
    ax.set_ylabel("EUR (log. Skala)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_xlabel("Datum")
    ax.set_title(f"Depotverlauf: {csv_path.stem}")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()

    out_path = output_path(csv_path, PLOT_FILENAME_DEPOSIT)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[ok] Plot geschrieben: {out_path}")


def _render_return_plot(csv_path: Path, own: dict, ref_results: dict[str, dict],
                         reference_tickers: dict[str, dict]) -> None:
    """Plot der absoluten Rendite (Rendite (Summe) in EUR, lineare
    y-Achse) über die Zeit (eigene Strategie + jeder Referenz-Ticker),
    siehe _return_abs_series()."""
    fig, ax = plt.subplots(figsize=(12, 7))
    own_color, _invested_color, ref_colors = _plot_colors(reference_tickers, ref_results)

    own_return = _return_abs_series(own["value_series"], own["invested_series"])
    ax.plot(own_return.index, own_return.values,
            label="Eigene Strategie", linewidth=2, color=own_color)

    for t, r in ref_results.items():
        name = reference_tickers.get(t, {}).get("name", t)
        ref_return = _plot_slice(_return_abs_series(r["value_series"], r["invested_series"]), r)
        ax.plot(ref_return.index, ref_return.values,
                label=_ref_label(t, name, r), linewidth=1.0, linestyle="--",
                alpha=0.85, color=ref_colors[t])

    ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
    ax.set_ylabel("Rendite (Summe, EUR)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_xlabel("Datum")
    ax.set_title(f"Renditeverlauf: {csv_path.stem}")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()

    out_path = output_path(csv_path, PLOT_FILENAME_RETURN)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[ok] Plot geschrieben: {out_path}")


def plot_depotverlauf(csv_path: Path, own: dict, ref_results: dict[str, dict],
                       reference_tickers: dict[str, dict]) -> None:
    """Erstellt zwei Plots: den Depotverlauf in EUR (logarithmische
    y-Achse, "deposit.png") sowie den Verlauf der absoluten Rendite in
    EUR (lineare y-Achse, "return.png") - beide im nach der CSV-Datei
    benannten Unterordner. In beiden Plots ist die eigene Strategie
    jeweils eine durchgehende (dickere) Linie, die Referenz-Ticker
    (Buy&Hold) jeweils gestrichelt und dünner."""
    _render_deposit_plot(csv_path, own, ref_results, reference_tickers)
    _render_return_plot(csv_path, own, ref_results, reference_tickers)


# ----------------------------------------------------------------------
# Verarbeitung einer einzelnen CSV-Datei
# ----------------------------------------------------------------------
def process_csv(csv_path: Path, tx: pd.DataFrame, all_prices: dict[str, pd.Series],
                 query_end_date: pd.Timestamp) -> None:
    """Wertet eine bereits eingelesene CSV-Datei aus. `all_prices`
    enthält die für ALLE CSV-Dateien gemeinsam vorab geladene
    Kurshistorie (siehe main()) - jede Ticker-Serie wird hier lediglich
    auf das für DIESE CSV tatsächlich benötigte Startdatum
    zurechtgeschnitten (ab dem ersten Transaktionsdatum), nicht erneut
    abgefragt."""
    print(f"\n=== Auswertung {csv_path.name} ===")

    own_tickers = sorted(tx.loc[tx["action"].isin(["buy", "sell"]), "ticker"].unique())
    start_date = tx["date"].min()

    all_tickers = sorted(set(own_tickers) | set(REFERENCE_TICKERS.keys()))
    prices: dict[str, pd.Series] = {}
    for t in all_tickers:
        full_series = all_prices[t]
        series = full_series.loc[full_series.index >= start_date]
        if series.empty:
            raise RuntimeError(f"Keine Kursdaten für {t} ab {start_date.date()} vorhanden.")
        prices[t] = series

    own = build_own_strategy(tx, prices)
    own_perf = compute_performance(own["value_series"], own["invested_series"])

    years = range(start_date.year, query_end_date.year + 1)
    contribution_flow = aggregate_net_flow(tx, include_tax=False)

    ref_results: dict[str, dict] = {}
    for ref_ticker in REFERENCE_TICKERS:
        ref_results[ref_ticker] = simulate_reference_buy_hold(
            ref_ticker, contribution_flow, prices[ref_ticker], years,
            own_value=own["value_series"], own_invested=own["invested_series"])

    apply_sparer_pauschbetrag_and_tax(ref_results, REFERENCE_TICKERS, years)

    ref_perf = {
        t: compute_performance(r["value_series"], r["invested_series"])
        for t, r in ref_results.items()
    }

    ref_listing = {t: r["plot_start"] for t, r in ref_results.items() if r["plot_start"] is not None}
    write_results_txt(csv_path, own_perf, ref_perf, own["current_shares"], REFERENCE_TICKERS,
                      ref_listing)
    plot_depotverlauf(csv_path, own, ref_results, REFERENCE_TICKERS)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    warnings.filterwarnings("ignore", category=FutureWarning)
    now_berlin = datetime.now(BERLIN_TZ)
    query_end_date = compute_query_end_date(now_berlin)
    print(f"Aktuelle Zeit: {now_berlin.strftime('%Y-%m-%d %H:%M:%S')} (Berlin) / "
          f"{now_berlin.astimezone(NEW_YORK_TZ).strftime('%H:%M')} (New York)")
    print(f"Abfrage-Enddatum (Kurse): {query_end_date.date()}")

    script_dir = Path(__file__).resolve().parent
    csv_dir = script_dir / CSV_SUBDIR
    csv_files = sorted(p for p in csv_dir.glob("*.csv"))
    if not csv_files:
        print(f"Keine CSV-Dateien in {csv_dir} gefunden.")
        return

    # --- Alle CSV-Dateien vorab einlesen (aber noch nicht auswerten),
    #     um den gemeinsamen Ticker-Bedarf und das früheste benötigte
    #     Startdatum über ALLE Dateien hinweg zu ermitteln. Jeder
    #     benötigte Ticker wird dadurch nur EIN einziges Mal abgefragt
    #     (mit einem Fenster, das alle CSV-Dateien abdeckt), auch wenn
    #     mehrere CSV-Dateien denselben Ticker verwenden (z.B. alle
    #     konfigurierten REFERENCE_TICKERS oder ein Ticker, der in
    #     mehreren Depots vorkommt) - statt ihn je Datei erneut
    #     herunterzuladen.
    tx_by_csv: dict[Path, pd.DataFrame] = {}
    for csv_path in csv_files:
        try:
            tx_by_csv[csv_path] = parse_transactions(csv_path)
        except Exception as exc:  # eine fehlerhafte Datei soll die anderen nicht blockieren
            print(f"[error] {csv_path.name}: {exc}")

    if not tx_by_csv:
        return

    global_start_date = min(tx["date"].min() for tx in tx_by_csv.values())
    own_tickers_all: set[str] = set()
    for tx in tx_by_csv.values():
        own_tickers_all |= set(tx.loc[tx["action"].isin(["buy", "sell"]), "ticker"].unique())
    all_tickers = sorted(own_tickers_all | set(REFERENCE_TICKERS.keys()))

    print(f"\nLade Kurshistorie für {len(all_tickers)} Ticker ab "
          f"{global_start_date.date()} (deckt alle {len(tx_by_csv)} CSV-Datei(en) ab)...")

    all_prices: dict[str, pd.Series] = {}
    price_errors: dict[str, Exception] = {}
    for t in all_tickers:
        try:
            series, dropped_today = load_prices(t, global_start_date, query_end_date)
            if series.empty:
                raise RuntimeError(f"Keine Kursdaten für {t} geladen (leere Kursreihe).")
            if dropped_today:
                print(f"[info] {t}: heutiger Kurs verworfen (Sicherheitsregel, siehe "
                      f"Docstring), letzter berücksichtigter Handelstag: "
                      f"{series.index[-1].date()}")
            all_prices[t] = series
        except Exception as exc:
            price_errors[t] = exc

    for csv_path, tx in tx_by_csv.items():
        try:
            needed = (set(tx.loc[tx["action"].isin(["buy", "sell"]), "ticker"].unique())
                      | set(REFERENCE_TICKERS.keys()))
            failed = needed & price_errors.keys()
            if failed:
                raise price_errors[sorted(failed)[0]]
            process_csv(csv_path, tx, all_prices, query_end_date)
        except Exception as exc:  # eine fehlerhafte Datei soll die anderen nicht blockieren
            print(f"[error] {csv_path.name}: {exc}")


if __name__ == "__main__":
    main()
