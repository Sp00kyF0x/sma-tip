"""
Gemeinsame Kursdaten-Lade-Logik für status.py, stats.py und backtest.py
=============================================================================

Dieses Modul bündelt die yfinance-Download-Logik für alle drei Skripte an
einer Stelle, damit Anpassungen (Bugfixes, neue Sicherheitsnetze, ...) nur
einmal gemacht werden müssen und automatisch für alle drei Skripte gelten.

Es gibt keinen Datei-Cache: Jeder Aufruf lädt frisch von Yahoo Finance.
Grund: Yahoo Finance korrigiert Adj-Close-Werte gelegentlich rückwirkend
(z.B. wenn nachträglich Dividenden/Splits eingepreist werden) - ein Cache
würde solche Korrekturen dauerhaft verpassen.

Stattdessen sorgen sechs zusammenwirkende Mechanismen für robuste, ein-
heitliche Kursreihen bei nur EINEM Abruf pro Aufruf von get_price_history():

  1. Persistente Ticker-Historie mit Werten als Regressions-Schutz UND
     Lückenfüller (siehe KNOWN_VALUES_DIR, _load_known_values()/
     _save_known_values()/_reconcile_known_gaps()/
     _purge_known_values()): für jeden Ticker wird in einer eigenen
     Textdatei unter KNOWN_VALUES_DIR zu jedem Handelstag, für den wir
     jemals tatsächlich einen Kurs von Yahoo erhalten haben, das Datum
     und der zugehörige, UNVERÄNDERTE (roh, d.h. NICHT gemäß Punkt 6
     kurssprung-korrigierte) Adj-Close-Wert geführt ("ISO-Datum,Wert"
     pro Zeile, sortiert). Diese Werte werden bei jedem Abruf mit den
     diesmal tatsächlich von Yahoo gelieferten Werten aktualisiert
     (überschreibt bereits bekannte Tage mit dem neuesten Stand, fügt
     neue Tage hinzu) - so kommen auch rückwirkende Kurskorrekturen an,
     statt an einem alten Stand festzuhalten.
       Bei jedem Abruf wird geprüft, ob alle für das angefragte Fenster
     bereits bekannten Handelstage auch diesmal geliefert wurden. Fehlt
     einer davon, wird versucht, ihn aus dem gespeicherten Wert
     aufzufüllen - aber nur nach einer Plausibilitätsprüfung: Wäre die
     Historie rund um den fehlenden Tag inzwischen von Yahoo
     nachträglich angepasst worden, wäre der gespeicherte Wert für
     genau diesen Tag vermutlich ebenfalls veraltet, und ihn einfach
     wiederzuverwenden würde einen Bruch in der Kursreihe einbauen (ein
     Tag auf altem Anpassungsstand zwischen lauter Tagen auf neuem
     Stand). Die Prüfung: gesucht wird - unabhängig davon, ob er im
     aktuellen Download auftaucht - je Seite (davor/danach, je nach
     Position im angefragten Fenster) der NÄCHSTE bereits LOKAL
     bekannte Handelstag; er zählt nur als Vergleichsbasis, wenn er
     auch im aktuellen Download tatsächlich vorhanden ist (sonst fehlt
     die Grundlage für einen Vergleich). Stimmen alle so gefundenen
     Nachbarn EXAKT mit ihrem gespeicherten Wert überein (keine
     Toleranzschwelle - beim Schreiben wird volle float-Präzision
     verwendet, ein exakter Vergleich ist damit zuverlässig, siehe
     _save_known_values()), gilt die Umgebung als stabil und der
     gespeicherte Wert für den fehlenden Tag wird übernommen. Weicht
     dagegen mindestens ein gefundener Nachbar ab, oder lässt sich gar
     kein Nachbar finden, der aktuell überprüfbar ist (z.B. weil der
     nächste lokal bekannte Nachbartag diesmal selbst nicht mitgeliefert
     wurde, oder bei einem extrem schmalen Abfragefenster), gilt der
     gespeicherte Wert für den fehlenden Tag als nicht mehr
     vertrauenswürdig: er wird NICHT übernommen, sondern aus der
     persistenten Historie entfernt (siehe _purge_known_values() - die
     einzige Ausnahme von "es wird nie etwas entfernt") - KEIN
     RuntimeError, KEIN Abbruch des Laufs. Die dadurch entstehende
     Lücke wird wie jede andere, noch nie bestätigte Lücke von Punkt 2-4
     behandelt (i.d.R. per linearer Interpolation geschlossen, sofern
     echte Werte davor und danach vorliegen). Ein abweichender Nachbar
     wird zusätzlich mit einer `[warn]`-Zeile gemeldet, da das auf eine
     echte rückwirkende Kursanpassung durch Yahoo hindeuten kann (im
     Unterschied zum reinen "kein Nachbar überprüfbar"-Fall, der nur ein
     `[info]` erhält, da er im normalen Rollen des Abfragefensters
     regelmäßig und harmlos auftritt).
       Liefert Yahoo dagegen mehr/andere Handelstage als bisher bekannt
     (z.B. der aktuelle Tag, oder ein zuvor fehlender Tag ist nun doch
     vorhanden), werden diese einfach als neue/aktualisierte bestätigte
     Handelstage übernommen.

  2. Vollständigkeitsprüfung gegen den echten Börsenkalender (siehe
     get_price_history()/_missing_trading_days()) für Handelstage, die
     wir noch nie gesehen haben (also von Punkt 1 nicht erfasst werden,
     z.B. beim allerersten Abruf eines Tickers): die geladene Kursreihe
     wird gegen den tatsächlichen Handelskalender der jeweiligen Börse
     geprüft (Bibliothek `pandas_market_calendars`, z.B. Kalender
     "NYSE" oder "XETR"). Der Kalendername wird dabei intern und
     automatisch über calendar_for_ticker() (siehe unten, anhand des
     Yahoo-Finance-Börsenplatz-Suffixes) ermittelt - der Aufrufer muss
     ihn nicht kennen oder übergeben, und canary.py, backtest.py und
     stats.py müssen hierfür keine eigene, potenziell abweichende
     Logik pflegen. Eine hier erkannte Lücke führt NICHT zum Abbruch, sondern
     zur Interpolation (siehe Punkt 4). Ein einzelner fehlender Tag
     ganz am Ende des angefragten Fensters (kein "danach"-Anker für
     eine Interpolation verfügbar) bleibt dabei
     dabei ohne Fehler oder Warnung einfach im Ergebnis aus (siehe
     Punkt 4).

     Es gibt keinen Wert-für-Wert-Vergleich einzelner Kurse zwischen
     Abrufen: die Prüfung beschränkt sich auf Vollständigkeit (welche
     Handelstage sind vorhanden) - der heutige, ggf. noch nicht final
     abgerechnete Kurs kann sich zwischen Abrufen legitim ändern, ohne
     dass das als Fehler gilt.

  3. Berücksichtigung von Börsengang/Erstnotiz (siehe
     _unexplained_missing_days()): ohne weitere Behandlung würde die
     Kalenderprüfung (Punkt 2) bei Tickern, die erst INNERHALB des
     angefragten Zeitraums an die Börse gegangen sind, die Handelstage
     VOR dem Börsengang fälschlich als "fehlende Daten" melden. Um das
     zu vermeiden:
       a) Bevorzugt wird das von Yahoo selbst mitgelieferte
          Erstnotiz-Datum genutzt (Metadatenfeld "firstTradeDate" der
          Chart-API, kommt ohne Zusatz-Request in derselben Antwort wie
          die Kursdaten mit, siehe _download_once()/
          _first_trade_date_from_metadata()). Das erwartete Fenster für
          die Vollständigkeitsprüfung wird dann automatisch auf
          [firstTradeDate, ...] statt [start_date, ...] verkürzt.
       b) Fallback, falls Yahoo kein "firstTradeDate" liefert: eine
          Lücke wird nur dann als plausibler Börsengang (und nicht als
          Datenfehler) akzeptiert, wenn ALLE fehlenden Handelstage
          VOR dem ersten tatsächlich gelieferten Kurs liegen (also ein
          einzelner zusammenhängender Block am Anfang des Fensters,
          keine Lücke MITTEN in oder NACH den vorhandenen Daten).

  4. Interpolation für genuin neue Lücken (siehe
     _interpolate_missing_days()): Handelstage, die laut Kalender
     (Punkt 2) fehlen, aber noch nie zuvor bekannt waren (für die also
     auch kein gespeicherter Wert existiert und Punkt 1 daher nicht
     greifen kann), werden - OHNE Größenlimit, auch mehrtägige/
     mehrwöchige Lücken - per linearer Interpolation zwischen den
     jeweils nächstgelegenen tatsächlich vorhandenen Adj-Close-Werten
     geschlossen, statt einen Fehler zu werfen - `yfinance`s eigenes
     "price repair"-Feature hilft hier NICHT, da es nur vorhandene,
     aber leere/fehlerhafte Werte repariert, keine komplett fehlenden
     Zeilen. Ein fehlender Tag ganz am Rand des angefragten Fensters,
     für den es auf einer Seite keinen tatsächlich vorhandenen
     Nachbarwert gibt, kann nicht interpoliert werden und bleibt ohne
     Fehler oder Warnung im Ergebnis aus. Interpolierte Tage werden
     NICHT in die persistente Ticker-Historie (Punkt 1) aufgenommen,
     damit sie bei zukünftigen Abrufen nicht fälschlich als "bekannt,
     aber fehlend" gewertet werden, falls Yahoo sie weiterhin nicht
     liefert.

  5. Datenvalidierung (siehe _check_and_clean()):
     - Inf/-Inf in Adj Close -> harter Fehler (Datenkorruption).
     - Adj Close <= 0 -> harter Fehler (Datenkorruption).
     - Interne NaN-Zeilen -> Warnung + Entfernen.
     - Doppelte Datums-Indizes -> Warnung + Entfernen (letzter Eintrag
       gewinnt).
     - Randständige NaN-Adj-Close-Zeilen (Yahoo hat den bereinigten
       Kurs des jüngsten Handelstags manchmal noch nicht fertig
       berechnet) -> werden abgeschnitten (_trim_trailing_nan_adjclose),
       damit sie nicht als valider "aktuellster" Kurs durchgehen.

  6. Automatische Erkennung und Korrektur extremer Kurssprünge (siehe
     PRICE_JUMP_FACTOR_THRESHOLD, _detect_and_correct_price_jumps()):
     Yahoo passt Adj-Close-Werte gelegentlich nicht korrekt rückwirkend
     an eine Kapitalmaßnahme (z.B. Reverse Split, Anteilszusammenlegung)
     an, oder liefert für einen oder mehrere Tage einen offensichtlich
     falschen Kurs. Für jeden Download wird das Verhältnis von Adj Close
     zwischen zwei aufeinanderfolgenden, tatsächlich vorhandenen
     Datenpunkten geprüft; überschreitet es PRICE_JUMP_FACTOR_THRESHOLD
     (Faktor 5, bewusst weit über jeder plausiblen eintägigen
     Marktbewegung), wird der Sprung AUTOMATISCH korrigiert: alle Werte
     VOR dem Sprungdatum werden mit dem Faktor dieses Übergangs
     skaliert, sodass die Reihe nahtlos anschließt (die Tagesrendite des
     Sprungtages wird dadurch zu 0 %). Der Faktor wird bei jedem Abruf
     frisch aus den beiden angrenzenden Werten berechnet, nie fest
     hinterlegt. Eine manuell gepflegte Liste bestätigter Sprünge
     oder einen Abbruch bei unbekannten Sprüngen gibt es nicht mehr.
       Das deckt beide Fälle ab: (a) dauerhafter Niveausprung (z.B.
     Faktor ~282 bei 18MF.DE am 02.01.2013): die Reihe davor wird auf
     das neue Niveau skaliert; (b) vorübergehend falsche Kurse (ein
     oder mehrere Tage, danach wieder normal): Hin- und Rücksprung
     heben sich bei der Skalierung auf - die Tage davor behalten ihr
     Niveau, die falschen Tage werden auf das normale Niveau
     zurückskaliert. Ein Sprung am allerletzten Datenpunkt lässt sich
     noch nicht von einem Ausreißer unterscheiden; die Kennzahlen aus
     Kursverhältnissen (Momentum, Kurs/SMA) bleiben auch dann richtig,
     nur der Absolutwert des letzten Kurses kann falsch sein.
       Jede Korrektur wird gemeldet: als `[warn]`, wenn der Sprung
     innerhalb der letzten JUMP_WARN_RECENT_ROWS Datenpunkte liegt (also
     die aktuelle Auswertung betreffen kann), sonst als `[info]`.
       Die Korrektur wirkt NUR auf die von get_price_history()
     zurückgegebene (und für Interpolation/Ausgabe verwendete)
     Kursreihe - die unter Punkt 1 persistierte Historie speichert
     weiterhin die unveränderten Rohwerte. Die Regressionsprüfung aus
     Punkt 1 läuft entsprechend VOR dieser Korrektur (Rohwerte gegen
     Rohwerte), die Kalender-Vollständigkeitsprüfung/Interpolation aus
     Punkt 2 NACH dieser Korrektur (auf der bereits durchgängigen
     Skala).

Sicherer Auswertungszeitpunkt (SAFE_EVALUATION_TIME_NY):
  Maßgeblich ist die New Yorker Zeit (NYSE/Nasdaq-Handelsschluss 16:00
  Uhr Ortszeit): Vor 16:05 Uhr New Yorker Zeit wird als Abfrage-Ende nur
  der letzte VOLLSTÄNDIGE Handelstag verwendet (statt eines unfertigen
  Intraday-Standes, siehe compute_query_end_date()). Die Funktion
  akzeptiert eine beliebige zeitzonenbehaftete aktuelle Zeit (z.B.
  datetime.now(BERLIN_TZ)) und rechnet sie selbst nach New York um; das
  gilt auch in den Wochen, in denen sich die Sommerzeit-Umstellungen
  der USA und Europas unterscheiden. Zusätzlich abgesichert durch
  drop_unsafe_todays_bar() auf jeder von load_prices() gelieferten
  Kursreihe (entfernt den heutigen Balken, falls doch einer zurückkäme
  und die New Yorker Uhrzeit noch vor dem Cutoff liegt) - die dafür
  benötigte aktuelle Zeit ermittelt load_prices() dabei selbst
  (datetime.now(BERLIN_TZ)), der Aufrufer muss sie hierfür nicht
  übergeben.

Verwendung in einem Skript:
    from yf_data import (
        BERLIN_TZ, NEW_YORK_TZ, SAFE_EVALUATION_TIME_NY,
        previous_business_day, compute_query_end_date,
        get_price_history, drop_unsafe_todays_bar, load_prices,
    )
    # load_prices() übernimmt sowohl die Wahl des Börsenkalenders
    # (zentral über calendar_for_ticker() anhand des
    # Yahoo-Finance-Börsenplatz-Suffixes, siehe
    # GERMAN_EXCHANGE_CALENDAR_BY_SUFFIX oben) als auch die Ermittlung
    # der aktuellen Berliner Zeit für den Sicherheits-Cutoff intern -
    # der Aufrufer übergibt nur noch Ticker und Zeitfenster:
    #   load_prices(ticker, start_date, query_end_date)
    # Gültige Kalendernamen: pandas_market_calendars.get_calendar_names().

Persistente Ticker-Historie:
    Liegt unter KNOWN_VALUES_DIR (Unterordner "yf_data" neben dieser
    Datei), eine Textdatei pro Ticker ("ISO-Datum,Adj-Close-Wert" pro
    Zeile, sortiert). Diese Dateien sollten NICHT von Hand bearbeitet
    werden - Einträge daraus zu entfernen hebt den Regressions-/
    Auffüll-Schutz für genau diese Handelstage auf. Zeilen ohne Komma
    (z.B. ein leeres Verzeichnis oder eine leere Datei) werden beim
    Einlesen ignoriert; existiert für einen Ticker noch keine Datei,
    wird das wie eine leere Historie behandelt (kein Fehler).
"""

from __future__ import annotations

from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import numpy as np
    import pandas as pd
    import yfinance as yf
    import pandas_market_calendars as mcal
except ImportError as exc:
    print(f"Fehler: Benötigtes Paket nicht gefunden ({exc.name}).\n"
          f"Bitte einmalig ausführen: pip install -r requirements.txt")
    raise SystemExit(1) from None

# ----------------------------------------------------------------------
# Konfiguration (für alle drei Skripte identisch)
# ----------------------------------------------------------------------
# Frühester Zeitpunkt (New Yorker Ortszeit), ab dem der Schlusskurs des
# heutigen Handelstags als final gilt: 5 Minuten nach dem US-Handelsschluss
# um 16:00 Uhr. In deutscher Zeit entspricht das meist 22:05 Uhr, in den
# Wochen mit abweichender Sommerzeit-Umstellung 21:05 Uhr.
SAFE_EVALUATION_TIME_NY = dt_time(16, 5)
NEW_YORK_TZ = ZoneInfo("America/New_York")
BERLIN_TZ = ZoneInfo("Europe/Berlin")

# Verzeichnis für die persistente, tickerweise Historie bereits
# bestätigter Handelstage MIT ihrem jeweiligen Adj-Close-Wert (siehe
# Modul-Docstring Punkt 1 und _load_known_values()/_save_known_values()).
# Liegt neben dieser Datei, unabhängig vom Arbeitsverzeichnis, aus dem
# ein Skript gestartet wird.
KNOWN_VALUES_DIR = Path(__file__).resolve().parent / "yf_data"

# Extremer Kurssprung: Verhältnis von Adj Close an zwei aufeinander-
# folgenden, tatsächlich vorhandenen Datenpunkten desselben Downloads,
# ab dem ein Tag als Datenfehler (z.B. unbereinigter Reverse Split,
# falscher Kurs) gilt und automatisch korrigiert wird (siehe Modul-
# Docstring Punkt 6 und _detect_and_correct_price_jumps()). Bewusst
# sehr großzügig gewählt - selbst ein hoch gehebelter ETF bewegt sich
# an einem einzelnen Handelstag nie in die Nähe von Faktor 5.
PRICE_JUMP_FACTOR_THRESHOLD = 5.0

# Liegt ein korrigierter Sprung innerhalb der letzten so vielen
# Datenpunkte, wird er als `[warn]` (statt `[info]`) gemeldet, da er die
# aktuelle Auswertung betreffen kann.
JUMP_WARN_RECENT_ROWS = 10

# ----------------------------------------------------------------------
# Handelskalender-Hilfsfunktionen
# ----------------------------------------------------------------------
def previous_business_day(date: pd.Timestamp) -> pd.Timestamp:
    """Liefert den letzten Werktag (Mo-Fr) vor `date`. Feiertage werden
    nicht berücksichtigt - das führt im schlimmsten Fall zu einem
    unnötigen, aber harmlosen Zusatz-Download."""
    d = date.normalize() - pd.Timedelta(days=1)
    while d.weekday() >= 5:  # 5=Samstag, 6=Sonntag
        d -= pd.Timedelta(days=1)
    return d


def compute_query_end_date(now: datetime) -> pd.Timestamp:
    """Letzter Handelstag, bis zu dem Kurse abgefragt werden sollen
    (siehe Modul-Docstring "Sicherer Auswertungszeitpunkt"). `now` ist
    die aktuelle, zeitzonenbehaftete Zeit (beliebige Zeitzone, z.B.
    datetime.now(BERLIN_TZ)); ein naives Datum wird als Berliner Zeit
    gelesen. Datum und Uhrzeit werden in New Yorker Zeit ausgewertet:
      - an Wochenenden gibt es ohnehin keinen aktuelleren Kurs ->
        letzter Freitag,
      - unter der Woche vor SAFE_EVALUATION_TIME_NY: der letzte
        vollständige Handelstag (i.d.R. der Vortag),
      - unter der Woche ab SAFE_EVALUATION_TIME_NY: heute."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=BERLIN_TZ)
    now_ny = now.astimezone(NEW_YORK_TZ)
    today = pd.Timestamp(now_ny.date())
    if today.weekday() >= 5:
        return previous_business_day(today + pd.Timedelta(days=1))
    if now_ny.time() >= SAFE_EVALUATION_TIME_NY:
        return today
    return previous_business_day(today)


# ----------------------------------------------------------------------
# Datenbereinigung & -validierung
# ----------------------------------------------------------------------
def _trim_trailing_nan_adjclose(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Schneidet randständige (aktuellste) Zeilen ab, deren 'Adj Close'
    NaN ist. Grund: Yahoo Finance liefert für den jüngsten, bereits
    abgeschlossenen Handelstag gelegentlich noch keinen fertig
    berechneten bereinigten Kurs (NaN), obwohl die Zeile im Download
    enthalten ist. Eine solche Zeile soll nicht als "aktuellster
    verfügbarer Kurs" durchgehen."""
    if df.empty or "Adj Close" not in df.columns:
        return df
    valid = df["Adj Close"].notna()
    if valid.all() or not valid.any():
        return df
    last_valid_pos = valid.to_numpy().nonzero()[0][-1]
    if last_valid_pos == len(df) - 1:
        return df
    return df.iloc[: last_valid_pos + 1]


def _check_and_clean(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Prüft und bereinigt einen rohen yfinance-Download:
      - Randständige NaN-Adj-Close-Zeilen abschneiden.
      - Doppelte Datums-Indizes entfernen (letzter Eintrag gewinnt).
      - Index chronologisch sortieren.
      - Interne NaN-Zeilen in Adj Close entfernen (mit Warnung).
      - Inf/-Inf in Adj Close -> ValueError (Datenkorruption).
      - Adj Close <= 0 -> ValueError (Datenkorruption).
      - Ungewöhnlich große Datenlücken -> informativer Hinweis.
    Wirft ValueError bei eindeutig korrupten Daten, damit solche Fälle
    nicht unbemerkt in eine Auswertung einfließen."""
    if df.empty:
        return df
    if "Adj Close" not in df.columns:
        raise ValueError(f"{ticker}: Spalte 'Adj Close' fehlt im Download "
                          f"(vorhandene Spalten: {list(df.columns)}).")

    df = _trim_trailing_nan_adjclose(df, ticker)
    if df.empty:
        return df

    if not df.index.is_unique:
        dupe_dates = df.index[df.index.duplicated()].unique()
        print(f"[warn]     {ticker}: {len(dupe_dates)} doppelte(s) Datum im Download "
              f"({', '.join(d.date().isoformat() for d in dupe_dates)}) - "
              f"behalte jeweils den letzten Eintrag.")
        df = df[~df.index.duplicated(keep="last")]

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()

    adj_close = df["Adj Close"]

    nan_mask = adj_close.isna()
    if nan_mask.any():
        bad_dates = adj_close.index[nan_mask]
        print(f"[warn]     {ticker}: {int(nan_mask.sum())} interne NaN-Zeile(n) in Adj Close "
              f"({bad_dates[0].date()} .. {bad_dates[-1].date()}) - werden entfernt.")
        df = df[~nan_mask]
        adj_close = df["Adj Close"]

    if adj_close.empty:
        return df

    values = adj_close.to_numpy(dtype="float64")

    inf_mask = np.isinf(values)
    if inf_mask.any():
        bad_dates = adj_close.index[inf_mask]
        raise ValueError(f"{ticker}: {int(inf_mask.sum())} Inf/-Inf-Wert(e) in Adj Close am "
                          f"{', '.join(d.date().isoformat() for d in bad_dates)} - "
                          f"vermutlich Datenkorruption, breche ab.")

    non_positive_mask = values <= 0
    if non_positive_mask.any():
        bad_dates = adj_close.index[non_positive_mask]
        raise ValueError(f"{ticker}: {int(non_positive_mask.sum())} Adj-Close-Wert(e) <= 0 am "
                          f"{', '.join(d.date().isoformat() for d in bad_dates)} - "
                          f"vermutlich Datenfehler, breche ab.")

    return df


# ----------------------------------------------------------------------
# Persistente Ticker-Historie mit Werten (siehe Modul-Docstring Punkt 1)
# ----------------------------------------------------------------------
def _known_values_path(ticker: str) -> Path:
    """Pfad zur Datei mit den für diesen Ticker bereits bestätigten
    (Handelstag, Adj-Close-Wert)-Paaren (siehe KNOWN_VALUES_DIR). Der
    Tickername wird defensiv von Pfadtrennzeichen befreit, auch wenn
    reguläre Ticker-Symbole diese nicht enthalten."""
    safe_name = ticker.replace("/", "_").replace("\\", "_")
    return KNOWN_VALUES_DIR / f"{safe_name}.txt"


def _load_known_values(ticker: str) -> pd.Series:
    """Liest die für diesen Ticker bereits bestätigten (Handelstag,
    Adj-Close-Wert)-Paare aus der persistenten Historie ("ISO-
    Datum,Wert" pro Zeile). Leere Series (float64, DatetimeIndex),
    falls für den Ticker noch keine Datei existiert (z.B. erste
    Abfrage überhaupt). Zeilen ohne Komma werden ignoriert."""
    path = _known_values_path(ticker)
    if not path.exists():
        return pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
    dates: list[str] = []
    values: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        date_str, value_str = line.split(",", 1)
        dates.append(date_str)
        values.append(float(value_str))
    if not dates:
        return pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
    index = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    return pd.Series(values, index=index, dtype="float64").sort_index()


def _save_known_values(ticker: str, values: pd.Series) -> None:
    """Schreibt die bestätigten (Handelstag, Adj-Close-Wert)-Paare
    eines Tickers sortiert in dessen Datei (eine Zeile je Handelstag,
    "ISO-Datum,Wert"). `repr()` auf den float-Wert (statt z.B. einer
    gerundeten Formatierung) garantiert einen verlustfreien Rundtrip
    beim Wiedereinlesen - ein exakter Wertevergleich (siehe
    _reconcile_known_gaps()) ist damit ohne Toleranzschwelle
    zuverlässig."""
    KNOWN_VALUES_DIR.mkdir(parents=True, exist_ok=True)
    values = values.sort_index()
    lines = [f"{d.date().isoformat()},{float(v)!r}" for d, v in values.items()]
    text = "\n".join(lines)
    _known_values_path(ticker).write_text(text + "\n" if text else "", encoding="utf-8")


def _reconcile_known_gaps(adj_close: pd.Series, ticker: str, start_date: pd.Timestamp,
                           query_end_date: pd.Timestamp) -> pd.Series:
    """Kernprüfung des Ansatzes: vergleicht die diesmal tatsächlich
    empfangenen Handelstage (`adj_close`, ECHTE, noch nicht
    interpolierte Werte) mit den für diesen Ticker bereits bekannten
    (persistierten, siehe _load_known_values()) - eingeschränkt auf das
    aktuell angefragte Fenster [start_date, query_end_date].

    Für jeden bereits bekannten, aber diesmal NICHT gelieferten
    Handelstag wird je Seite (davor/danach) der NÄCHSTE bereits LOKAL
    bekannte Handelstag gesucht (unabhängig davon, ob er unmittelbar
    im aktuellen Download benachbart ist) - er zählt nur als
    Vergleichsbasis, wenn er auch im aktuellen Download tatsächlich
    vorhanden ist (sonst fehlt die Grundlage für einen Vergleich).
    Stimmen ALLE so gefundenen Nachbarn exakt mit ihrem jeweils
    gespeicherten Wert überein, wird der fehlende Tag mit dem für ihn
    gespeicherten Wert aufgefüllt - die Umgebung gilt dann als stabil,
    der gespeicherte Wert also weiterhin aktuell.

    Gibt es dagegen keinen einzigen überprüfbaren Nachbarn, oder weicht
    mindestens einer ab (Hinweis auf eine nachträgliche Kursanpassung
    durch Yahoo, siehe Modul-Docstring), gilt der gespeicherte Wert
    für diesen Tag als nicht mehr vertrauenswürdig: er wird NICHT
    übernommen, sondern per _purge_known_values() aus der persistenten
    Historie entfernt - bewusst KEIN RuntimeError, KEIN Abbruch des
    Laufs (das entspricht dem manuellen "Known-Values-Datei löschen und
    Skript neu ausführen"). Die dadurch entstehende Lücke wird
    anschließend ganz regulär wie jede andere, noch nie bestätigte
    Lücke behandelt (siehe get_price_history(), Punkt 3: i.d.R. per
    linearer Interpolation geschlossen, sofern echte Werte davor und
    danach vorliegen - liegt der fehlende Tag ganz am Rand des
    Fensters, bleibt er stattdessen kommentarlos aus). Ein abweichender
    Nachbar wird zusätzlich mit `[warn]` gemeldet (im Unterschied zum
    rein informativen "kein Nachbar überprüfbar"-Fall), da das auf eine
    echte, ggf. auch andere Handelstage betreffende rückwirkende
    Kursanpassung hindeuten kann.

    Gibt `adj_close`, ergänzt um etwaige aus der Historie aufgefüllte
    Tage, zurück (unverändert, falls für dieses Fenster nichts
    fehlt)."""
    known = _load_known_values(ticker)
    known_in_window = known[(known.index >= start_date) & (known.index <= query_end_date)]
    have_dates = adj_close.index
    missing = known_in_window.index[~known_in_window.index.isin(have_dates)]
    if len(missing) == 0:
        return adj_close

    filled: dict[pd.Timestamp, float] = {}
    purged: list[pd.Timestamp] = []
    for d in sorted(missing):
        # Nächster LOKAL bekannter Nachbar je Seite (nicht zwingend der
        # nächste Tag aus DIESEM Download) - zählt nur, wenn er auch im
        # aktuellen Download vorhanden ist (siehe Docstring oben).
        before_known = known.index[known.index < d]
        after_known = known.index[known.index > d]
        candidates = []
        if len(before_known) > 0:
            candidates.append(before_known.max())
        if len(after_known) > 0:
            candidates.append(after_known.min())
        neighbors = [n for n in candidates if n in have_dates]

        mismatch = None  # (Nachbartag, gespeicherter Wert, frischer Wert), falls Abweichung
        for n in neighbors:
            fresh_val = float(adj_close.loc[n])
            stored_val = float(known.loc[n])
            if fresh_val != stored_val:
                mismatch = (n, stored_val, fresh_val)
                break

        if neighbors and mismatch is None:
            filled[d] = float(known_in_window.loc[d])
            continue

        purged.append(d)
        if mismatch is not None:
            n, stored_val, fresh_val = mismatch
            print(f"[warn]     {ticker}: bereits bekannter Handelstag {d.date()} fehlt in "
                  f"dieser Antwort, und Nachbartag {n.date()} weicht gegenüber dem "
                  f"gespeicherten Wert ab ({stored_val!r} -> {fresh_val!r}) - vermutlich hat "
                  f"Yahoo die Kurshistorie nachträglich angepasst (z.B. Dividende/Split); der "
                  f"gespeicherte Wert für {d.date()} ist damit vermutlich ebenfalls veraltet "
                  f"und wird aus der lokalen Historie entfernt (siehe "
                  f"{_known_values_path(ticker)}).")
        else:
            print(f"[info]     {ticker}: bereits bekannter Handelstag {d.date()} fehlt in "
                  f"dieser Antwort, und es liegt kein aktuell überprüfbarer Nachbartag vor - "
                  f"gespeicherter Wert wird aus der lokalen Historie entfernt (siehe "
                  f"{_known_values_path(ticker)}).")

    if filled:
        tag_wort = "Handelstag" if len(filled) == 1 else "Handelstage"
        print(f"[info]     {ticker}: {len(filled)} bereits bekannte(r), aber diesmal fehlende(r) "
              f"{tag_wort} aus lokal gespeicherten Werten aufgefüllt "
              f"({', '.join(d.date().isoformat() for d in sorted(filled))}).")

    if purged:
        _purge_known_values(ticker, purged)

    if not filled:
        return adj_close
    add_series = pd.Series(filled, dtype="float64")
    return pd.concat([adj_close, add_series]).sort_index()


def _update_known_values(ticker: str, fresh_values: pd.Series) -> None:
    """Aktualisiert die persistente Historie eines Tickers mit den
    diesmal tatsächlich (ECHT, nicht interpoliert, nicht aus der
    lokalen Historie aufgefüllt) von Yahoo gelieferten Werten -
    überschreibt bereits bekannte Handelstage mit dem neuesten Stand
    (siehe Modul-Docstring: "nicht in Stein gemeißelt") und ergänzt
    neue Handelstage. Es werden hier nie Einträge entfernt (die einzige
    Ausnahme dazu ist _purge_known_values(), siehe dort)."""
    existing = _load_known_values(ticker)
    combined = pd.concat([existing, fresh_values])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    _save_known_values(ticker, combined)


def _purge_known_values(ticker: str, dates: list[pd.Timestamp]) -> None:
    """Entfernt die übergebenen Handelstage aus der persistenten
    Historie eines Tickers - Gegenstück zu _update_known_values(), das
    bewusst nie etwas entfernt. Einzige Aufruferin ist
    _reconcile_known_gaps(): wird ein zuvor bekannter Handelstag in der
    aktuellen Antwort vermisst UND kann er (mangels überprüfbarem
    Nachbarn oder wegen einer Abweichung) nicht mehr bestätigt werden,
    gilt sein gespeicherter Wert als nicht mehr vertrauenswürdig und
    wird hier verworfen, statt den Lauf mit RuntimeError abzubrechen -
    entspricht dem manuellen Löschen der betroffenen Zeile(n) aus der
    Known-Values-Datei. Unbekannte/bereits fehlende Daten werden
    stillschweigend ignoriert."""
    existing = _load_known_values(ticker)
    remaining = existing.drop(index=[d for d in dates if d in existing.index])
    _save_known_values(ticker, remaining)


_calendar_instance_cache: dict[str, "mcal.MarketCalendar"] = {}


def _get_calendar(calendar_name: str) -> "mcal.MarketCalendar":
    if calendar_name not in _calendar_instance_cache:
        _calendar_instance_cache[calendar_name] = mcal.get_calendar(calendar_name)
    return _calendar_instance_cache[calendar_name]


# Ordnet einem Yahoo-Finance-Börsenplatz-Suffix den zugehörigen
# pandas_market_calendars-Kalendernamen zu (siehe calendar_for_ticker()
# unten). Für München (.MU), Berlin (.BE) und Hannover (.HA) bietet
# pandas_market_calendars keinen eigenen Kalender - dort wird
# ersatzweise Xetra (XETR) verwendet, was in der Praxis nur an sehr
# wenigen Tagen im Jahr abweichen dürfte (bundesweite Feiertage sind
# ohnehin für alle deutschen Börsen identisch). Bei allen hier
# geprüften, tatsächlich vorhandenen Kalendern (XETR/XFRA/XDUS/XHAM)
# stimmen die Handelstage über mehrere Jahre exakt überein; XSTU
# (Stuttgart) weicht davon in nur ~1 von 300 Handelstagen ab (einzelne
# Tage rund um Feiertage wie Pfingstmontag/Tag der Deutschen Einheit).
#
# Ursprünglich nur deutsche Börsenplätze (Name aus historischen
# Gründen beibehalten) - um auch nicht-deutsche/nicht-US-Ticker (z.B.
# Euronext Amsterdam, ".AS") korrekt gegen ihren TATSÄCHLICHEN
# Handelskalender statt des NYSE-Default-Fallbacks (siehe
# calendar_for_ticker()) zu prüfen, sind hier bei Bedarf weitere
# Börsenplätze zu ergänzen (siehe ".AS" unten als erstes Beispiel).
# pandas_market_calendars.get_calendar_names() listet die verfügbaren
# Kalendernamen.
GERMAN_EXCHANGE_CALENDAR_BY_SUFFIX = {
    ".DE": "XETR",  # Xetra
    ".F":  "XFRA",  # Frankfurt (Parkett)
    ".SG": "XSTU",  # Stuttgart
    ".DU": "XDUS",  # Düsseldorf
    ".HM": "XHAM",  # Hamburg
    ".MU": "XETR",  # München - kein eigener Kalender verfügbar, Xetra als beste Näherung
    ".BE": "XETR",  # Berlin - kein eigener Kalender verfügbar
    ".HA": "XETR",  # Hannover - kein eigener Kalender verfügbar
    ".AS": "XAMS",  # Euronext Amsterdam (z.B. IWRD.AS/IWDA.AS) - EUR-notiert
                     # wie die deutschen Börsenplätze oben, daher hier
                     # ohne zusätzliche Währungsumrechnung mitgeführt.
}


def calendar_for_ticker(ticker: str) -> str:
    """Ordnet einem Ticker den Namen seines Börsenkalenders zu (für
    pandas_market_calendars, siehe load_prices()/get_price_history()
    oben) - anhand des Yahoo-Finance-Börsenplatz-Suffixes (siehe
    GERMAN_EXCHANGE_CALENDAR_BY_SUFFIX, trotz des Namens nicht mehr nur
    deutsche Börsenplätze, siehe ".AS"/Euronext Amsterdam dort).
    Tickern ohne einen der dort gelisteten Suffixe (z.B. TIP, an der
    NYSE Arca notiert) wird NYSE als Kalender zugeordnet - bitte bei
    neuen, nicht in den USA oder an einer der gelisteten Börsen
    gehandelten Tickern prüfen und diese Funktion/das Dict
    entsprechend erweitern (Vorsicht bei Börsenplätzen mit abweichender
    Notierungswährung, z.B. London/GBX - dort würde zusätzlich eine
    Währungsumrechnung nötig, die dieses Modul bislang nicht
    beherrscht). Zentral hier (statt je Aufrufer-Skript dupliziert)
    hinterlegt, damit canary.py, backtest.py und stats.py stets
    dieselbe Zuordnung verwenden."""
    for suffix, calendar_name in GERMAN_EXCHANGE_CALENDAR_BY_SUFFIX.items():
        if ticker.endswith(suffix):
            return calendar_name
    return "NYSE"


def _first_trade_date_from_metadata(ticker_obj: "yf.Ticker") -> pd.Timestamp | None:
    """Liest das Erstnotiz-/Börsengangsdatum aus den von Yahoo mit der
    Kurshistorie mitgelieferten Metadaten (Feld "firstTradeDate" der
    Chart-API) - erfordert keinen zusätzlichen Request, siehe
    _download_once(). Gibt None zurück, falls das Feld fehlt oder
    `ticker_obj.history()` noch nicht aufgerufen wurde.

    Das Feld liegt je nach yfinance-Version unterschiedlich vor:
    ältere Versionen liefern einen rohen Unix-Zeitstempel (int/float,
    Sekunden), neuere Versionen (siehe yfinance.utils.
    format_history_metadata()) wandeln es bereits selbst in einen
    pd.Timestamp um - und zwar TZ-BEWUSST, lokalisiert auf die
    Zeitzone der jeweiligen Börse. Beide Fälle werden hier behandelt;
    ein tz-bewusster Timestamp wird per tz_convert(None) in die lokale
    Kalenderdatumsangabe ohne Zeitzoneninfo umgewandelt (verschiebt NICHT
    die Uhrzeit/das Datum, entfernt nur das tz-Label)."""
    try:
        meta = ticker_obj.history_metadata
    except Exception:
        return None
    if not meta:
        return None
    epoch = meta.get("firstTradeDate")
    if epoch is None:
        return None
    try:
        if isinstance(epoch, (int, float)):
            ts = pd.Timestamp(epoch, unit="s", tz="UTC")
        else:
            ts = pd.Timestamp(epoch)
        if ts.tzinfo is not None:
            ts = ts.tz_convert(None)
        return ts.normalize()
    except Exception:
        return None


def _missing_trading_days(adj_close: pd.Series, calendar_name: str,
                           window_start: pd.Timestamp, window_end: pd.Timestamp) -> pd.DatetimeIndex:
    """Vergleicht die tatsächlich vorhandenen Handelstage einer Kursreihe
    im Fenster [window_start, window_end] gegen den ECHTEN Handelskalender
    der Börse `calendar_name` - eine von Yahoo Finance UNABHÄNGIGE
    Quelle. Gibt die laut Kalender fehlenden Handelstage zurück (leer,
    wenn vollständig). Damit lassen sich Datenlücken erkennen, die ein
    reiner Vergleich mehrerer Yahoo-Abrufe untereinander verpasst, wenn
    Yahoo serverseitig mehrfach identisch dieselbe unvollständige
    Antwort liefert (siehe Modul-Docstring)."""
    if window_end < window_start:
        return pd.DatetimeIndex([])
    cal = _get_calendar(calendar_name)
    expected = cal.valid_days(start_date=window_start, end_date=window_end)
    expected_naive = pd.DatetimeIndex(pd.DatetimeIndex(expected).tz_localize(None).normalize())
    have = pd.DatetimeIndex(adj_close.index.normalize())
    return expected_naive.difference(have)


def _unexplained_missing_days(adj_close: pd.Series, calendar_name: str, start_date: pd.Timestamp,
                               first_trade_date: pd.Timestamp | None) -> tuple[pd.DatetimeIndex, pd.Timestamp]:
    """Prüft eine geladene Adj-Close-Kursreihe auf Vollständigkeit
    gegen den echten Börsenkalender (siehe _missing_trading_days()) -
    UNTER BERÜCKSICHTIGUNG eines möglichen Börsengangs/Listings
    innerhalb des angefragten Zeitraums (siehe Modul-Docstring, Punkt
    2), damit ein junger Ticker nicht fälschlich als "unvollständige
    Daten" gemeldet wird:
      a) Ist `first_trade_date` bekannt (aus Yahoo-Metadaten, siehe
         _first_trade_date_from_metadata()) und liegt es nach
         `start_date`, wird das erwartete Fenster entsprechend
         verkürzt (Handelstage vor dem Listing werden gar nicht erst
         erwartet).
      b) Ist `first_trade_date` NICHT bekannt, aber die verbleibenden
         fehlenden Handelstage bilden ausschließlich einen
         zusammenhängenden Block VOR dem ersten tatsächlich
         gelieferten Kurs (keine Lücke mitten in oder nach den
         vorhandenen Daten), wird das ebenfalls als plausibler
         Börsengang gewertet - das unterscheidet ihn von einer
         "echten" Datenlücke, wie sie ursprünglich beobachtet wurde
         (dort lagen die fehlenden Tage VERSTREUT zwischen
         vorhandenen Daten).
    Reine Berechnung ohne Ausgabe/Exception - gibt (verbleibende,
    NICHT durch ein Listing erklärbare fehlende Handelstage, tatsächlich
    zugrunde gelegtes Fenster-Startdatum) zurück. Ist das zurückgegebene
    Fenster-Startdatum > `start_date`, wurde ein Börsengang/Listing
    erkannt (Aufrufer kann das für einen einzigen kurzen Hinweis
    nutzen)."""
    if adj_close.empty:
        return pd.DatetimeIndex([]), start_date

    window_start = start_date
    if first_trade_date is not None and first_trade_date > window_start:
        window_start = first_trade_date
    window_end = adj_close.index.max()

    missing = _missing_trading_days(adj_close, calendar_name, window_start, window_end)
    if len(missing) == 0:
        return missing, window_start

    earliest_present = adj_close.index.min()
    leading_gap_only = all(d < earliest_present for d in missing)
    if leading_gap_only and first_trade_date is None:
        return pd.DatetimeIndex([]), earliest_present

    return missing, window_start


def _interpolate_missing_days(df: pd.DataFrame, calendar_name: str,
                               missing_days: pd.DatetimeIndex, ticker: str) -> pd.DataFrame:
    """Schließt fehlende Handelstage - OHNE Größenlimit, auch mehrtägige
    Lücken - per linearer Interpolation zwischen den jeweils
    nächstgelegenen tatsächlich vorhandenen Adj-Close-Werten davor und
    danach: als letzter Ausweg, wenn nach allen Versuchen kein
    einziger vollständiger Download erreicht wurde (siehe
    get_price_history()). Jeder fehlende Tag wird proportional zu
    seiner Position (gemessen in Handelstagen laut Börsenkalender)
    zwischen diesen beiden Nachbarn interpoliert - bei einer einzelnen
    fehlenden Zeile ist das der einfache Mittelwert, bei einer
    mehrtägigen Lücke ergibt sich eine Gerade zwischen den beiden
    Randwerten. Motivation: `yfinance`s "price repair"
    (https://ranaroussi.github.io/yfinance/advanced/price_repair.html)
    hilft hier nicht, da es nur vorhandene, aber leere/fehlerhafte
    Kurswerte repariert - nicht komplett fehlende Zeilen.

    Ein fehlender Tag, für den es GAR KEINEN vorhandenen Kurs davor
    oder danach gibt (z.B. ganz am Rand des angefragten Fensters),
    wird übersprungen - dafür fehlt jede Grundlage zur Interpolation.
    Das kann in der Praxis nur bei einem sehr knapp/ungenau bekannten
    Börsengangsdatum vorkommen (siehe _unexplained_missing_days())."""
    if len(missing_days) == 0:
        return df
    cal = _get_calendar(calendar_name)
    have = df.index  # bereits sortiert, siehe _check_and_clean()
    new_rows: dict[pd.Timestamp, float] = {}
    for d in sorted(missing_days):
        before = have[have < d]
        after = have[have > d]
        if len(before) == 0 or len(after) == 0:
            continue  # kein Nachbar auf einer Seite - nicht interpolierbar
        prev_day, next_day = before.max(), after.min()
        span = pd.DatetimeIndex(
            cal.valid_days(start_date=prev_day, end_date=next_day)
        ).tz_localize(None).normalize()
        total_steps = len(span) - 1
        if d not in span or total_steps <= 0:
            continue
        pos = span.get_loc(d)
        prev_price = float(df.loc[prev_day, "Adj Close"])
        next_price = float(df.loc[next_day, "Adj Close"])
        new_rows[d] = prev_price + (next_price - prev_price) * (pos / total_steps)
    if not new_rows:
        return df
    add_df = pd.DataFrame({"Adj Close": pd.Series(new_rows, dtype="float64")})
    return pd.concat([df, add_df], axis=0).sort_index()


# ----------------------------------------------------------------------
# Extreme Kurssprünge: automatische Korrektur (siehe Modul-Docstring Punkt 6)
# ----------------------------------------------------------------------
def _detect_and_correct_price_jumps(adj_close: pd.Series, ticker: str) -> pd.Series:
    """Prüft `adj_close` (ein einzelner Download, bereits nach
    Vollständigkeits-/Wertevalidierung) auf extreme Sprünge zwischen
    zwei aufeinanderfolgenden, tatsächlich vorhandenen Datenpunkten
    (Verhältnis > PRICE_JUMP_FACTOR_THRESHOLD oder <
    1/PRICE_JUMP_FACTOR_THRESHOLD) und korrigiert jeden davon
    automatisch: alle Werte VOR dem Sprungdatum werden mit dem aus genau
    diesem Übergang berechneten Faktor skaliert, sodass die Reihe
    nahtlos in die Werte AB diesem Datum übergeht. Der Faktor wird bei
    jedem Aufruf frisch aus den beiden angrenzenden Werten berechnet.
    Bei mehreren Sprüngen wirken die Faktoren kumulativ - ein
    vorübergehend falscher Kurs (Hinsprung + Rücksprung) wird so
    insgesamt auf das normale Niveau zurückgeführt (siehe Modul-
    Docstring Punkt 6). Jede Korrektur wird gemeldet (`[warn]`, falls der
    Sprung innerhalb der letzten JUMP_WARN_RECENT_ROWS Datenpunkte
    liegt, sonst `[info]`). Gibt `adj_close` zurück (bei Sprüngen
    entsprechend skaliert, sonst unverändert)."""
    if adj_close.empty:
        return adj_close
    adj_close = adj_close.sort_index()
    ratios = adj_close / adj_close.shift(1)
    suspicious = ratios[(ratios > PRICE_JUMP_FACTOR_THRESHOLD) |
                         (ratios < 1.0 / PRICE_JUMP_FACTOR_THRESHOLD)]
    if suspicious.empty:
        return adj_close

    recent_dates = set(adj_close.index[-JUMP_WARN_RECENT_ROWS:])
    corrected = adj_close.copy()
    for jump_date, ratio in suspicious.items():
        prev_date = adj_close.index[adj_close.index.get_loc(jump_date) - 1]
        factor = float(ratio)
        mask = corrected.index < jump_date
        corrected.loc[mask] = corrected.loc[mask] * factor
        level = "[warn]" if jump_date in recent_dates else "[info]"
        print(f"{level}     {ticker}: extremer Kurssprung am {jump_date.date()} um Faktor "
              f"{factor:.6g} ({float(adj_close.loc[prev_date])!r} am {prev_date.date()} -> "
              f"{float(adj_close.loc[jump_date])!r}) automatisch korrigiert - Werte davor "
              f"entsprechend skaliert.")

    return corrected


# ----------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------
def _download_once(ticker: str, start_date: pd.Timestamp,
                    query_end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Lädt Kursdaten von Yahoo Finance und liest, falls von Yahoo
    mitgeliefert, das Erstnotiz-/Börsengangsdatum aus derselben
    Antwort mit (siehe _first_trade_date_from_metadata()) - dafür wird
    bewusst `yf.Ticker(...).history()` statt `yf.download()` verwendet,
    da nur Ersteres die Metadaten der Chart-API zugänglich macht. Gibt
    (Kursdaten, Erstnotizdatum oder None) zurück."""
    ticker_obj = yf.Ticker(ticker)
    df = ticker_obj.history(start=start_date, end=query_end_date + pd.Timedelta(days=1),
                             auto_adjust=False, actions=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is not None:
        # Handelstag bleibt dieselbe Kalenderdatum, nur die
        # Zeitzoneninfo wird entfernt (kein Zeitzonen-Shift).
        df.index = df.index.tz_localize(None)
    first_trade_date = _first_trade_date_from_metadata(ticker_obj)
    return df, first_trade_date


def get_price_history(ticker: str, start_date: pd.Timestamp,
                       query_end_date: pd.Timestamp) -> pd.DataFrame:
    """Lädt die Kurshistorie eines Tickers von `start_date` bis
    `query_end_date` direkt von Yahoo Finance (kein Cache, genau EIN
    Abruf).

    Drei sich ergänzende Prüfungen:
      1. Abgleich gegen die persistente Ticker-Historie MIT Werten
         (siehe _reconcile_known_gaps()): fehlt in dieser Antwort ein
         Handelstag, den wir für diesen Ticker in diesem Fenster
         bereits einmal zuverlässig von Yahoo erhalten haben, wird
         versucht, ihn aus dem dafür gespeicherten Wert aufzufüllen -
         aber NUR, wenn der nächste bereits LOKAL bekannte Nachbartag
         je Seite (sofern im aktuellen Download überprüfbar) exakt mit
         seinem gespeicherten Wert übereinstimmt (Absicherung gegen
         zwischenzeitliche, rückwirkende Kursanpassungen durch Yahoo).
         Ist das nicht der Fall, oder gibt es keinen einzigen
         überprüfbaren Nachbartag, wird der gespeicherte Wert für
         diesen Tag als nicht mehr vertrauenswürdig verworfen (siehe
         _purge_known_values()) - KEIN RuntimeError, KEIN Abbruch; die
         entstehende Lücke fällt danach ggf. unter Punkt 3
         (Interpolation).
      2. Extreme Kurssprünge zwischen zwei aufeinanderfolgenden
         Datenpunkten (siehe _detect_and_correct_price_jumps()): werden
         automatisch korrigiert, indem die Werte davor entsprechend
         skaliert werden (wirkt NUR auf die zurückgegebene Kursreihe,
         NICHT auf die unter Punkt 1 persistierten Rohwerte).
      3. Vollständigkeit gegen den ECHTEN Börsenkalender
         (Kalendername wird intern über calendar_for_ticker(ticker)
         ermittelt, siehe _unexplained_missing_days()), inkl.
         Börsengang/Listing-Behandlung: fehlende, NOCH NIE gesehene
         Handelstage werden hier NICHT hart abgelehnt, sondern per
         linearer Interpolation geschlossen (siehe
         _interpolate_missing_days(), kein Größenlimit) - auf der
         bereits kurssprung-korrigierten Skala aus Punkt 2.

    Nach erfolgreicher Prüfung wird die persistente Historie mit den
    ECHTEN (nicht interpolierten, nicht aus der Historie aufgefüllten),
    UNVERÄNDERT ROHEN (nicht kurssprung-korrigierten, siehe Punkt 2)
    Handelstagen und Werten dieser Antwort aktualisiert (siehe
    _update_known_values()) - bereits bekannte Tage werden dabei mit
    dem neuesten Yahoo-Stand überschrieben; entfernt werden Einträge
    dabei nie (die einzige Ausnahme ist die Bereinigung nicht mehr
    bestätigbarer Tage in Punkt 1 oben, siehe _purge_known_values()).

    `start_date` kann entweder ein fixes, tatsächlich benötigtes Datum
    sein (z.B. frühestes Transaktionsdatum in stats.py) oder ein
    rollierendes, vom Aufrufer berechnetes Lookback-Fenster (wie in
    status.py) - für sehr lange/komplette Historien (wie in
    backtest.py) kann ein sehr frühes Ankerdatum (z.B.
    pd.Timestamp("1990-01-01")) übergeben werden. Ist der Ticker erst
    nach `start_date` an die Börse gegangen, wird das automatisch
    erkannt (siehe _unexplained_missing_days()) und nicht als fehlende
    Daten gewertet.
    """
    raw, first_trade_date = _download_once(ticker, start_date, query_end_date)
    if raw.empty:
        cleaned = raw
    else:
        cleaned = _check_and_clean(raw, ticker)
        cleaned = cleaned.loc[(cleaned.index >= start_date) & (cleaned.index <= query_end_date)]
        # cleaned["Adj Close"] enthält hier bewusst noch die ROHEN, von
        # Yahoo tatsächlich gelieferten Werte (siehe unten, Schritt 2).

    if cleaned.empty:
        known = _load_known_values(ticker)
        known_in_window = known[(known.index >= start_date) & (known.index <= query_end_date)]
        if len(known_in_window) > 0:
            raise RuntimeError(
                f"{ticker}: leerer/unbrauchbarer Download, obwohl {len(known_in_window)} "
                f"Handelstage in diesem Fenster laut vorheriger Abfragen bereits bekannt sind "
                f"(z.B. {known_in_window.index[0].date()}) - Datenregression, breche ab."
            )
        if first_trade_date is not None and first_trade_date > query_end_date:
            raise RuntimeError(f"{ticker}: keine Daten - laut Yahoo-Metadaten erst ab "
                                f"{first_trade_date.date()} gelistet (nach dem angefragten "
                                f"Enddatum {query_end_date.date()}).")
        raise RuntimeError(f"{ticker}: keine verwertbaren Daten für das angefragte Fenster "
                            f"{start_date.date()} - {query_end_date.date()} erhalten.")

    real_dates = cleaned.index  # ECHTE, von Yahoo gelieferte Handelstage dieser Antwort,
                                 # vor Auffüllen aus der Historie/Interpolation, siehe unten
    raw_real_values = cleaned.loc[real_dates, "Adj Close"].copy()  # ROHE Werte dieser
                                 # Antwort, VOR jeder Kurssprung-Korrektur - werden unten
                                 # unverändert persistiert (siehe Schritt 2 und
                                 # _update_known_values()).

    # 1) Bereits bekannte, aber diesmal fehlende Handelstage aus der
    #    persistenten Historie auffüllen (mit Nachbarabgleich) - oder,
    #    falls die Vertrauensbasis dafür fehlt/wackelt, aus der
    #    persistenten Historie entfernen (kein Abbruch, siehe
    #    _reconcile_known_gaps()). Arbeitet bewusst noch im
    #    ROHDATEN-Raum: sowohl die frisch heruntergeladenen als auch die
    #    gespeicherten Werte sind an dieser Stelle unkorrigiert, ein
    #    Vergleich ist also konsistent.
    reconciled = _reconcile_known_gaps(cleaned["Adj Close"], ticker, start_date, query_end_date)
    added_dates = reconciled.index.difference(cleaned.index)
    if len(added_dates) > 0:
        add_df = pd.DataFrame({"Adj Close": reconciled.loc[added_dates]})
        cleaned = pd.concat([cleaned, add_df], axis=0).sort_index()

    # 2) Extreme Kurssprünge automatisch korrigieren (siehe
    #    PRICE_JUMP_FACTOR_THRESHOLD) - NACH dem Abgleich in Schritt 1 (der
    #    bewusst noch mit Rohdaten arbeitet), aber VOR der Interpolation
    #    in Schritt 3 (die eine durchgängige, bereits korrigierte Skala
    #    voraussetzt). Wirkt auf die vollständige Rohdaten-Reihe dieser
    #    Antwort inkl. ggf. in Schritt 1 aus der Historie aufgefüllter
    #    Tage.
    cleaned["Adj Close"] = _detect_and_correct_price_jumps(cleaned["Adj Close"], ticker)

    # 3) Vollständigkeit gegen den Börsenkalender + Interpolation für
    #    genuin neue (nie zuvor gesehene) Lücken. Kalendername wird
    #    zentral über calendar_for_ticker() ermittelt (siehe dort).
    filled = 0
    calendar_name = calendar_for_ticker(ticker)
    missing, window_start = _unexplained_missing_days(cleaned["Adj Close"], calendar_name,
                                                        start_date, first_trade_date)
    if window_start > start_date:
        print(f"[info]     {ticker}: laut Daten erst ab {window_start.date()} notiert "
              f"(Börsengang/Listing).")
    if len(missing) > 0:
        before = len(cleaned)
        cleaned = _interpolate_missing_days(cleaned, calendar_name, missing, ticker)
        filled = len(cleaned) - before

    _update_known_values(ticker, raw_real_values)

    if filled > 0:
        tag_wort = "fehlender Handelstag" if filled == 1 else "fehlende Handelstage"
        print(f"[ok]       {ticker}: {filled} {tag_wort} interpoliert ({cleaned.index.min().date()} - "
              f"{cleaned.index.max().date()}, {len(cleaned)} Zeilen).")
    elif len(added_dates) > 0:
        print(f"[ok]       {ticker}: vollständig, {len(added_dates)} Handelstag(e) davon aus "
              f"lokaler Historie aufgefüllt ({cleaned.index.min().date()} - "
              f"{cleaned.index.max().date()}, {len(cleaned)} Zeilen).")
    else:
        print(f"[ok]       {ticker}: vollständig ({cleaned.index.min().date()} - "
              f"{cleaned.index.max().date()}, {len(cleaned)} Zeilen).")

    return cleaned


# ----------------------------------------------------------------------
# Sicherheits-Cutoff für den heutigen (ggf. noch unfertigen) Kurs
# ----------------------------------------------------------------------
def drop_unsafe_todays_bar(adj_close: pd.Series, now: datetime) -> tuple[pd.Series, bool]:
    """Entfernt den letzten Eintrag aus `adj_close`, falls er vom
    HEUTIGEN Kalendertag (New Yorker Zeit) stammt UND die aktuelle New
    Yorker Uhrzeit vor SAFE_EVALUATION_TIME_NY liegt. `now` ist die
    aktuelle, zeitzonenbehaftete Zeit (naiv: Berliner Zeit).
    Sicherheitsnetz zusätzlich zur Begrenzung des Abfrage-Enddatums in
    compute_query_end_date() (siehe Modul-Docstring). Gibt (bereinigte
    Serie, ob etwas verworfen wurde) zurück."""
    if adj_close.empty:
        return adj_close, False
    if now.tzinfo is None:
        now = now.replace(tzinfo=BERLIN_TZ)
    now_ny = now.astimezone(NEW_YORK_TZ)
    last_date = adj_close.index[-1].date()
    if last_date == now_ny.date() and now_ny.time() < SAFE_EVALUATION_TIME_NY:
        return adj_close.iloc[:-1], True
    return adj_close, False


# ----------------------------------------------------------------------
# Komfort-Funktion: fertige, bereinigte Adj-Close-Kursreihe
# ----------------------------------------------------------------------
def load_prices(ticker: str, start_date: pd.Timestamp,
                 query_end_date: pd.Timestamp) -> tuple[pd.Series, bool]:
    """Lädt die Adj-Close-Kursreihe eines Tickers (ein einzelner Abruf,
    siehe get_price_history()) inkl. Regressionsprüfung gegen die
    persistente Ticker-Historie und Börsenkalender-Vollständigkeits-
    prüfung mit Interpolation (Kalendername wird intern über
    calendar_for_ticker() ermittelt), sowie Sicherheits-Cutoff (siehe
    drop_unsafe_todays_bar(), aktuelle Zeit wird intern via
    datetime.now(BERLIN_TZ) ermittelt). Gibt (bereinigte Kursreihe, ob
    der heutige Balken verworfen wurde) zurück."""
    df = get_price_history(ticker, start_date, query_end_date)
    adj_close = df["Adj Close"].dropna()
    adj_close.name = ticker
    return drop_unsafe_todays_bar(adj_close, datetime.now(BERLIN_TZ))
