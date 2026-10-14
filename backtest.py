"""
Backtest: Hybrid-Strategie (TIP-Canary + Nasdaq-100-SMA200) mit realen Risk-Assets
===================================================================================

Strategien (je Risk-Asset-Variante, alle nach Steuern):
  Hybrid (maßgeblich)  Risk, wenn das TIP-Canary-Signal ODER das Nasdaq-100-
                       SMA-Signal auf Risk steht. Defensiv nur, wenn BEIDE
                       schlecht stehen. Ein TIP-Risk-Signal gilt immer; in
                       TIP-Defensiv-Phasen hält der Nasdaq-100 (^NDX) das
                       Risk-Asset, solange sein Schlusskurs STRIKT ÜBER dem
                       200-Tage-SMA liegt (Gleichstand zählt wie beim TIP-
                       Score = 0 als "nicht über", also defensiv).
  TIP-Canary           nur das TIP-Signal (Vergleich).
  NDX-SMA200           nur das Nasdaq-100-SMA-Signal (Vergleich); Risk-off
                       ebenfalls im Defensiv-Asset (Cash vor dessen Notierung).
  Buy & Hold           Referenz.
  Die ausführlichen Zusatztabellen (Kennzahlen, Jahresvergleich, Defensiv-
  Phasen) und die Plot-Einfärbung beziehen sich auf den HYBRID der ersten
  Variante in RISK_TICKERS.
  Das SMA-Signal hat einen eigenen asymmetrischen Whipsaw-Filter
  (TREND_CONFIRMATION_A/B, getrennt von CONFIRMATION_A/B des TIP):
    A: Handelstage, die der Kurs UNTER der SMA bleiben muss, bevor das
       SMA-Signal von "Risk" auf "Defensiv" kippt,
    B: Handelstage über der SMA, bevor es zurück auf "Risk" kippt.
  Kandidaten: 1x nur SXR4.DE, 2x nur 18MF.DE (davor das synthetische Asset).
  Wechsel = Wechsel zwischen Risk-Asset und Defensiv-Asset/Cash (jede
  Richtung einzeln; Cash -> Defensiv-Asset bei der Erstnotierung zählt nicht).

Ursprünglicher Kopf (TIP-Canary-Backtest):

Im Risk-on-Modus wird ein Risk-Asset gehalten (siehe RISK_TICKERS und
"Reale Risk-Assets und Auswahl" unten), im Risk-off-Modus das eine fest
vorgegebene defensive Asset (siehe DEFENSIVE) - AUSSER für den
Zeitraum VOR dessen Börsengang, siehe "Verfügbarkeit des defensiven
Assets" unten. Der Whipsaw-/Bestätigungsfilter des TIP-Canary-Signals
verwendet ZWEI getrennte Bestätigungsfenster je Wechselrichtung,
CONFIRMATION_A=1 (Risk -> Defensiv) und CONFIRMATION_B=2 (Defensiv ->
Risk) - siehe Abschnitt "Rebalancing / Whipsaw-Filter" unten.

Getestete Varianten:
  RISK_TICKERS enthält EINE oder MEHRERE Varianten (z.B. 2x- und
  1x-Hebel). Jede Variante besteht aus einem synthetischen Risk-Asset
  (Ticker, Hebel, Währung) und einer Liste realer "candidates" (siehe
  unten). Für JEDE Variante wird die TIP-Canary-Strategie gerechnet und
  einer Buy & Hold-Kurve (nach Steuern) gegenübergestellt - diese
  Zahlen landen für ALLE Varianten im Gesamtvergleich
  (Kennzahlen-Tabelle) und in den beiden Plots. Die AUSFÜHRLICHEN
  Zusatz-Auswertungen (Zeitanteile/Steuern, Jahresvergleich, Defensiv-
  und Risk-Phasen im Detail, Ø Phasen-Rendite) werden dagegen NUR für
  die ERSTE Variante in RISK_TICKERS (Dictionary-Reihenfolge) erstellt.

Reale Risk-Assets und Auswahl:
  Reale (später notierte) Risk-Assets werden als "candidates" je Variante
  geführt (Yahoo-Ticker -> {"name", "teilfreistellung", "currency"}); der
  Hebel steckt im Produkt selbst, eine Hebelung der Kandidaten findet
  nicht statt. Das synthetische Asset der Variante (z.B. SPY, 2x) ist
  der Fallback für Zeiträume, in denen kein Kandidat verfügbar ist.
    Auswahl: Zu Beginn JEDER zusammenhängenden Risk-Phase (Tage mit
  Makrosignal RISK, siehe backtest_tip_canary()) wird der Kandidat mit
  dem höchsten 13612U-Momentum gewählt und für die GESAMTE Phase
  gehalten. Es konkurrieren nur Kandidaten, für die zu diesem Zeitpunkt
  ein vollständiges 13612U-Momentum (21/63/126/252 Handelstage in der
  eigenen Kurshistorie, in EUR) vorliegt. Verwendet wird der Wert vom
  Schlusskurs des Signaltags (letzte Zeile vor dem Phasenbeginn, kein
  Look-Ahead). Liegt für keinen Kandidaten ein Momentum vor, wird für
  die ganze Phase das synthetische Asset gehalten. Wird ein Kandidat
  mitten in einer laufenden Phase verfügbar, wird NICHT gewechselt -
  die nächste Auswahl findet erst zu Beginn der nächsten Risk-Phase
  statt.
    Steuer: Gewählt wird nur beim Einstieg in eine Risk-Phase (Kauf),
  das vorherige Asset wurde beim Wechsel in die Defensive ohnehin
  verkauft - die Auswahl löst daher keine zusätzliche Steuer aus. Jeder
  Kandidat hat seine eigene Teilfreistellung (siehe "teilfreistellung").
    Buy & Hold-Vergleich: Verkettete Reihe aus dem synthetischen Asset
  bis zum ersten Kurs der FIX gewählten Referenz ("bh_reference" je Variante
  in RISK_TICKERS, muss einer der Kandidaten sein) und dieser Referenz danach.
  Es findet KEINE nachträgliche Auswahl mehr statt.
    Kostenbruch (Caveat): Die synthetische Reihe enthält weder TER noch
  Finanzierungskosten des Hebels, die realen Kandidaten schon. Die
  synthetische Reihe bleibt unverändert; ab Notierung der Kandidaten
  ist die Strategie dadurch realistischer gerechnet als davor.

Währungsumrechnung ("currency"-Angabe in DEFENSIVE/RISK_TICKERS und
den candidates):
  Jeder tatsächlich GEHALTENE Ticker (also NICHT das Canary-Asset TIP,
  siehe unten, inkl. der Kandidaten) muss eine Notierungswährung "EUR" oder "USD" angeben
  (KEIN Default, analog zu "teilfreistellung"). Ein mit "USD"
  gekennzeichneter Ticker wird über den Yahoo-Finance-Ticker EUR=X in
  EUR umgerechnet (siehe load_eur_per_usd()/convert_to_eur()) - Yahoo
  notiert EUR=X als "EUR JE 1 USD" (Stand 2024ff. typischerweise
  0.85-0.95), Multiplikation mit diesem Faktor rechnet also USD -> EUR
  um. Ein rudimentärer Plausibilitäts-Check (Wertebereich 0.4-2.0)
  soll eine versehentlich vertauschte Umrechnungsrichtung oder
  fehlerhafte FX-Daten sichtbar machen, ersetzt aber keine eigene
  Prüfung der Kursdaten.
    Reicht die Kurshistorie eines USD-Tickers weiter zurück als die von
  EUR=X auf Yahoo Finance (das kommt vor - siehe convert_to_eur()),
  wird die Kursreihe automatisch auf den ab dann gemeinsam abgedeckten
  Zeitraum eingeschränkt (mit [info]-Meldung) statt einen Fehler zu
  werfen - die nicht umrechenbare, frühere Historie entfällt
  ersatzlos. Eine Lücke MITTEN in der EUR=X-Historie wird dagegen
  vorwärts gefüllt (letzter bekannter Kurs); ein Fehler entsteht nur,
  wenn für ein Datum auch danach kein Kurs vorliegt.
    Reihenfolge bei einem zusätzlich gehebelten Risk-Asset (siehe
  "leverage" oben): der synthetische Hebel wird auf die NATIVE
  (unkonvertierte) Kursreihe angewendet und ERST DANACH nach EUR
  umgerechnet - das bildet ab, wie ein real gehandeltes Hebelprodukt
  tatsächlich funktioniert (Hebelung der Tagesrendite des Index in
  DESSEN eigener Währung, NICHT eine zusätzliche Hebelung der
  Währungsschwankung selbst).
    Caveat: EUR=X wird wie jeder andere Ticker über yf_data.py geladen
  (siehe dortiger Docstring) - dessen Börsenkalender-Vollständigkeits-
  prüfung kennt keinen speziellen FX-Kalender für "=X"-Ticker und
  ordnet ersatzweise den NYSE-Kalender zu. An US-Feiertagen, an denen
  der Devisenmarkt (anders als die NYSE) durchgehend handelt, kann das
  vereinzelt zu falsch-positiven "fehlender Handelstag"-Meldungen
  führen - bitte bei der ersten Ausführung mit echten Daten beobachten.

Synthetischer Hebel des Risk-/Defensiv-Assets ("leverage"-Angabe in
RISK_TICKERS UND DEFENSIVE):
  Über den Schlüssel "leverage" kann das konfigurierte Asset künstlich
  gehebelt werden, statt einen bereits real gehebelten ETF (z.B. einen
  2x-Daily-ETF) als Ticker eintragen zu müssen - nützlich, wenn der
  zugrundeliegende (ungehebelte) Index/ETF selbst eine deutlich längere
  Kurshistorie hat als jedes darauf gehebelte Produkt (z.B.
  MSCI-Index-Ticker via Yahoo Finance). Gilt GLEICHERMAßEN für
  RISK_TICKERS wie für DEFENSIVE - beide erwarten explizit einen
  "leverage"-Schlüssel (KEIN Default, analog zu
  "teilfreistellung"/"currency").
    leverage = 1.0   -> die geladenen Original-Kurswerte werden
                        unverändert verwendet.
    leverage > 1.0   -> künstlich gehebelte LONG-Kursreihe, siehe
                        synthetic_leveraged_series(): die TÄGLICHEN
                        Renditen des Basis-Tickers werden mit `leverage`
                        multipliziert und anschließend aufsummiert
                        (compoundiert) - analog zu real gehandelten
                        Hebelprodukten mit täglichem Reset auf den
                        Ziel-Hebel (daily rebalancing), inkl. des
                        dadurch entstehenden "Volatility-Decay"-Effekts
                        (Pfadabhängigkeit).
    leverage < 0.0   -> künstliche synthetische SHORT-Position (z.B.
                        leverage=-3.0 für eine 3x-Short-Position) - exakt
                        dieselbe tägliche Reset-/Compounding-Logik wie
                        beim positiven Hebel, nur mit umgekehrtem
                        Vorzeichen (steigt der Basis-Ticker, FÄLLT die
                        synthetische Reihe entsprechend gehebelt).
                        Nützlich, um z.B. einen 3x-Short-ETF mit kurzer
                        Historie (wie den "WisdomTree US Treasuries 30Y
                        3x Daily Short") über einen langjährigen,
                        ungehebelten Basis-Ticker nachzubilden. Der
                        "Volatility-Decay"-Effekt gilt unverändert auch
                        hier.
    leverage = 0.0   -> nicht zulässig (ValueError), siehe
                        synthetic_leveraged_series().
  Vereinfachung/Caveat: laufende Kosten (TER) und der
  Finanzierungskostensatz für den geliehenen Hebel-Anteil (bzw. bei
  einer Short-Position: die Kosten für das Leerverkaufen), die ein
  reales Hebel-/Short-Produkt zusätzlich trägt, werden NICHT abgezogen -
  die synthetische Reihe ist damit tendenziell optimistischer als ein
  reales gehebeltes/Short-Produkt über denselben Zeitraum gewesen wäre.

Basis-Strategie (TIP-Canary-Signal):
  - TIP (iShares TIPS Bond ETF) dient als "Canary Asset".
  - Für TIP wird der 13612U-Momentum-Score gebildet:
        Score = 1/4 * [ (P0/P1 - 1) + (P0/P3 - 1) + (P0/P6 - 1) + (P0/P12 - 1) ]
    wobei P0 der aktuelle Kurs und P1/P3/P6/P12 die Kurse vor 1/3/6/12
    Monaten sind (siehe Abschnitt "Momentum-Berechnung" unten).
  - Ist der Score > 0 ("Risk-on"), wird in das Risk-Asset investiert
    (siehe "Reale Risk-Assets und Auswahl").
  - Ist der Score <= 0 ("Risk-off"), wird das konfigurierte defensive
    Asset (siehe DEFENSIVE) gehalten - unabhängig von dessen eigenem
    Momentum (sofern es an diesem Tag bereits verfügbar ist, siehe
    unten).

Verfügbarkeit des defensiven Assets (DEFENSIVE_TICKER, FTGB.SG; bei leerem
DEFENSIVE gibt es kein defensives Asset, an allen Risk-off-Tagen gilt dann CASH):
  DEFENSIVE_TICKER wurde erst 2017 aufgelegt. An Risk-off-Tagen VOR
  dessen erstem verfügbaren Handelstag wird CASH gehalten (Rendite 0 %,
  keine Verzinsung). Ab diesem Zeitpunkt wird DEFENSIVE_TICKER in
  Risk-off-Phasen immer gehalten - unabhängig von dessen eigenem
  Momentum. Dadurch ist der Backtest nicht durch die Historie von
  DEFENSIVE_TICKER, sondern nur durch die der RISK_TICKERS und des
  Canary-Assets nach hinten begrenzt (siehe resolve_daily_position(),
  first_valid_date in backtest_tip_canary()).
    Ein Wechsel zwischen Risk-Asset und defensivem Asset wird als
  Verkauf + Neukauf besteuert (siehe Besteuerung unten); der Wechsel
  IN Cash bzw. das Halten von Cash selbst löst dagegen keine Steuer
  aus.

Rebalancing / Whipsaw-Filter (Canary-Signal):
  Das Rohsignal wird für jeden Handelstag des Canary-Assets berechnet.
  Um den Whipsaw-Effekt (viele kurzfristige Hin-und-Her-Wechsel) zu
  reduzieren, wird ein Wechsel der Position (Risk <-> Defensiv) erst
  dann übernommen, wenn das rohe Tagessignal mehrere aufeinander-
  folgende Handelstage dieselbe neue Position anzeigt
  ("Bestätigungsfenster"). Die Fenster sind je Wechselrichtung getrennt:
    CONFIRMATION_A = 1  - Handelstage, die nötig sind, um WEG von
                          RISK zu wechseln (Risk -> Defensiv)
    CONFIRMATION_B = 2  - Handelstage, die nötig sind, um HIN ZU RISK
                          zu wechseln (Defensiv -> Risk)
  Ein Fenster von 1 bedeutet: der Wechsel wird sofort übernommen (siehe
  apply_confirmation_filter()).

Kalender (Master-Kalender):
  Das Signal (Momentum, Rohsignal, Bestätigungsfilter) wird vollständig
  auf dem eigenen Handelskalender des Canary-Assets (TIP, NYSE) be-
  rechnet. Die Ausführung und die Renditen laufen auf einem einzigen
  Master-Kalender, dem Handelskalender des synthetischen Risk-Assets
  (NYSE). Alle anderen Reihen (reale Kandidaten, Defensiv-Asset) werden
  darauf gelegt und an Tagen, an denen ihre Börse geschlossen ist,
  vorwärtsgefüllt: ihre Rendite ist an einem solchen Tag 0, die
  aufgelaufene Bewegung folgt am nächsten Handelstag (es geht nichts
  verloren). Für jeden Tag d des Master-Kalenders gilt die zuletzt
  bestätigte Signalposition des letzten Canary-Handelstags STRENG VOR d
  (kein Look-Ahead: das Signal vom Schlusskurs des Tages t wirkt auf die
  Rendite ab der nächsten Zeile). Vereinfachung: Fällt ein Wechsel auf
  einen Tag, an dem die Börse des betroffenen Assets geschlossen ist,
  wird zum letzten verfügbaren Kurs gewechselt. Vor dem ersten Signaltag
  gilt "DEFENSIVE".

Momentum-Berechnung:
  - TIP (Canary): Der 13612U-Score wird in HANDELSTAGEN berechnet, nicht
    kalendarisch. D.h. P1/P3/P6/P12 sind nicht die letzten verfügbaren
    Kurse an/vor (t - n Kalendermonate), sondern schlicht die Kurse n
    Handelstage zuvor in TIPs eigener Kurshistorie
    (P(t - n Handelstage), per Series.shift(n)):
        1M = 21 Handelstage
        3M = 63 Handelstage
        6M = 126 Handelstage
        12M = 252 Handelstage
    (LOOKBACK_DAYS_CANARY). Damit werden Kalender-/Feiertagseffekte
    vermieden, die bei einer kalendarischen Berechnung dazu führen
    könnten, dass durch Nichthandelstage derselbe Vergleichskurs an
    mehreren aufeinanderfolgenden Handelstagen einbezogen wird.
  - Für das defensive Asset (DEFENSIVE_TICKER) wird KEIN Momentum
    berechnet - es wird ab Verfügbarkeit bedingungslos gehalten. Davor
    wird Cash gehalten (siehe "Verfügbarkeit des defensiven Assets").

Startdatum:
  Da die Lookbacks (insb. 12 Monate/252 Handelstage) eine Vorlaufzeit
  brauchen, beginnt der Backtest am frühestmöglichen Tag des Risk-
  Kalenders mit vollständigem Signal.

Besteuerung:
  Das Script zeigt ausschließlich Ergebnisse NACH deutscher
  Kapitalertragsbesteuerung an. Berücksichtigt werden:
    - Kapitalertragsteuer (Abgeltungsteuer + Soli, jeweils nach Abzug
      der individuellen Teilfreistellung des betroffenen Tickers nach
      § 20 InvStG, siehe TEILFREISTELLUNG-Angabe in CANARY/DEFENSIVE/
      RISK_TICKERS sowie
      capital_gains_tax_rate_for_ticker()) auf
      realisierte Gewinne bei jedem Positionswechsel - dazu zählt
      AUSDRÜCKLICH auch der Wechsel zwischen Risk-Asset und defensivem
      Asset, da es sich um unterschiedliche Wertpapiere
      (unterschiedliche ISINs) handelt und ein Wechsel technisch
      Verkauf + Neukauf bedeutet.
    - Die jährliche Vorabpauschale (siehe
      https://de.wikipedia.org/wiki/Vorabpauschale) für alle über einen
      Jahreswechsel gehaltenen Fondspositionen, ebenfalls je Ticker mit
      dessen individueller Teilfreistellung (siehe
      vorabpauschale_faktor_for_ticker()). Für den Basiszins wird
      bewusst ein fester, zukunftsgerichteter Wert von 2,5% angenommen
      (siehe BASISZINS). Details siehe apply_taxes().

Kursdaten kommen von Yahoo Finance über das gemeinsame Modul
yf_data.py, es wird der "Adj Close" (Adjusted Close) verwendet -
inklusive Vollständigkeitsprüfung gegen den echten Börsenkalender,
Auffüllen bereits bekannter, aber diesmal fehlender Handelstage aus
einer persistenten lokalen Historie sowie Korrektur bekannter,
bestätigter Kurssprünge (z.B. unbereinigte Reverse Splits) - siehe
dortiger Docstring für die Details.

Ergebnisse (Vergleichstabelle, Zusatzkennzahlen, Jahresübersicht) werden
sowohl auf der Konsole ausgegeben als auch gesammelt in eine einzelne
Textdatei geschrieben (siehe OUTPUT_DIR/main()), zusätzlich zu den
beiden Plots (Strategievergleich, Drawdown-Verlauf).

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

from yf_data import (
    BERLIN_TZ,
    compute_query_end_date,
    load_prices,
)

# ----------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------
# Ticker -> {"name": Anzeigename, "teilfreistellung": Satz nach § 20
# InvStG}. Der Ticker (Dictionary-Key) wird für die
# yf-Abfrage verwendet, "name" ausschließlich für die Ausgabe/Plots.
# "teilfreistellung" (siehe capital_gains_tax_rate_for_ticker()/
# vorabpauschale_faktor_for_ticker() unten):
#   0.30 = Aktienfonds (mind. 51% Aktienquote)
#   0.15 = Mischfonds (mind. 25% Aktienquote)
#   0.0  = "sonstige Fonds" (u.a. reine Renten-, Geldmarkt- und
#          Devisenfonds) - KEINE Teilfreistellung.
CANARY = {
    "TIP": {"name": "TIP", "teilfreistellung": 0.0},  # iShares TIPS Bond ETF als Canary-Asset
}
CANARY_TICKER = next(iter(CANARY))

# Das einzige "echte" defensive Asset, das die Strategie im Risk-off-
# Fall AB dessen Erstnotierung hält (davor: Cash). "currency": Notierungswährung ("EUR"/"USD", siehe
# Modul-Docstring "Währungsumrechnung") - KEIN Default. "leverage":
# synthetischer Hebel (auch NEGATIV für eine Short-Position möglich,
# siehe Modul-Docstring "Synthetischer Hebel des Risk-/Defensiv-
# Assets" sowie synthetic_leveraged_series()) - ebenfalls KEIN Default,
# 1.0 = unverändert.
DEFENSIVE = {
    "FTGB.SG": {"name": "First Trust FactorFX", "teilfreistellung": 0.0,
                "leverage": 1.0, "currency": "EUR"},
}
# DEFENSIVE darf auch LEER sein ({}): dann gibt es kein defensives Asset und
# an allen Risk-off-Tagen wird Cash gehalten (Rendite 0 %, keine Steuer);
# DEFENSIVE_TICKER ist dann None.
DEFENSIVE_TICKER = next(iter(DEFENSIVE), None)

# EINE oder MEHRERE Risk-Asset-Varianten (siehe Modul-Docstring "Getestete
# Varianten") - NUR die ERSTE Variante (Dictionary-Reihenfolge) bekommt
# die ausführlichen Zusatz-Tabellen.
#   Der Dictionary-KEY ist ein FREI WÄHLBARER, eindeutiger Varianten-Name
#   (KEIN Yahoo-Ticker).
#   "ticker"/"leverage"/"currency": das SYNTHETISCHE Risk-Asset der
#     Variante (Fallback, siehe Modul-Docstring "Reale Risk-Assets und
#     Auswahl"): Yahoo-Ticker, synthetischer Hebel (1.0 = unverändert,
#     siehe synthetic_leveraged_series()) und Notierungswährung
#     ("EUR"/"USD"). Mehrere Varianten dürfen denselben "ticker"
#     teilen - die Rohkurse werden nur EINMAL abgerufen.
#   "candidates": reale Risk-Assets, aus denen zu Beginn jeder Risk-Phase
#     das mit dem besten 13612U-Momentum gewählt wird. Der KEY ist der
#     Yahoo-Ticker. Je Kandidat: "name" (Anzeigename), "teilfreistellung",
#     "currency" - KEIN Default. Der Hebel steckt im Produkt (keine
#     synthetische Hebelung).
# "ticker"/"leverage"/"currency"/"candidates" sind KEIN Default (analog
# zu "teilfreistellung", siehe _teilfreistellung()).
RISK_TICKERS = {
    "SP500_2x": {"ticker": "SPY", "name": "S&P 500", "teilfreistellung": 0.30,
                 "leverage": 2.0, "currency": "USD",
                 "bh_reference": "18MF.DE",
                 "candidates": {
                     "18MF.DE": {"name": "Amundi MSCI USA (2x)",
                                 "teilfreistellung": 0.30, "currency": "EUR"},
                 }},
    "SP500_1x": {"ticker": "SPY", "name": "S&P 500", "teilfreistellung": 0.30,
                 "leverage": 1.0, "currency": "USD",
                 "bh_reference": "SXR4.DE",
                 "candidates": {
                     "SXR4.DE": {"name": "iShares MSCI USA",
                                 "teilfreistellung": 0.30, "currency": "EUR"},
                 }},
}

# Yahoo-Finance-Ticker für den EUR/USD-Wechselkurs, notiert als "EUR JE
# 1 USD" (siehe Modul-Docstring "Währungsumrechnung",
# load_eur_per_usd()/convert_to_eur()).
FX_TICKER = "EUR=X"

# Kursdaten kommen direkt (ohne Cache) über yf_data.py, siehe dortiger
# Docstring sowie get_adj_close() unten.
# Ausführliche Risk-Phasen-Tabelle (Start, Ende, Tage, Asset, Rendite je Phase)
# in der Auswertung ausgeben? Standard: aus - die Defensiv-Phasen-Tabelle
# ist der aussagekräftige Teil, die Risk-Phasen stehen als Mittelwert in der
# Tabelle "Durchschnittliche Phasen-Rendite".
SHOW_RISK_PHASES = False

OUTPUT_DIR = Path("backtest")
OUTPUT_DIR.mkdir(exist_ok=True)

# Lookbacks in HANDELSTAGEN für den 13612U-Score des Canary-Assets
# (TIP): 1M/3M/6M/12M = 21/63/126/252 Handelstage, gezählt in TIPs
# eigener Kurshistorie.
LOOKBACK_DAYS_CANARY = (21, 63, 126, 252)
# Für das defensive Asset wird kein Momentum berechnet (siehe
# Modul-Docstring "Verfügbarkeit des defensiven Assets"): vor dessen
# Börsengang wird Cash gehalten, danach wird es bedingungslos gehalten.

# Whipsaw-/Bestätigungsfenster (in Handelstagen) des TIP-Canary-
# Signals, GETRENNT je Wechselrichtung (siehe Modul-Docstring
# "Rebalancing / Whipsaw-Filter").
CONFIRMATION_A = 1  # Risk -> Defensiv
CONFIRMATION_B = 2  # Defensiv -> Risk

# Nasdaq-100-SMA-Signal (Veto in TIP-Defensiv-Phasen), eigener Whipsaw-Filter
# (getrennt vom TIP). Signalquelle: Preisindex ^NDX (USD, nur Signal - es wird
# nicht gehandelt, daher keine Währungsumrechnung).
TREND_TICKER = "^NDX"
TREND_SMA_DAYS = 200
TREND_CONFIRMATION_A = 1  # SMA-Signal: Risk -> Defensiv (Kurs unter SMA)
TREND_CONFIRMATION_B = 1  # SMA-Signal: Defensiv -> Risk (Kurs über SMA)

# Anzeigenamen der Strategien (Reihenfolge = Ausgabe-Reihenfolge)
STRATEGY_NAMES = {"hybrid": "TIP+SMA", "tip": "TIP", "sma": "SMA"}

TRADING_DAYS_PER_YEAR = 252

# Deutsche Kapitalertragsteuer auf realisierte Gewinne beim Verkauf von
# Wertpapieren (Abgeltungsteuer 25% + Solidaritätszuschlag 5,5% darauf
# = 25% * 1,055 = 26,375%, unreduzierter Satz vor Teilfreistellung).
# Kirchensteuer ist NICHT berücksichtigt.
ABGELTUNGSTEUER_BASISSATZ = 0.26375
APPLY_CAPITAL_GAINS_TAX = True


def _teilfreistellung(ticker: str) -> float:
    """Teilfreistellung für `ticker` nach § 20 InvStG - nachgeschlagen
    in CANARY/DEFENSIVE/RISK_TICKERS sowie den "candidates" aller
    Varianten (siehe dort). KEIN Default: jeder für Steuerzwecke
    verwendete Ticker muss dort explizit mit seiner Teilfreistellung
    eingetragen sein, ein stiller Fallback-Wert würde bei einem
    vergessenen Eintrag eine falsche Steuerannahme verschleiern statt
    sie sichtbar zu machen. Bei RISK_TICKERS ist `ticker` hier der
    Dictionary-KEY (der frei wählbare Varianten-Name, NICHT zwingend der
    Yahoo-Ticker), bei den Kandidaten der Yahoo-Ticker; main() reicht
    konsequent diese Schlüssel durch (siehe run_single_backtest())."""
    for group in (CANARY, DEFENSIVE, RISK_TICKERS,
                  *(info["candidates"] for info in RISK_TICKERS.values())):
        if ticker in group:
            return group[ticker]["teilfreistellung"]
    raise KeyError(
        f"{ticker}: keine Teilfreistellung hinterlegt - bitte in CANARY, DEFENSIVE, "
        f"RISK_TICKERS oder bei den candidates mit \"teilfreistellung\" eintragen."
    )


def capital_gains_tax_rate_for_ticker(ticker: str) -> float:
    """Effektiver Kapitalertragsteuersatz für `ticker`, nach Abzug
    seiner individuellen Teilfreistellung (siehe ABGELTUNGSTEUER_BASISSATZ,
    _teilfreistellung())."""
    return ABGELTUNGSTEUER_BASISSATZ * (1.0 - _teilfreistellung(ticker))


def vorabpauschale_faktor_for_ticker(ticker: str) -> float:
    """Faktor (1 - Teilfreistellung), mit dem der Vorabpauschale-
    Basisertrag für `ticker` multipliziert wird (siehe apply_taxes())."""
    return 1.0 - _teilfreistellung(ticker)


# Vorabpauschale (jährliche Vorwegbesteuerung thesaurierender/nicht
# ausschüttender Fondsanteile, siehe
# https://de.wikipedia.org/wiki/Vorabpauschale).
BASISZINS = 0.025
APPLY_VORABPAUSCHALE = True


# ----------------------------------------------------------------------
# Kursdaten laden (Download und Vollständigkeitsprüfung gegen den echten
# Börsenkalender kommen aus yf_data.py, siehe dortiger Docstring)
# ----------------------------------------------------------------------

# Börsenkalender-Vollständigkeitsprüfung und der Sicherheits-Cutoff
# für einen ggf. noch unfertigen heutigen Kurs laufen vollständig
# innerhalb von load_prices() (siehe yf_data.py) - dieses Skript übergibt
# dafür nur Ticker und Zeitfenster.


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


def synthetic_leveraged_series(base_adj: pd.Series, leverage: float) -> pd.Series:
    """Baut künstlich eine `leverage`-fach gehebelte Kursreihe aus
    `base_adj`, indem die TÄGLICHEN Renditen von `base_adj` mit
    `leverage` multipliziert und anschließend aufsummiert (compoundiert)
    werden - analog zu real gehandelten Hebelprodukten, die TÄGLICH auf
    den Ziel-Hebel zurückgesetzt werden (daily rebalancing). Das bildet
    insbesondere den bekannten "Volatility-Decay"-Effekt ab
    (Pfadabhängigkeit). Für leverage == 1.0 werden unverändert die
    Original-Kurswerte zurückgegeben (siehe Aufrufstelle in main()) -
    diese Funktion wird für diesen Fall gar nicht erst aufgerufen.

    `leverage` darf auch NEGATIV sein (siehe Modul-Docstring
    "Synthetischer Hebel des Risk-/Defensiv-Assets") - das bildet eine
    synthetische SHORT-Position ab: die TÄGLICHE Rendite von `base_adj`
    wird mit dem (negativen) Hebel multipliziert, d.h. steigt `base_adj`
    an einem Tag, FÄLLT die synthetische Reihe entsprechend gehebelt
    (und umgekehrt) - exakt dieselbe tägliche Reset-/Compounding-Logik
    wie bei positivem Hebel, nur mit umgekehrtem Vorzeichen. Der
    "Volatility-Decay"-Effekt gilt unverändert auch hier (eine Short-
    Position verliert bei einer volatilen, aber per Saldo seitwärts
    laufenden Basis-Kursreihe ebenso an Wert wie eine Long-Position).
    leverage == 0 ist NICHT sinnvoll (entspräche einer konstant flachen
    Kursreihe) und wird deshalb abgelehnt.

    Vereinfachung/Caveat: reale Hebelprodukte tragen zusätzlich
    laufende Kosten (TER) und einen Finanzierungskostensatz für den
    geliehenen Hebel-Anteil - beides wird hier NICHT abgezogen. Die
    synthetische Reihe ist also tendenziell optimistischer als ein
    reales gehebeltes Produkt über denselben Zeitraum gewesen wäre
    (siehe Modul-Docstring "Synthetischer Hebel des Risk-/Defensiv-Assets")."""
    if leverage == 0:
        raise ValueError("leverage darf nicht 0 sein.")
    base_returns = base_adj.pct_change().fillna(0.0)
    lev_returns = leverage * base_returns
    lev_index = (1.0 + lev_returns).cumprod()
    lev_index = lev_index / lev_index.iloc[0] * base_adj.iloc[0]
    return lev_index


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


def convert_to_eur(adj_close: pd.Series, currency: str, eur_per_usd: pd.Series) -> pd.Series:
    """Rechnet `adj_close` nach EUR um, sofern `currency == "USD"`
    (Multiplikation mit dem auf den Handelskalender von `adj_close`
    vorwärtsgefüllten EUR/USD-Kurs, siehe load_eur_per_usd()) - bei
    `currency == "EUR"` unverändert zurückgegeben (No-Op, hält den
    Aufruf an dieser Stelle trotzdem einheitlich für alle Ticker,
    siehe Aufrufstellen in main()). Andere Währungen sind (noch) nicht
    unterstützt.

    Reicht die Kurshistorie von `adj_close` weiter zurück als die von
    `eur_per_usd` (typischer Fall: ein Index-Ticker mit sehr langer
    Historie wie ^892400-USD-STRD gegenüber der kürzeren EUR=X-Historie
    auf Yahoo Finance), wird `adj_close` auf den ab dann gemeinsam
    abgedeckten Zeitraum EINGESCHRÄNKT (siehe Modul-Docstring
    "Währungsumrechnung") - die frühere, nicht umrechenbare Historie
    entfällt ersatzlos, first_valid_date in backtest_tip_canary()
    berücksichtigt das automatisch. Eine Lücke INNERHALB der
    EUR=X-Historie wird dagegen (wie bei jeder anderen Kalender-
    Angleichung in diesem Skript, z.B. defensive_on_calendar) über
    Vorwärtsfüllung überbrückt, löst also KEINEN Fehler aus - nur wenn
    für ein Datum in `adj_close` auch nach Vorwärtsfüllung kein
    EUR/USD-Kurs vorliegt (z.B. eine komplett leere FX-Reihe), wird
    weiterhin ein Fehler geworfen."""
    if currency == "EUR":
        return adj_close
    if currency != "USD":
        raise ValueError(f"Nicht unterstützte Währung: {currency!r} (erwartet 'EUR' oder 'USD').")

    fx_start = eur_per_usd.index.min()
    if adj_close.index.min() < fx_start:
        cutoff = adj_close.index[adj_close.index >= fx_start]
        if cutoff.empty:
            raise ValueError(
                f"convert_to_eur: {FX_TICKER}-Historie beginnt erst {fx_start.date()} - "
                f"das liegt komplett NACH dem Ende der umzurechnenden Kursreihe "
                f"({adj_close.index.max().date()}), keine Überschneidung."
            )
        print(f"[info]     Kurshistorie wegen kürzerer {FX_TICKER}-Historie eingeschränkt: "
              f"{adj_close.index.min().date()} -> {cutoff[0].date()}.")
        adj_close = adj_close.loc[adj_close.index >= fx_start]

    fx_on_calendar = eur_per_usd.reindex(adj_close.index, method="ffill")
    if fx_on_calendar.isna().any():
        missing = fx_on_calendar.index[fx_on_calendar.isna()]
        raise ValueError(
            f"convert_to_eur: kein EUR/USD-Kurs verfügbar für "
            f"{missing[0].date()} (auch nach Vorwärtsfüllung nicht) - bitte "
            f"{FX_TICKER}-Kursdaten prüfen."
        )
    return adj_close * fx_on_calendar


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
    Rein makro-seitig - ob "DEFENSIVE" an einem gegebenen Tag
    tatsächlich das defensive Asset bedeutet oder (mangels dessen
    Verfügbarkeit) CASH, wird erst in
    backtest_tip_canary() über resolve_daily_position() entschieden.
    """
    risk_on = canary_mom > 0
    position = pd.Series("DEFENSIVE", index=canary_mom.index, dtype=object)
    position[risk_on] = "RISK"
    return position


def resolve_daily_position(macro_position: pd.Series,
                            defensive_first_date: pd.Timestamp,
                            candidate_scores: dict[str, pd.Series],
                            ) -> tuple[pd.Series, list[dict]]:
    """Übersetzt das makro-seitige RISK/DEFENSIVE-Signal in die
    tatsächlich zu haltende Position (siehe Modul-Docstring
    "Verfügbarkeit des defensiven Assets" und "Reale Risk-Assets und
    Auswahl"):
      macro == "DEFENSIVE" und Datum >= defensive_first_date -> "DEFENSIVE"
      macro == "DEFENSIVE" und Datum <  defensive_first_date -> "CASH"
      macro == "RISK"                                        -> Kandidat
                         (Ticker) mit dem höchsten Score zu Beginn der
                         Risk-Phase, sonst "RISK" (synthetisches Asset)

    `candidate_scores`: Ticker -> 13612U-Momentum auf dem Kalender von
    `macro_position`, BEREITS so verschoben, dass die Zeile d den Wert vom
    Schlusskurs der Vorzeile (= Signaltag) enthält. Eine Risk-Phase ist
    eine maximale Folge aufeinanderfolgender RISK-Zeilen. Ihr Asset wird
    in der ersten Zeile gewählt (nur Kandidaten mit vorhandenem Score)
    und bis zum Ende der Phase beibehalten.

    Rückgabe: (daily_position, choices) - choices ist je Risk-Phase ein
    dict {"start", "chosen", "scores"} (Scores der zur Wahl stehenden
    Kandidaten) für die Auswertung in format_risk_phase_detail_table()."""
    values = macro_position.to_numpy().copy()
    dates = macro_position.index
    is_risk = values == "RISK"
    cash_days = (values == "DEFENSIVE") & np.asarray(dates < defensive_first_date)
    values[cash_days] = "CASH"

    score_arrays = {t: s.reindex(dates).to_numpy(dtype=float) for t, s in candidate_scores.items()}
    choices: list[dict] = []
    n = len(values)
    i = 0
    while i < n:
        if not is_risk[i]:
            i += 1
            continue
        j = i
        while j < n and is_risk[j]:
            j += 1
        available = {t: arr[i] for t, arr in score_arrays.items() if not np.isnan(arr[i])}
        chosen = max(available, key=available.get) if available else "RISK"
        values[i:j] = chosen
        choices.append({"start": dates[i], "chosen": chosen, "scores": available})
        i = j

    return pd.Series(values, index=dates), choices


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
                 ) -> tuple[pd.Series, pd.Series, pd.Series]:
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
       Wird fällig, sobald eine Wertpapier-Position über einen
       Jahreswechsel hinweg gehalten wird (Stichtag: Bestand am
       Jahresende, hier approximiert durch den letzten Handelstag des
       Jahres in den Kursdaten). Vereinfachte Berechnung:
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

    Parameter:
      daily_position      - Serie mit der je Handelstag gehaltenen
                             Position (z.B. "RISK"/"DEFENSIVE"/"CASH").
      returns_by_position - dict: Positionswert -> zugehörige
                             Tagesrendite-Serie.

    Rückgabe:
      equity_after_tax        - tägliche Wertentwicklung nach Steuern
                                 (Start = 1.0)
      capital_gains_tax_paid  - am jeweiligen Tag gezahlte
                                 Kapitalertragsteuer bei Wechsel/Verkauf
      vorabpauschale_tax_paid - am jeweiligen Tag gezahlte Steuer auf
                                 die Vorabpauschale
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

    equity_after_tax = np.empty(len(dates))
    capital_gains_tax_paid = np.zeros(len(dates))
    vorabpauschale_tax_paid = np.zeros(len(dates))

    current_equity = 1.0
    cost_basis = 1.0
    purchase_date = dates[0]
    value_at_year_start = 1.0
    prev_position = None

    for i, date in enumerate(dates):
        pos = positions[i]

        # --- 1) Jahreswechsel: Vorabpauschale auf die zum Jahresende
        #     (= vorheriger Handelstag) gehaltene Wertpapier-Position ---
        if (apply_vorabpauschale and i > 0
                and years[i] != years[i - 1]
                and prev_position is not None
                and prev_position in returns_by_position):
            year_ended = int(years[i - 1])
            start_of_year = pd.Timestamp(year=year_ended, month=1, day=1)
            period_start = max(purchase_date, start_of_year)
            full_months_held = min(max(12 - period_start.month + 1, 0), 12)

            basisertrag = (value_at_year_start * basiszins
                           * vorabpauschale_faktor_by_position[prev_position]
                           * full_months_held / 12.0)
            wertzuwachs = current_equity - value_at_year_start
            vorabpauschale = max(0.0, min(basisertrag, wertzuwachs))

            if vorabpauschale > 0:
                tax = vorabpauschale * tax_rate_by_position[prev_position]
                current_equity -= tax
                cost_basis += vorabpauschale
                vorabpauschale_tax_paid[i] = tax

            value_at_year_start = current_equity

        # --- 2) Positionswechsel: Kapitalertragsteuer auf Gewinn seit
        #     letztem Kauf/Wechsel ---
        if (apply_capital_gains_tax and prev_position is not None
                and pos != prev_position):
            if prev_position in returns_by_position:
                gain = current_equity - cost_basis
                if gain > 0:
                    tax = gain * tax_rate_by_position[prev_position]
                    current_equity -= tax
                    capital_gains_tax_paid[i] = tax
            cost_basis = current_equity
            purchase_date = date
            value_at_year_start = current_equity

        # --- 3) Tagesrendite der aktuell gehaltenen Position anwenden ---
        r = return_arrays[pos][i] if pos in return_arrays else 0.0
        current_equity *= (1.0 + r)

        equity_after_tax[i] = current_equity
        prev_position = pos

    return (pd.Series(equity_after_tax, index=dates),
            pd.Series(capital_gains_tax_paid, index=dates),
            pd.Series(vorabpauschale_tax_paid, index=dates))


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
    defensive_adj: pd.Series | None,
    a: int,
    b: int,
    candidate_adj_by_ticker: dict[str, pd.Series],
    candidate_mom_by_ticker: dict[str, pd.Series],
    trend_adj: pd.Series,
    mode: str = "hybrid",
    trend_a: int = TREND_CONFIRMATION_A,
    trend_b: int = TREND_CONFIRMATION_B,
    trend_sma_days: int = TREND_SMA_DAYS,
    lookback_days_canary: tuple[int, ...] = LOOKBACK_DAYS_CANARY,
) -> dict:
    """
    Führt den Backtest der TIP-Canary-Strategie für EINE Risk-Asset-
    Variante mit getrennten Bestätigungsfenstern `a`/`b` je
    Wechselrichtung durch (siehe apply_confirmation_filter()). Solange
    das Signal "Risk-on" meldet, wird zu Beginn jeder Risk-Phase einer der
    Kandidaten (`candidate_adj_by_ticker`) oder - mangels Kandidat mit
    Momentum - das synthetische Asset `risky_adj` gewählt und die ganze
    Phase gehalten (siehe resolve_daily_position()).

    `risky_adj`/`defensive_adj`/`candidate_adj_by_ticker` werden in EUR
    erwartet (Umrechnung ist Aufgabe des Aufrufers, siehe main()/
    convert_to_eur()). `candidate_mom_by_ticker` enthält das 13612U-
    Momentum jedes Kandidaten auf dessen EIGENEM Handelskalender. Der
    Kalender von `risky_adj` ist der Master-Kalender (siehe Modul-
    Docstring "Kalender").

    Ablauf (Kalender siehe Modul-Docstring "Kalender"):
      1) Auf dem Handelskalender von `canary_adj`: 13612U-Score ->
         Rohsignal (Score > 0 -> RISK, sonst DEFENSIVE) -> Whipsaw-Filter
         (`a`: Risk -> Defensiv, `b`: Defensiv -> Risk) -> bestätigte
         Signalposition (RISK/DEFENSIVE).
      2) Übertragung auf den Master-Kalender (`risky_adj`): jede Zeile d
         erhält die bestätigte Position des letzten Signaltags STRENG
         VOR d. Vor dem ersten Signaltag gilt DEFENSIVE.
      3) resolve_daily_position() konkretisiert die Position: RISK ->
         gewählter Kandidat bzw. synthetisches Asset (je Risk-Phase),
         DEFENSIVE -> das defensive Asset ab dessen erstem Handelstag,
         davor CASH.
      4) Die Rendite einer Zeile d ist die Tagesrendite der in d
         gehaltenen Position (CASH: 0).

    Rückgabe: dict mit
      equity                - tägliche Wertentwicklung (Start = 1.0, VOR
                              Steuern), Kalender des Risk-Assets
      confirmed_position    - bestätigtes Makrosignal (RISK/DEFENSIVE),
                              auf den Risk-Kalender vorwärtsgefüllt (die
                              Zeile d zeigt hier das Signal von d selbst,
                              nur für Kennzahlen; nicht um einen Tag
                              versetzt und nicht aufgelöst)
      daily_position        - konkret gehaltene Position je Zeile des
                              Master-Kalenders (RISK = synthetisches
                              Asset / <Kandidaten-Ticker> / DEFENSIVE /
                              CASH); bestimmt die Rendite dieser Zeile
      risk_choices          - Auswahl je Risk-Phase (siehe
                              resolve_daily_position())
      canary_mom            - Momentum-Score des Canary-Assets, auf den
                              Risk-Kalender vorwärtsgefüllt
      defensive_first_date  - erster Handelstag von `defensive_adj`
                              (Grenze für den CASH-Zeitraum); ohne
                              defensives Asset (`defensive_adj` None):
                              Tag nach dem Kalenderende, d.h. immer CASH
      returns_by_position   - Tagesrenditen je Position für apply_taxes()
      first_valid_date      - erster Tag mit vollständigem Signal
    """
    trading_calendar = risky_adj.index
    has_defensive = defensive_adj is not None and len(defensive_adj) > 0
    # Ohne defensives Asset (DEFENSIVE = {}): "erster Handelstag" liegt hinter
    # dem Ende des Kalenders -> resolve_daily_position() macht aus JEDEM
    # DEFENSIVE-Tag CASH.
    defensive_first_date = (defensive_adj.index.min() if has_defensive
                            else trading_calendar[-1] + pd.Timedelta(days=1))

    # --- Signal auf dem EIGENEN Kalender des Canary-Assets (TIP) ---
    # Momentum, Rohsignal und Whipsaw-Filter laufen ausschließlich auf den
    # Handelstagen von TIP - unabhängig vom Kalender des Risk-Assets.
    canary_mom = momentum_13612u_trading_days(canary_adj, lookback_days_canary)
    signal_start = canary_mom.first_valid_index()
    if signal_start is None:
        raise ValueError("Zu wenig gemeinsame Historie für die gewählten Lookbacks.")
    canary_mom_signal = canary_mom.loc[canary_mom.index >= signal_start]
    raw_position = raw_target_position(canary_mom_signal)
    signal_position = apply_confirmation_filter(raw_position, a, b)

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
    # `mode` wählt TIP allein, SMA allein oder den Hybrid (siehe combine_macro()).
    trend_signal = trend_signal_position(trend_adj, trend_sma_days, trend_a, trend_b)
    tip_macro = signal_to_master_calendar(signal_position, trading_calendar)
    trend_macro = signal_to_master_calendar(trend_signal, trading_calendar)
    macro_daily_position = combine_macro(tip_macro, trend_macro, mode)

    # Auf den Risk-Kalender ausgerichtete Ansichten (nur für Kennzahlen).
    tip_conf = signal_position.reindex(trading_calendar, method="ffill").fillna("DEFENSIVE")
    trend_conf = trend_signal.reindex(trading_calendar, method="ffill").fillna("DEFENSIVE")
    confirmed_position = combine_macro(tip_conf, trend_conf, mode)
    confirmed_position = confirmed_position.loc[confirmed_position.index >= first_valid_date]
    canary_mom_cal = canary_mom.reindex(trading_calendar, method="ffill")
    canary_mom_cal = canary_mom_cal.loc[canary_mom_cal.index >= first_valid_date]

    # Momentum der Kandidaten: vom eigenen Kalender auf den Master-
    # Kalender gelegt (vorwärtsgefüllt) und um EINE Zeile verschoben, damit
    # die Zeile d den Wert vom Schlusskurs der Vorzeile (Signaltag) enthält.
    candidate_scores = {t: mom.reindex(trading_calendar, method="ffill").shift(1)
                        for t, mom in candidate_mom_by_ticker.items()}
    daily_position, risk_choices = resolve_daily_position(
        macro_daily_position, defensive_first_date, candidate_scores)

    risky_returns = risky_adj.pct_change().fillna(0.0)
    returns_by_position = {"RISK": risky_returns}
    if has_defensive:
        defensive_on_calendar = defensive_adj.reindex(trading_calendar).ffill()
        returns_by_position["DEFENSIVE"] = defensive_on_calendar.pct_change().fillna(0.0)
    for ticker, adj in candidate_adj_by_ticker.items():
        on_calendar = adj.reindex(trading_calendar).ffill()
        returns_by_position[ticker] = on_calendar.pct_change().fillna(0.0)

    strategy_returns = pd.Series(0.0, index=daily_position.index)
    for label, returns in returns_by_position.items():
        mask = daily_position == label
        strategy_returns[mask] = returns[mask]
    # "CASH" ist absichtlich nicht in returns_by_position enthalten ->
    # bleibt bei der Initialisierung mit 0.0.

    equity = (1.0 + strategy_returns).cumprod()
    equity = equity.loc[equity.index >= first_valid_date]
    equity = equity / equity.iloc[0]

    return {
        "equity": equity,
        "confirmed_position": confirmed_position,
        "daily_position": daily_position,
        "risk_choices": risk_choices,
        "canary_mom": canary_mom_cal,
        "defensive_first_date": defensive_first_date,
        "returns_by_position": returns_by_position,
        "first_valid_date": first_valid_date,
        "tip_macro": tip_macro,
        "trend_macro": trend_macro,
    }


def buy_and_hold_after_tax(adj_close: pd.Series, ticker: str,
                            start_date: pd.Timestamp | None = None) -> pd.Series:
    """Buy & Hold-Kurve NACH Steuern (Vorabpauschale über Jahreswechsel
    hinweg; da nie verkauft wird, fällt keine Kapitalertragsteuer an -
    wohl aber die jährliche Vorabpauschale, siehe apply_taxes()).
    `ticker` bestimmt die individuelle Teilfreistellung (siehe
    _teilfreistellung())."""
    returns_full = adj_close.pct_change()
    if start_date is not None:
        returns = returns_full.loc[returns_full.index >= start_date].copy()
        if len(returns) > 0 and pd.isna(returns.iloc[0]):
            # start_date ist der allererste verfügbare Handelstag dieses
            # Tickers - es gibt keinen Vortageskurs, aus dem sich eine
            # Rendite für diesen Tag berechnen ließe. Der erste Tag wird
            # daher mit Rendite 0 behandelt (Kauf zum Schlusskurs dieses
            # Tages, noch kein Wertzuwachs), statt NaN: NaN würde über
            # die multiplikative Verkettung in apply_taxes() (ein
            # einzelner, laufend multiplizierter Skalar - kein
            # NaN-sicheres cumprod) die gesamte Equity-Kurve ab diesem
            # Punkt auf NaN setzen.
            returns.iloc[0] = 0.0
    else:
        returns = returns_full.dropna().copy()
    if returns.isna().any():
        bad_dates = returns.index[returns.isna()]
        raise ValueError(
            f"buy_and_hold_after_tax: unerwartete NaN-Rendite(n) am "
            f"{', '.join(d.date().isoformat() for d in bad_dates[:5])} - Kursdaten prüfen."
        )
    daily_position = pd.Series("RISK", index=returns.index)
    equity_after_tax, _, _ = apply_taxes(
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


def yearly_stats(equity: pd.Series,
                  periods_per_year: int = TRADING_DAYS_PER_YEAR) -> dict[int, dict[str, float]]:
    """Wie performance_stats(), aber je Kalenderjahr statt für den
    gesamten Zeitraum: Rendite (%), Volatilität p.a. und Max Drawdown.
    Für die Rendite eines Jahres wird als Startwert der letzte
    verfügbare Equity-Wert VOR Jahresbeginn verwendet (bzw. der erste
    verfügbare Wert im Jahr selbst, falls es das erste Jahr der Kurve
    ist) - das Jahresergebnis bildet damit exakt den in diesem
    Kalenderjahr erzielten Wertzuwachs ab. Volatilität wird aus den
    Tagesrenditen INNERHALB des Jahres berechnet (inkl. der Rendite des
    ersten Handelstags, die sich aus dem Übergang vom Vorjahr ergibt).
    Der Max Drawdown wird ebenfalls nur innerhalb des Jahres gemessen,
    mit dem Jahresstartwert als erstem (und damit höchstmöglichem)
    Punkt des Laufenden Maximums - ein in einem Vorjahr aufgelaufener
    Drawdown wirkt sich also nicht auf ein späteres Jahr aus."""
    returns_full = equity.pct_change()
    years = sorted(set(equity.index.year))
    result: dict[int, dict[str, float]] = {}

    for y in years:
        year_dates = equity.index[equity.index.year == y]
        prior_dates = equity.index[equity.index < year_dates[0]]
        start_date = prior_dates[-1] if len(prior_dates) else year_dates[0]
        start_equity = float(equity.loc[start_date])
        end_equity = float(equity.loc[year_dates[-1]])
        return_pct = end_equity / start_equity - 1.0

        year_returns = returns_full.loc[year_dates]
        ann_vol = year_returns.std() * np.sqrt(periods_per_year)

        year_equity = equity.loc[year_dates]
        if start_date not in year_equity.index:
            year_equity = pd.concat([pd.Series([start_equity], index=[start_date]), year_equity])
        running_max = year_equity.cummax()
        drawdown = year_equity / running_max - 1.0
        max_dd = drawdown.min()

        result[y] = {
            "Rendite (%)": return_pct,
            "Volatilität p.a.": ann_vol,
            "Max Drawdown": max_dd,
        }

    return result


def format_yearly_comparison_table(canary_equity: pd.Series, bh_equity: pd.Series,
                                    name: str = "TIP") -> str:
    """Listet pro Kalenderjahr zunächst die Rendite von TIP-Canary
    (TIP-Rend.) und Buy&Hold (B&H-Rend.) selbst, gefolgt von deren
    DIFFERENZ (Δ Rendite = TIP-Canary minus Buy&Hold), plus einer
    Gewinner-Spalte. Ein positives Delta ist ein Vorteil für TIP-Canary
    (höhere Rendite als B&H) in diesem Jahr. Die Gewinner-Spalte richtet
    sich entsprechend nach dieser Rendite-Differenz.

    Eine abschließende "Gesamt"-Zeile zeigt bei Δ Rendite NICHT die
    Summe der einzelnen Jahreswerte (das wäre wegen des
    Zinseszinseffekts irreführend), sondern die Differenz der
    GESAMTZEIT-Rendite aus performance_stats() über den kompletten
    Backtest-Zeitraum - also dieselbe Gesamtzahl, die bereits weiter
    oben in der Kennzahlen-Tabelle steht. Die TIP-Rend.-/B&H-Rend.-
    Spalten zeigen in dieser Zeile entsprechend ebenfalls die jeweilige
    Gesamtrendite statt einer Summe der Jahresrenditen. Die
    Gewinner-Spalte zählt weiterhin, in wie vielen EINZELNEN Jahren
    TIP-Canary bzw. B&H vorne lag - das ist unabhängig von der
    (zinseszins-bereinigten) Gesamtbetrachtung eine eigene, ergänzende
    Information.

    Eine Durchschnittszeile über TIP-Rend., B&H-Rend. und Δ Rendite
    (für die Gewinner-Spalte gibt es kein sinnvolles Analogon) rundet
    die Tabelle ab. Auf einen Median wird bewusst verzichtet: bei einer
    Regime-Strategie wie dieser stammt die Outperformance typischerweise
    aus wenigen dominanten Phasen, wodurch der Median eher irreführend
    als aussagekräftig wäre."""
    canary_yearly = yearly_stats(canary_equity)
    bh_yearly = yearly_stats(bh_equity)
    years = sorted(set(canary_yearly) & set(bh_yearly))

    def _fmt_pct(v: float) -> str:
        return f"{v:+.1%}" if pd.notna(v) else "n/a"

    lines = ["\nJahresweise Kennzahlen:"]
    header = (f"  {'Jahr':<14}"
              f"{name + '-Rend.':>14}{'B&H-Rend.':>14}"
              f"{'Δ Rendite':>16}{'Gewinner':>22}")
    lines.append(header)
    lines.append("-" * len(header))
    n_tip = n_bh = 0
    all_tip_returns, all_bh_returns = [], []
    all_returns = []
    for y in years:
        c, b = canary_yearly[y], bh_yearly[y]
        d_return = c["Rendite (%)"] - b["Rendite (%)"]
        winner = name if d_return > 0 else ("B&H" if d_return < 0 else "=")
        if winner == name:
            n_tip += 1
        elif winner == "B&H":
            n_bh += 1
        all_tip_returns.append(c["Rendite (%)"])
        all_bh_returns.append(b["Rendite (%)"])
        all_returns.append(d_return)
        lines.append(f"  {y:<14}"
                      f"{_fmt_pct(c['Rendite (%)']):>14}{_fmt_pct(b['Rendite (%)']):>14}"
                      f"{_fmt_pct(d_return):>16}"
                      f"{winner:>22}")

    # Gesamt-Zeile: Differenz der GESAMTZEIT-Rendite (siehe Docstring),
    # nicht die Summe der Jahreswerte.
    tip_total = performance_stats(canary_equity)
    bh_total = performance_stats(bh_equity)
    total_d_return = tip_total["Rendite"] - bh_total["Rendite"]

    lines.append("-" * len(header))
    lines.append(f"  {'Gesamt':<14}"
                  f"{_fmt_pct(tip_total['Rendite']):>14}{_fmt_pct(bh_total['Rendite']):>14}"
                  f"{_fmt_pct(total_d_return):>16}"
                  f"{f'{n_tip} {name} / {n_bh} B&H':>22}")

    # Durchschnitt über TIP-Rend., B&H-Rend. und Δ Rendite - für die
    # Gewinner-Zählung gibt es dort kein sinnvolles Analogon. Auf einen
    # Median wird bewusst verzichtet: bei einer Regime-Strategie wie
    # dieser stammt die Outperformance typischerweise aus wenigen
    # dominanten Phasen, wodurch der Median eher irreführend als
    # aussagekräftig wäre.
    if all_returns:
        lines.append(f"  {'Durchschnitt':<14}"
                      f"{_fmt_pct(np.mean(all_tip_returns)):>14}"
                      f"{_fmt_pct(np.mean(all_bh_returns)):>14}"
                      f"{_fmt_pct(np.mean(all_returns)):>16}")
    return "\n".join(lines)


def signal_stats(daily_position: pd.Series, position: pd.Series,
                  risk_labels: tuple[str, ...],
                  start_date: pd.Timestamp | None = None) -> dict[str, float]:
    """Kennzahlen zur Signal-Nutzung: Zeitanteile in Risk/DEFENSIVE/CASH
    (gemessen an Handelstagen) sowie Anzahl der bestätigten
    Regime-Wechsel (Signalwechsel). `risk_labels` sind die Positions-
    Labels, die ein Risk-Asset bedeuten ("RISK" = synthetisch sowie die
    Kandidaten-Ticker). "Zeit im defensiven Asset" zählt die Tage mit dem
    echten DEFENSIVE_TICKER, "Zeit in Cash" die Risk-off-Tage vor dessen
    Erstnotierung (siehe resolve_daily_position()). "asset_shares"
    schlüsselt den Risk-Anteil je Label auf (siehe format_extra_metrics())."""
    if start_date is not None:
        daily_position = daily_position.loc[daily_position.index >= start_date]
        position = position.loc[position.index >= start_date]

    total_days = len(daily_position)
    counts = daily_position.value_counts()
    asset_shares = {label: (counts.get(label, 0) / total_days if total_days else np.nan)
                    for label in risk_labels}
    share_risk = (sum(counts.get(label, 0) for label in risk_labels) / total_days
                  if total_days else np.nan)
    share_defensive = counts.get("DEFENSIVE", 0) / total_days if total_days else np.nan
    share_cash = counts.get("CASH", 0) / total_days if total_days else np.nan

    n_changes = int((position != position.shift(1)).sum() - 1) if len(position) > 0 else 0
    n_changes = max(n_changes, 0)

    return {
        "Zeit im Risk-Asset": share_risk,
        "Zeit im defensiven Asset": share_defensive,
        "Zeit in Cash": share_cash,
        "asset_shares": asset_shares,
        "Regime-Changes (Anzahl)": n_changes,
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
# Backtest-Lauf (festes k, festes Risk-Asset)
# ----------------------------------------------------------------------
def run_single_backtest(canary_adj: pd.Series,
                         risky_adj: pd.Series,
                         risky_ticker: str,
                         defensive_adj: pd.Series | None,
                         defensive_ticker: str | None,
                         a: int,
                         b: int,
                         candidate_adj_by_ticker: dict[str, pd.Series],
                         candidate_mom_by_ticker: dict[str, pd.Series],
                         common_start: pd.Timestamp | None,
                         trend_adj: pd.Series,
                         mode: str = "hybrid") -> dict:
    """Führt einen kompletten Backtest (inkl. Steuern) für feste `a`/`b`
    (Whipsaw-Bestätigungsfenster, siehe apply_confirmation_filter())
    und ein festes Risk-Asset durch und liefert Kennzahlen +
    Equity-Kurve NACH Steuern zurück. `risky_ticker`/`defensive_ticker`
    bestimmen die jeweils individuelle Teilfreistellung (siehe
    _teilfreistellung()); jeder Kandidat bekommt seine eigene, über
    "candidates" hinterlegte Teilfreistellung - die Positionen können
    unterschiedlich besteuert werden."""
    result = backtest_tip_canary(canary_adj, risky_adj, defensive_adj, a=a, b=b,
                                  candidate_adj_by_ticker=candidate_adj_by_ticker,
                                  candidate_mom_by_ticker=candidate_mom_by_ticker,
                                  trend_adj=trend_adj, mode=mode)

    tax_rate_by_position = {"RISK": capital_gains_tax_rate_for_ticker(risky_ticker)}
    vorabpauschale_faktor_by_position = {"RISK": vorabpauschale_faktor_for_ticker(risky_ticker)}
    if defensive_ticker is not None:     # ohne defensives Asset gibt es keine DEFENSIVE-Position
        tax_rate_by_position["DEFENSIVE"] = capital_gains_tax_rate_for_ticker(defensive_ticker)
        vorabpauschale_faktor_by_position["DEFENSIVE"] = vorabpauschale_faktor_for_ticker(
            defensive_ticker)
    for candidate_ticker in candidate_adj_by_ticker:
        tax_rate_by_position[candidate_ticker] = capital_gains_tax_rate_for_ticker(candidate_ticker)
        vorabpauschale_faktor_by_position[candidate_ticker] = vorabpauschale_faktor_for_ticker(
            candidate_ticker)

    equity_after_tax_full, capgains_tax_full, vorab_tax_full = apply_taxes(
        result["daily_position"], result["returns_by_position"],
        tax_rate_by_position=tax_rate_by_position,
        vorabpauschale_faktor_by_position=vorabpauschale_faktor_by_position,
    )

    start = result["equity"].index[0]
    if common_start is not None:
        start = max(start, common_start)

    equity_after_tax = equity_after_tax_full.loc[equity_after_tax_full.index >= start]
    equity_after_tax = equity_after_tax / equity_after_tax.iloc[0]

    capgains_tax = capgains_tax_full.loc[capgains_tax_full.index >= start]
    vorab_tax = vorab_tax_full.loc[vorab_tax_full.index >= start]

    perf = performance_stats(equity_after_tax)
    sig = signal_stats(result["daily_position"], result["confirmed_position"],
                        risk_labels=("RISK", *candidate_adj_by_ticker), start_date=start)

    # Wechsel zwischen Risk-Asset (synthetisch/Kandidat) und Defensiv-Asset/Cash,
    # gezählt auf der tatsächlich gehaltenen Position ab `start`.
    held = result["daily_position"].loc[result["daily_position"].index >= start]
    in_risk = held.isin(("RISK", *candidate_adj_by_ticker))
    n_switches = max(int((in_risk != in_risk.shift(1)).sum() - 1), 0)
    span_years = (held.index[-1] - held.index[0]).days / 365.25
    switches_per_year = n_switches / span_years if span_years > 0 else np.nan

    return {
        "a": a,
        "b": b,
        "mode": mode,
        "switches": n_switches,
        "switches_per_year": switches_per_year,
        "equity_after_tax": equity_after_tax,
        "perf": perf,
        "sig": sig,
        "kapitalertragsteuer_kumuliert": capgains_tax.sum(),
        "vorabpauschale_steuer_kumuliert": vorab_tax.sum(),
        "confirmed_position": result["confirmed_position"],
        "tip_macro": result["tip_macro"].loc[result["tip_macro"].index >= start],
        "trend_macro": result["trend_macro"].loc[result["trend_macro"].index >= start],
        "daily_position": result["daily_position"].loc[result["daily_position"].index >= start],
        "risk_choices": result["risk_choices"],
        "canary_mom": result["canary_mom"],
        "defensive_first_date": result["defensive_first_date"],
        "common_start_used": start,
    }


def format_extra_metrics(r: dict, capture: dict[str, float] | None = None) -> str:
    """Baut die Kennzahlen der TIP-Canary-Strategie, die über den
    reinen Rendite-/Risiko-Vergleich hinausgehen (Zeitanteile je
    Regime, Anzahl Regime-Wechsel, kumulierte Steuern) als eigenen
    Textblock - diese Werte haben für eine reine Buy&Hold-Position
    keine sinnvolle Entsprechung (die hält immer zu 100% das
    Risk-Asset, ohne Regime-Wechsel) und werden deshalb separat von
    der Gesamtzeit-Vergleichstabelle ausgewiesen. "Zeit defensiv" ist der
    Zeitanteil im echten Defensiv-Asset, "Zeit Cash" der Anteil vor
    dessen Erstnotierung (siehe signal_stats())."""
    sig = r["sig"]

    def _pct(v: float) -> str:
        return f"{v:.1%}" if pd.notna(v) else "n/a"

    # Feste Label-Spaltenbreite fuer die ganze Tabelle, damit die
    # Prozent-/Zahlenwerte immer in derselben Spalte stehen.
    LABEL_WIDTH = 40

    def _row(label: str, value: str, indent: int = 2) -> str:
        prefix = " " * indent + label
        return f"{prefix:<{LABEL_WIDTH}}{value:>8}"

    lines = ["\nZusätzliche Kennzahlen:",
             _row("Zeit im Risk-Asset:", _pct(sig['Zeit im Risk-Asset']))]
    for label, share in sig["asset_shares"].items():
        if pd.notna(share) and share > 0:
            lines.append(_row(f"davon {'synthetisch' if label == 'RISK' else label}:",
                               _pct(share), indent=4))
    lines.append(_row("Zeit im Defensiv-Asset:", _pct(sig['Zeit im defensiven Asset'])))
    lines += [_row("Zeit in Cash:", _pct(sig['Zeit in Cash'])),
              _row("Wechsel (gesamt):", str(r['switches'])),
              _row("Wechsel pro Jahr (Ø):", f"{r['switches_per_year']:.1f}"),
              _row("Kapitalertragsteuer (kum.):", f"{r['kapitalertragsteuer_kumuliert']:.4f}"),
              _row("Vorabpauschale-Steuer (kum.):", f"{r['vorabpauschale_steuer_kumuliert']:.4f}")]
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
                           asset_by_state: dict[str, tuple[str, str, pd.Series | None]],
                           daily_position: pd.Series) -> list[dict]:
    """Baut die rohe, chronologisch sortierte Phasen-Liste (Start, Ende,
    Dauer, gehaltenes Asset, dessen Rendite sowie die Rendite des
    Risk-Assets in genau dieser Phase) auf, über ALLE in `asset_by_state`
    genannten Def-Zustände hinweg (siehe
    format_defensive_phase_detail_table() für Details) - als
    gemeinsame Grundlage sowohl für die Detail-Tabelle als auch für
    format_defensive_score_table(), damit beide garantiert auf exakt
    denselben Phasen rechnen."""
    idx = risky_adj.index
    rows = []
    for state, (state_ticker, state_name, adj) in asset_by_state.items():
        episodes = identify_position_episodes(daily_position, state)
        adj_on_calendar = adj.reindex(idx).ffill() if adj is not None else None
        for start, end in episodes:
            pos = idx.get_loc(start)
            anchor = idx[pos - 1] if pos > 0 else start
            n_days = idx.get_loc(end) - idx.get_loc(anchor)
            asset_return = (0.0 if adj_on_calendar is None
                             else adj_on_calendar.loc[end] / adj_on_calendar.loc[anchor] - 1.0)
            risky_return = risky_adj.loc[end] / risky_adj.loc[anchor] - 1.0
            delta = asset_return - risky_return
            winner = "Def" if delta > 0 else ("Risk" if delta < 0 else ("=" if pd.notna(delta) else "n/a"))
            rows.append({
                "start": start, "end": end, "n_days": n_days,
                "asset_ticker": state_ticker, "asset_name": state_name,
                "asset_return": asset_return, "risky_return": risky_return,
                "delta": delta, "winner": winner,
            })
    rows.sort(key=lambda r: r["start"])
    return rows


def format_defensive_phase_detail_table(risky_adj: pd.Series,
                                         asset_by_state: dict[str, tuple[str, str, pd.Series | None]],
                                         daily_position: pd.Series) -> str:
    """Listet JEDE einzelne Def-Phase (Risk-off) einzeln auf (Start,
    Ende, Dauer, welches konkrete Asset tatsächlich gehalten wurde,
    dessen Rendite (Def-Rend.) sowie die Rendite des Risk-Assets in
    genau dieser Phase (Risk-Rend.), gefolgt vom DELTA daraus, siehe
    identify_position_episodes()) - analog zu
    format_yearly_comparison_table(): ein positives Delta heißt, Def
    hat sich in dieser Phase gelohnt (Defensiv-Position schlug das
    Risk-Asset), ein negatives, dass man mit Risk besser gefahren wäre
    - zeigt auf einen Blick, in welchen Phasen die Strategie
    tatsächlich Mehrwert gebracht hat, auch bei verzögerter Reaktion
    (die Auswertung je Phase, nicht Einzeltag, erfasst eine Reaktion
    irgendwann innerhalb derselben Phase mit).

    `asset_by_state` ordnet jedem in `daily_position` vorkommenden
    Def-Zustand (hier: "DEFENSIVE" und "CASH") ein (Anzeige-Ticker,
    Anzeigename, Kursreihe) zu - Kursreihe=None für CASH (Rendite dort
    per Definition 0%). Weil beide Zustände zu unterschiedlichen Zeiten
    gelten (CASH nur vor Börsengang des defensiven Assets), wird für
    jeden Zustand separat nach Phasen gesucht und anschließend
    chronologisch zu einer einzigen Tabelle zusammengeführt.

    Die "Gesamt"-Zeile ist wie bei format_yearly_comparison_table() NICHT
    die (zinseszins-verzerrende) Summe der einzelnen Phasen-Deltas,
    sondern verkettet (compoundet) Def-Rend. und Risk-Rend. über ALLE
    Phasen hinweg zu je einer Gesamtrendite ("als hätte man
    ununterbrochen nur in Def- bzw. nur in Risk-Phasen investiert") -
    Δ Rendite in dieser Zeile ist die Differenz dieser beiden
    Gesamtrenditen. Die Gewinner-Spalte zählt davon unabhängig weiterhin,
    in wie vielen EINZELNEN Phasen Def bzw. Risk vorne lag. Die
    Durchschnittszeile bildet den Mittelwert je Phase für Tage,
    Def-Rend., Risk-Rend. und Δ Rendite."""
    rows = _defensive_phase_rows(risky_adj, asset_by_state, daily_position)

    def _pct(v: float) -> str:
        return f"{v:+.1%}" if pd.notna(v) else "n/a"

    asset_col = max(11, max((len(r["asset_ticker"]) for r in rows), default=11) + 3)
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
                      f"{_pct(row['asset_return']):>14}{_pct(row['risky_return']):>14}"
                      f"{_pct(row['delta']):>13}"
                      f"{row['winner']:>18}")

    # Summenzeile: Def-Rend./Risk-Rend. werden über alle (gültigen)
    # Phasen hinweg VERKETTET (compoundet) zu je einer Gesamtrendite -
    # so, als hätte man ununterbrochen nur in Def- bzw. nur in
    # Risk-Phasen investiert (analog zu den GESAMTZEIT-Kennzahlen in
    # format_yearly_comparison_table(), statt einer simplen,
    # zinseszins-verzerrenden Summe der Delta-Werte). Δ Rendite in
    # dieser Zeile ist die Differenz dieser beiden Gesamtrenditen. Die
    # Tage-Summe sowie die Zählung, in wie vielen EINZELNEN Phasen Def
    # (Delta > 0) bzw. Risk (Delta < 0) vorn lag, bleiben wie gehabt.
    lines.append("-" * len(header))
    # NaN-Deltas (siehe oben, "n/a"-Zeilen - erste Phase eines Assets,
    # deren Anker-Tag dessen eigene Kurshistorie unterschreitet) werden
    # von der Verkettung/Zählung ausgeschlossen, statt das Gesamtergebnis
    # auf NaN zu setzen.
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
                 f"{_pct(total_def):>14}{_pct(total_risk):>14}{_pct(total_delta):>13}"
                 f"{f'{n_def} Def / {n_risk} Risk':>18}")

    # Durchschnitt je Phase für Tage, Def-Rend., Risk-Rend. und
    # Δ Rendite - jeweils NUR über die gültigen Phasen (siehe oben),
    # damit alle vier Mittelwerte auf demselben Nenner beruhen. Die
    # Def/Risk-Zählung hat dort kein sinnvolles Analogon. Auf einen
    # Median wird bewusst verzichtet: die Outperformance stammt
    # typischerweise aus wenigen dominanten Phasen, wodurch der Median
    # eher irreführend als aussagekräftig wäre.
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
                 f"{_pct(avg_def):>14}{_pct(avg_risk):>14}{_pct(avg_delta):>13}")
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


def _regime_phase_returns(risky_adj: pd.Series, defensive_adj: pd.Series,
                           daily_position: pd.Series,
                           states: tuple[str, ...]) -> tuple[list[tuple[float, float]], int]:
    """Sammelt für die angegebenen Regime-Zustände (Teilmenge von
    "RISK"/"DEFENSIVE") jede einzelne Episode (siehe
    identify_position_episodes()) - UNABHÄNGIG davon, welches Asset in
    dieser Episode tatsächlich gehalten wurde - und berechnet je Episode
    ein (Def-Rendite, Risk-Rendite)-Paar auf Basis des EXPLIZITEN
    defensiven Assets (defensive_adj, z.B. FTGB.SG, per ffill auf den
    Handelskalender des Risk-Assets gebracht - NICHT CASH). Nur
    Episoden, die (inkl. ihres Anker-Tages) bereits ab dem Börsengang
    des defensiven Assets liegen, fließen ein - CASH-Phasen davor haben
    keine eigene Kursreihe und werden dadurch automatisch
    ausgeschlossen. Gibt (Liste der Renditepaare, Summe der Handelstage
    dieser Episoden) zurück - Grundlage für
    format_defensive_score_table(), dort wird aus der Summe die
    durchschnittliche Phasendauer gebildet (Summe / Anzahl Episoden)."""
    idx = risky_adj.index
    # Vor der Erstnotierung des defensiven Assets gilt Cash (Kurs konstant
    # = Rendite 0 %, wie in der Defensiv-Phasen-Tabelle): bfill hält den
    # ersten Kurs rückwirkend konstant. Eine Phase, die über die
    # Erstnotierung hinweg läuft, bekommt so Cash bis dahin und das Asset danach.
    def_on_calendar = defensive_adj.reindex(idx).ffill().bfill()
    pairs: list[tuple[float, float]] = []
    total_days = 0
    for state in states:
        for start, end in identify_position_episodes(daily_position, state):
            pos = idx.get_loc(start)
            anchor = idx[pos - 1] if pos > 0 else start
            def_ret = def_on_calendar.loc[end] / def_on_calendar.loc[anchor] - 1.0
            risk_ret = risky_adj.loc[end] / risky_adj.loc[anchor] - 1.0
            if pd.notna(def_ret) and pd.notna(risk_ret):
                pairs.append((def_ret, risk_ret))
                total_days += idx.get_loc(end) - idx.get_loc(anchor)
    return pairs, total_days


def format_defensive_score_table(risky_adj: pd.Series, defensive_adj: pd.Series | None,
                                  daily_position: pd.Series) -> str:
    """Vergleicht - getrennt für Defensiv-Phasen, Risk-Phasen und den
    gesamten Zeitraum (siehe _regime_phase_returns()) - den
    DURCHSCHNITT der Phasen-Rendite des Risk-Assets mit der des
    EXPLIZITEN defensiven Assets (defensive_ticker, NICHT CASH) -
    UNABHÄNGIG davon, welches Asset in der jeweiligen Episode
    tatsächlich gehalten wurde. Die Risk-/Def-Spalten sind jeweils der
    MITTELWERT über die Episoden der jeweiligen Zeile (Summe der
    einzelnen Phasenrenditen geteilt durch die Anzahl der Phasen
    dieser Zeile): bei "Gesamtzeitraum" zählen Defensiv- UND
    Risk-Phasen gemeinsam (Nenner = Anzahl ALLER Phasen), bei
    "Risk-Phasen"/"Defensiv-Phasen" jeweils nur die Phasen der
    entsprechenden Zeile. Die Spalte "Ø Tage" zeigt analog die
    DURCHSCHNITTLICHE Dauer einer Phase dieser Zeile (Summe der
    Handelstage aus _regime_phase_returns() geteilt durch die Anzahl
    der Phasen), NICHT deren Summe. Berücksichtigt werden dabei
    ohnehin nur Episoden ab der Erstnotierung des defensiven Assets
    (siehe _regime_phase_returns(), Anker-Tag-Filterung) - das wird
    zusätzlich in der Tabellenüberschrift vermerkt. Ohne defensives Asset
    (`defensive_adj` None) entfällt die Tabelle (Def = Cash, Rendite 0 %)."""
    if defensive_adj is None or len(defensive_adj) == 0:
        return ("\nDurchschnittliche Phasen-Rendite Def vs. Risk: entfällt "
                "(kein Defensiv-Asset konfiguriert, Def = Cash).")
    def_pairs, def_days = _regime_phase_returns(risky_adj, defensive_adj, daily_position,
                                                 ("DEFENSIVE",))
    risk_pairs, risk_days = _regime_phase_returns(risky_adj, defensive_adj, daily_position,
                                                   ("RISK",))
    total_pairs, total_days = _regime_phase_returns(risky_adj, defensive_adj, daily_position,
                                                      ("DEFENSIVE", "RISK"))

    def _means(pairs: list[tuple[float, float]]) -> tuple[float, float]:
        if not pairs:
            return float("nan"), float("nan")
        mean_def = sum(def_ret for def_ret, _ in pairs) / len(pairs)
        mean_risk = sum(risk_ret for _, risk_ret in pairs) / len(pairs)
        return mean_def, mean_risk

    def _pct(v: float) -> str:
        return f"{v:+.1%}" if pd.notna(v) else "n/a"

    def _avg_days_str(days: int, n_pairs: int) -> str:
        return f"{days / n_pairs:.1f}" if n_pairs else "n/a"

    def_first_date = defensive_adj.index.min()
    lines = [f"\nDurchschnittliche Phasen-Rendite (gesamter Backtest-Zeitraum; Def = "
             f"Cash bis zur Notierung des Defensiv-Assets am {def_first_date.date()}):"]
    header = f"  {'Basis':<18}{'Anzahl':>8}{'Ø Tage':>8}{'Risk':>12}{'Def':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for name, pairs, days in (
        ("Gesamtzeitraum", total_pairs, total_days),
        ("Risk-Phasen", risk_pairs, risk_days),
        ("Defensiv-Phasen", def_pairs, def_days),
    ):
        mean_def, mean_risk = _means(pairs)
        lines.append(f"  {name:<18}{len(pairs):>8}{_avg_days_str(days, len(pairs)):>8}"
                      f"{_pct(mean_risk):>12}{_pct(mean_def):>12}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Risk-Phasen und Buy & Hold-Kette
# ----------------------------------------------------------------------
def to_regime_view(daily_position: pd.Series, risk_labels: tuple[str, ...]) -> pd.Series:
    """Fasst alle Risk-Labels (synthetisches Asset "RISK" und die
    Kandidaten-Ticker) zu "RISK" zusammen. Grundlage für alle Auswertungen,
    die nur das Regime (Risk vs. Defensiv/Cash) betrachten: Phasen-
    Erkennung, Ø Phasen-Rendite, Plot-Hintergrund."""
    return daily_position.where(~daily_position.isin(risk_labels), "RISK")


def chain_price_series(synthetic_adj: pd.Series, candidate_adj: pd.Series) -> pd.Series:
    """Verkettete Kurs-Reihe für den Buy & Hold-Vergleich: Tagesrenditen
    des synthetischen Assets bis einschließlich zum ersten Kurs des
    Kandidaten, danach die Tagesrenditen des Kandidaten (auf den Kalender
    des synthetischen Assets gelegt, vorwärtsgefüllt). Hat der Kandidat
    keinen Kurs auf diesem Kalender, ist das Ergebnis die synthetische
    Reihe."""
    idx = synthetic_adj.index
    candidate = candidate_adj.reindex(idx).ffill()
    first = candidate.first_valid_index()
    if first is None:
        return synthetic_adj
    returns = synthetic_adj.pct_change().where(idx <= first, candidate.pct_change())
    chained = (1.0 + returns.fillna(0.0)).cumprod() * synthetic_adj.iloc[0]
    return chained


def _risk_phase_rows(risky_adj: pd.Series,
                      candidate_adj_by_ticker: dict[str, pd.Series],
                      daily_position: pd.Series,
                      risk_choices: list[dict]) -> list[dict]:
    """Baut die rohe, chronologisch sortierte Liste der Risk-Phasen (Start,
    Ende, Dauer, gehaltenes Asset, dessen Rendite, Rendite des
    synthetischen Referenz-Assets `risky_adj` in derselben Phase sowie
    Qualität der Auswahl: nachträglich bestes zur Wahl stehendes
    Asset und Rang des gewählten) auf. Als zur Wahl stehend gelten genau
    die Kandidaten, die bei der Auswahl (risk_choices) ein Momentum hatten.
    Anker-Tag und Dauer wie in _defensive_phase_rows()."""
    idx = risky_adj.index
    risk_labels = ("RISK", *candidate_adj_by_ticker)
    regime = to_regime_view(daily_position, risk_labels)
    adj_on_calendar = {"RISK": risky_adj}
    for ticker, adj in candidate_adj_by_ticker.items():
        adj_on_calendar[ticker] = adj.reindex(idx).ffill()
    choice_by_start = {c["start"]: c for c in risk_choices}

    rows = []
    for start, end in identify_position_episodes(regime, "RISK"):
        held = daily_position.loc[start]
        pos = idx.get_loc(start)
        anchor = idx[pos - 1] if pos > 0 else start
        n_days = idx.get_loc(end) - idx.get_loc(anchor)

        def phase_return(label: str) -> float:
            series = adj_on_calendar[label]
            return series.loc[end] / series.loc[anchor] - 1.0

        held_return = phase_return(held)
        ref_return = phase_return("RISK")
        delta = held_return - ref_return

        eligible = list(choice_by_start.get(start, {}).get("scores", {}))
        eligible_returns = {t: phase_return(t) for t in eligible}
        best_ticker, rank = "-", None
        if held != "RISK" and held in eligible_returns:
            best_ticker = max(eligible_returns, key=eligible_returns.get)
            rank = 1 + sum(1 for r in eligible_returns.values() if r > held_return)
        rows.append({
            "start": start, "end": end, "n_days": n_days, "held": held,
            "held_return": held_return, "ref_return": ref_return, "delta": delta,
            "best": best_ticker, "rank": rank, "n_eligible": len(eligible),
        })
    return rows


def format_risk_phase_detail_table(risky_adj: pd.Series,
                                    candidate_adj_by_ticker: dict[str, pd.Series],
                                    daily_position: pd.Series,
                                    risk_choices: list[dict],
                                    synthetic_name: str = "synth.") -> str:
    """Listet JEDE einzelne Risk-Phase auf (Start, Ende, Dauer, tatsächlich
    gehaltenes Asset und dessen Rendite) - analog zu
    format_defensive_phase_detail_table(). Das synthetische Asset erscheint
    unter `synthetic_name` (Varianten-Name aus RISK_TICKERS, z.B. SP500_2x).
    Die "Gesamt"-Zeile verkettet (compoundet) die Phasenrenditen - dieselbe
    Rechenlogik wie in der Defensiv-Tabelle; die Durchschnittszeile bildet
    den Mittelwert je Phase."""
    rows = _risk_phase_rows(risky_adj, candidate_adj_by_ticker, daily_position, risk_choices)

    def _pct(v: float) -> str:
        return f"{v:+.1%}" if pd.notna(v) else "n/a"

    def _name(label: str) -> str:
        return synthetic_name if label == "RISK" else label

    asset_col = max(10, max((len(_name(r["held"])) for r in rows), default=10) + 3)
    lines = ["\nRisk-Phasen im Detail:"]
    header = f"  {'Start':<12}{'Ende':<12}{'Tage':>6}{'Asset':>{asset_col}}{'Rendite':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in rows:
        lines.append(f"  {r['start'].date().isoformat():<12}{r['end'].date().isoformat():<12}"
                      f"{r['n_days']:>6}{_name(r['held']):>{asset_col}}"
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
# Main
# ----------------------------------------------------------------------
def main() -> None:
    # Kein festes Startdatum: der Backtest beginnt am frühestmöglichen Tag
    # mit vollständigem Signal (siehe run_single_backtest()/common_start).
    user_start_date = None

    now_berlin = datetime.now(BERLIN_TZ)
    query_end_date = compute_query_end_date(now_berlin)
    print(f"Aktuelle Zeit (Berlin): {now_berlin.strftime('%Y-%m-%d %H:%M:%S')} "
          f"- Kurse werden bis {query_end_date.date()} abgefragt.\n")

    # Eingabeprüfung der Kandidaten: keine Namenskollision mit den
    # Positions-Labels, und derselbe Ticker in mehreren Varianten muss
    # dieselbe Teilfreistellung/Währung haben.
    seen_candidates: dict[str, dict] = {}
    for variant, info in RISK_TICKERS.items():
        for ticker, cinfo in info["candidates"].items():
            if ticker in ("RISK", "DEFENSIVE", "CASH"):
                raise ValueError(f"{variant}: Kandidat \"{ticker}\" kollidiert mit einem Positions-Label.")
            known = seen_candidates.setdefault(ticker, cinfo)
            if (known["teilfreistellung"], known["currency"]) != (
                    cinfo["teilfreistellung"], cinfo["currency"]):
                raise ValueError(f"Kandidat {ticker}: abweichende Teilfreistellung/Währung in "
                                 f"mehreren Varianten - bitte vereinheitlichen.")
        for ticker, cinfo in info["candidates"].items():
            if cinfo["teilfreistellung"] != info["teilfreistellung"]:
                print(f"[warn]     {variant}: Kandidat {ticker} hat eine andere Teilfreistellung "
                      f"als das synthetische Asset - die Buy & Hold-Kette nutzt die des "
                      f"synthetischen Assets.")

    for variant, info in RISK_TICKERS.items():
        if info.get("bh_reference") not in info["candidates"]:
            raise ValueError(f"{variant}: \"bh_reference\" muss einer der Kandidaten sein "
                             f"(aktuell: {info.get('bh_reference')!r}).")

    # Nur der ERSTE Eintrag in RISK_TICKERS bekommt die ausführlichen
    # Zusatz-Tabellen (siehe Modul-Docstring "Getestete Varianten").
    primary_ticker = next(iter(RISK_TICKERS))

    canary_adj = get_adj_close(CANARY_TICKER, query_end_date)
    trend_adj = get_adj_close(TREND_TICKER, query_end_date)

    # EUR/USD-Wechselkurs EINMALIG laden (siehe "Währungsumrechnung" im
    # Modul-Docstring).
    eur_per_usd = load_eur_per_usd(query_end_date)

    # Defensiv-Asset laden, ggf. synthetisch hebeln und ERST DANACH nach
    # EUR umrechnen.
    # Bei leerem DEFENSIVE gibt es kein defensives Asset (defensive_adj None):
    # Risk-off-Tage werden dann komplett als CASH gehalten.
    if DEFENSIVE_TICKER is not None:
        defensive_adj_raw = get_adj_close(DEFENSIVE_TICKER, query_end_date)
        defensive_leverage = DEFENSIVE[DEFENSIVE_TICKER]["leverage"]
        defensive_lev_adj = (defensive_adj_raw if defensive_leverage == 1.0
                             else synthetic_leveraged_series(defensive_adj_raw, defensive_leverage))
        defensive_adj = convert_to_eur(defensive_lev_adj, DEFENSIVE[DEFENSIVE_TICKER]["currency"],
                                        eur_per_usd)
    else:
        defensive_adj = None

    # Synthetische Risk-Assets und Kandidaten laden. Rohkurse je
    # Yahoo-Ticker nur einmal abrufen. Das synthetische Asset wird ggf.
    # gehebelt und DANACH nach EUR umgerechnet; Kandidaten werden nur
    # umgerechnet (Hebel steckt im Produkt). Das Momentum der Kandidaten
    # wird auf der (ggf. umgerechneten) Kursreihe in EUR berechnet, auf
    # dem EIGENEN Handelskalender des Kandidaten.
    raw_adj_by_yahoo_ticker: dict[str, pd.Series] = {}

    def _raw(yahoo_ticker: str) -> pd.Series:
        if yahoo_ticker not in raw_adj_by_yahoo_ticker:
            raw_adj_by_yahoo_ticker[yahoo_ticker] = get_adj_close(yahoo_ticker, query_end_date)
        return raw_adj_by_yahoo_ticker[yahoo_ticker]

    risky_adj_by_ticker: dict[str, pd.Series] = {}
    candidate_adj_by_variant: dict[str, dict[str, pd.Series]] = {}
    candidate_mom_by_variant: dict[str, dict[str, pd.Series]] = {}
    for variant, info in RISK_TICKERS.items():
        raw_adj = _raw(info["ticker"])
        leverage = info["leverage"]
        lev_adj = raw_adj if leverage == 1.0 else synthetic_leveraged_series(raw_adj, leverage)
        risky_adj_by_ticker[variant] = convert_to_eur(lev_adj, info["currency"], eur_per_usd)

        candidate_adj_by_variant[variant] = {}
        candidate_mom_by_variant[variant] = {}
        for ticker, cinfo in info["candidates"].items():
            candidate_adj = convert_to_eur(_raw(ticker), cinfo["currency"], eur_per_usd)
            candidate_adj_by_variant[variant][ticker] = candidate_adj
            candidate_mom_by_variant[variant][ticker] = momentum_13612u_trading_days(
                candidate_adj, LOOKBACK_DAYS_CANARY)

    # --- Backtest (a=CONFIRMATION_A, b=CONFIRMATION_B, fix) je Variante ---
    results_by_label: dict[str, dict[str, dict]] = {}
    for variant, info in RISK_TICKERS.items():
        results_by_label[variant] = {
            mode: run_single_backtest(
                canary_adj, risky_adj_by_ticker[variant], variant, defensive_adj, DEFENSIVE_TICKER,
                a=CONFIRMATION_A, b=CONFIRMATION_B,
                candidate_adj_by_ticker=candidate_adj_by_variant[variant],
                candidate_mom_by_ticker=candidate_mom_by_variant[variant],
                common_start=user_start_date,
                trend_adj=trend_adj, mode=mode,
            )
            for mode in STRATEGY_NAMES
        }

    # --- Buy & Hold-Referenzen (nach Steuern), je Variante, ab demselben
    #     Startdatum wie der TIP-Canary-Lauf dieser Variante. Referenz =
    #     verkettete Reihe (synthetisch -> FIX gewählte "bh_reference" der
    #     Variante, siehe Modul-Docstring "Reale Risk-Assets und Auswahl"). ---
    def _leverage_suffix(info: dict) -> str:
        leverage = info["leverage"]
        if leverage == 1.0:
            return ""
        if leverage < 0:
            return f" [synth. {abs(leverage):g}x Short]"
        return f" [synth. {leverage:g}x]"

    strategy_stats_by_label = {}
    stats_labels_by_variant: dict[str, list[str]] = {}
    bh_label_by_variant: dict[str, str] = {}
    curves = {}
    canary_label_by_ticker: dict[str, str] = {}
    bh_info_lines: list[str] = []
    capture_by_variant: dict[str, dict[str, float]] = {}
    for variant, info in RISK_TICKERS.items():
        suffix = _leverage_suffix(info)
        risky_adj = risky_adj_by_ticker[variant]
        # Alle Strategien teilen denselben Start (TIP-Signalstart).
        common_start = results_by_label[variant]["hybrid"]["common_start_used"]

        bh_ref = info["bh_reference"]
        chain = chain_price_series(risky_adj, candidate_adj_by_variant[variant][bh_ref])
        best_equity = buy_and_hold_after_tax(chain, variant, start_date=common_start)
        first_date = candidate_adj_by_variant[variant][bh_ref].index.min().date()
        bh_info_lines.append(f"  {variant}: synthetisch bis {first_date}, danach {bh_ref} (fix).")

        lev_prefix = f"{info['leverage']:g}x "
        bh_label = f"{lev_prefix}B&H"
        bh_label_by_variant[variant] = bh_label
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
            capture = capture_ratios(result["equity_after_tax"], best_equity)
            if mode == "hybrid":
                capture_by_variant[variant] = capture
                canary_label_by_ticker[variant] = label
            strategy_stats_by_label[label] = {
                **result["perf"], "Up-Cap": capture["up"], "Down-Cap": capture["down"],
                "Wechsel": result["switches"], "Ø/Jahr": result["switches_per_year"]}
            curves[label] = result["equity_after_tax"]
            stats_labels_by_variant.setdefault(variant, []).append(label)
        strategy_stats_by_label[bh_label] = {
            **performance_stats(best_equity), "Up-Cap": 1.0, "Down-Cap": 1.0,
            "Wechsel": 0, "Ø/Jahr": 0.0}
        curves[bh_label] = best_equity
        stats_labels_by_variant[variant].append(bh_label)

    # --- Textauswertung: wird gleichzeitig ausgegeben und gesammelt,
    #     um sie am Ende in EINE Textdatei zu schreiben ---
    report_lines: list[str] = [
        "=" * 70,
        "Backtest-Auswertung: TIP+SMA (TIP-Canary + Nasdaq-100-SMA) mit realen Risk-Assets",
        f"Erstellt: {datetime.now(BERLIN_TZ).strftime('%Y-%m-%d %H:%M:%S')} (Berlin)",
        "=" * 70,
    ]

    def emit(text: str) -> None:
        print(text)
        report_lines.append(text)

    def _variant_label(variant: str, info: dict) -> str:
        primary_marker = " [ausführliche Auswertung]" if variant == primary_ticker else ""
        candidates = ", ".join(info["candidates"]) or "keine"
        return (f"({info['ticker']}) {info['name']}{_leverage_suffix(info)}{primary_marker}"
                f"\n    Kandidaten: {candidates}")

    risk_assets_str = "\n  ".join(_variant_label(v, info) for v, info in RISK_TICKERS.items())
    if DEFENSIVE_TICKER is not None:
        defensive_info = DEFENSIVE[DEFENSIVE_TICKER]
        defensive_text = (f"Defensiv-Asset: ({DEFENSIVE_TICKER}) {defensive_info['name']}"
                          f"{_leverage_suffix(defensive_info)}"
                          f"\nVor Erstnotierung des Defensiv-Assets: Cash")
    else:
        defensive_info = None
        defensive_text = "Defensiv-Asset: keines (DEFENSIVE leer) - Risk-off = durchgehend Cash"
    emit(f"\nRisk-Asset-Varianten (synthetischer Fallback, reale Kandidaten):\n  {risk_assets_str}"
         f"\n{defensive_text}"
         f"\nTIP+SMA: Risk, wenn TIP (a={CONFIRMATION_A}/b={CONFIRMATION_B}) ODER {TREND_TICKER} über "
         f"seiner SMA{TREND_SMA_DAYS} (Filter a={TREND_CONFIRMATION_A}/b={TREND_CONFIRMATION_B}) "
         f"Risk meldet; Defensiv nur, wenn beide schlecht stehen."
         f"\nBuy & Hold-Referenz:\n" + "\n".join(bh_info_lines))

    # --- Gesamtübersicht: je Variante (1x/2x) eine eigene Tabelle, jeweils
    #     absteigend nach der erzielten Rendite sortiert ---
    for variant, info in RISK_TICKERS.items():
        labels = stats_labels_by_variant[variant]
        variant_stats = {lbl: strategy_stats_by_label[lbl] for lbl in labels}
        ordered = sorted(variant_stats, key=lambda lbl: variant_stats[lbl]["Rendite"], reverse=True)
        emit(f"\n{info['leverage']:g}x: TIP+SMA, TIP und SMA (NDX-SMA200) vs. B&H "
             f"(jeweils nach Steuern, sortiert nach Rendite; "
             f"Wechsel = Risk-Asset <-> Defensiv/Cash):")
        emit(format_stats_table({lbl: variant_stats[lbl] for lbl in ordered}))

    # --- Zusätzliche Kennzahlen der Referenz-Strategie (Regime-
    #     Zeitanteile, Steuern), NUR für die primäre Variante ---
    emit(format_extra_metrics(results_by_label[primary_ticker]["hybrid"], capture_by_variant[primary_ticker]))

    asset_by_state = {}
    if defensive_info is not None:
        asset_by_state["DEFENSIVE"] = (DEFENSIVE_TICKER,
                                        f"{defensive_info['name']}{_leverage_suffix(defensive_info)}",
                                        defensive_adj)
    asset_by_state["CASH"] = ("CASH", "Cash (kein Asset gehalten)", None)
    primary_risky_adj = risky_adj_by_ticker[primary_ticker]
    primary_daily_position = results_by_label[primary_ticker]["hybrid"]["daily_position"]
    primary_risk_labels = ("RISK", *candidate_adj_by_variant[primary_ticker])
    primary_regime = to_regime_view(primary_daily_position, primary_risk_labels)
    # --- Ø Phasen-Rendite Def vs. Risk (kleine Tabelle) VOR den beiden
    #     großen Phasen-Tabellen, NUR für die primäre Variante ---
    emit(format_defensive_score_table(primary_risky_adj, defensive_adj, primary_regime))

    # --- Diagnose: Risk-Asset-Rendite nach TIP-Regime x Trendsignal, NUR
    #     für die Referenz-Strategie (primäre Variante) ---
    primary_result = results_by_label[primary_ticker]["hybrid"]
    emit(format_trend_quadrant_table(primary_risky_adj, primary_result["tip_macro"],
                                      primary_result["trend_macro"], f"SMA{TREND_SMA_DAYS}"))

    # --- Jahresweise Kennzahlen, NUR für die primäre Variante ---
    primary_canary_label = canary_label_by_ticker[primary_ticker]
    primary_bh_label = bh_label_by_variant[primary_ticker]
    emit(format_yearly_comparison_table(curves[primary_canary_label], curves[primary_bh_label],
                                         name=STRATEGY_NAMES["hybrid"]))

    # --- Jede Risk-off-Phase einzeln aufgelistet, NUR für die primäre
    #     Variante ---
    emit(format_defensive_phase_detail_table(primary_risky_adj, asset_by_state,
                                              primary_daily_position))

    # --- Jede Risk-Phase einzeln aufgelistet (gewähltes Asset, Rendite vs.
    #     synthetische Referenz, Qualität der Auswahl), NUR für die
    #     primäre Variante ---
    if SHOW_RISK_PHASES:
        emit(format_risk_phase_detail_table(
            primary_risky_adj, candidate_adj_by_variant[primary_ticker],
            primary_daily_position, results_by_label[primary_ticker]["hybrid"]["risk_choices"],
            synthetic_name=primary_ticker))

    results_path = OUTPUT_DIR / "backtest_ergebnis.txt"
    results_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # --- Plots (Regime-Phasen-Hintergrund: hellgrün = Risk-Phase,
    #     hellrot = Defensiv-Phase - aus der gehaltenen Position der
    #     PRIMÄREN Variante, siehe regime_phases()) ---
    risk_phases, defensive_phases = regime_phases(primary_regime)
    plot_strategy_comparison(
        curves,
        title="TIP+SMA / TIP / SMA vs. B&H - jeweils nach Steuern",
        filename="01_strategie_vergleich.png",
        risk_phases=risk_phases,
        defensive_phases=defensive_phases,
    )
    plot_drawdowns(curves, filename="02_drawdowns.png",
                    risk_phases=risk_phases, defensive_phases=defensive_phases)

    print(f"\nTextauswertung und Plots gespeichert in: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
    input("\nFertig - Enter zum Beenden drücken...")
