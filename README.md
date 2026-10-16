# SMA-TIP: steuerbewusste taktische Allokation

**SMA-TIP** ist ein regelbasiertes Signal, das börsentäglich sagt, ob ein (gehebelter) Aktien-ETF
oder eine defensive Position gehalten werden soll. Das Repository enthält

- das **Live-Signal** (`canary.py`), das nach US-Börsenschluss läuft und eine Push-Nachricht schickt,
- einen **Backtest** mit deutscher Steuerlogik (`backtest.py`),
- Werkzeuge für **Kalibrierung** und **Depotauswertung**.

> **Hinweis:** Dies ist ein Entscheidungshilfe-Projekt und keine Anlageberatung.
> Alle Ergebnisse beruhen auf historischen Daten und einem vereinfachten Modell.
> Qualitative Aussagen (Richtung, Rangfolge) sind belastbarer als exakte Zahlen.
> Hebelprodukte können hohe Verluste erzeugen (im Backtest bis über 50 % Drawdown).

---

## Die Strategie

### Idee in einem Satz

Man ist investiert (**RISK**), solange *mindestens eines* von zwei Signalen grünes Licht gibt,
und geht erst in die Defensive, wenn *beide* schlecht stehen.

### Die zwei Signale

| Signal | Regel | Rolle |
|---|---|---|
| **TIP-Canary** | 13612U-Momentum des ETFs `TIP` (inflationsgeschützte US-Anleihen) **> 0** → RISK | Makro-Frühwarnung über Zinsen und Inflation |
| **Trend (SMA)** | Schlusskurs des `^NDX` (Nasdaq 100) **strikt über** seinem 200-Tage-Durchschnitt → RISK | klassischer Trendfilter |

**13612U-Momentum** (Keller): Mittelwert der Kursänderungen über 1, 3, 6 und 12 Monate,
gerechnet in Handelstagen (21/63/126/252):

```
Score = 1/4 · [ (P0/P21 − 1) + (P0/P63 − 1) + (P0/P126 − 1) + (P0/P252 − 1) ]
```

### Kombination („Hybrid“, SMA-TIP)

```
Regime = RISK       wenn TIP-Signal = RISK  ODER  SMA-Signal = RISK
Regime = DEFENSIV   nur wenn beide Signale nicht RISK melden
```

Die ODER-Verknüpfung ist der Kern: Das Trendsignal wirkt praktisch nur dann, wenn das
TIP-Signal bereits defensiv ist. Dadurch wechselt der Hybrid mit etwa **2,4 Wechseln pro Jahr**
deutlich seltener als die Einzelsignale (je rund 6).

### Whipsaw-Filter (Bestätigung)

Ein neues Signal gilt erst nach mehreren aufeinanderfolgenden Handelstagen als bestätigt:

| Signal | Weg von RISK | Hin zu RISK |
|---|---|---|
| TIP | 1 Tag | 2 Tage |
| SMA | 1 Tag | 1 Tag |

Hysterese-Bänder um den SMA wurden getestet und bewusst **nicht** übernommen (siehe unten).

### Was gehalten wird

- **RISK:** ein Risk-ETF, z. B. ein 2x-S&P-500-ETF (`18MF.DE`) oder ein 1x-ETF (`SXR4.DE`).
  Bei mehreren Kandidaten gewinnt zu Beginn jeder Risk-Phase der mit dem höchsten Momentum.
- **DEFENSIV:** `FTGB.SG` (First Trust FactorFX) ab seiner Notierung (2017-12-27),
  davor Cash. Ist auch der Defensiv-Score nicht positiv, gilt Cash.

### Ausführung

Das Script läuft nach US-Börsenschluss (Sicherheitspuffer bis 16:05 New Yorker Zeit).
Das mit dem **heutigen** Schlusskurs bestätigte Regime ist die Grundlage für die Order am Abend.
Im Backtest wirkt das Signal von Tag *d−1* an Tag *d* (kein Look-Ahead).

---

## Ergebnisse des Backtests (nach Steuern, seit Dezember 2004)

| Variante | CAGR | Max. Drawdown |
|---|---|---|
| 2x SMA-TIP (Hybrid) | 25,5 % | −58,9 % |
| 2x Buy & Hold | 17,4 % | −82,3 % |
| 1x SMA-TIP (Hybrid) | 14,0 % | −35,2 % |
| 1x Buy & Hold | 11,1 % | −51,6 % |

Zeitraum bis Oktober 2026. In der Ausgabe von `backtest.py` heißt die Strategie noch „TIP+SMA“. Steuern (Kapitalertragsteuer, Teilfreistellung, Vorabpauschale)
sind im Ergebnis enthalten, Spread und Gebühren beim Handel nicht.

### Robustheit

Getestet wurden unter anderem Parameter-Overfitting (PBO, Walk-forward, Monte-Carlo),
Zeitverschiebung der Signale, Hysterese-Bänder, Tagesfilter, SMA-Längen und
mehrstimmige SMA-Abstimmung. **Ergebnis:** Kein Test stützt belastbar eine Abweichung vom
Standard. Gefundene Vorteile hängen an wenigen Episoden (z. B. Februar 2009, 2015/2022/2023).
Die Signale tragen im Hybrid nachweislich zum Ergebnis bei (Zeitverschiebungs-Test),
der Standard liegt aber in einem scharfen Parametergipfel, daher sollten die Erwartungen
für die Zukunft vorsichtiger sein als die Historie.

---

## Dateien

| Datei | Zweck |
|---|---|
| `canary.py` | **Live-Signal.** Lädt aktuelle Kurse, berechnet TIP-Momentum und NDX-SMA200, filtert und kombiniert sie zum Regime, wählt den besten Kandidaten und gibt Signal-Historie (10 Tage) und Handlungsempfehlung aus. Enthält die Ticker-Konfiguration (`RISK_TICKERS`, `DEFENSIVE_TICKERS`). |
| `ntfy_push.py` | Liest die Ausgabe von `canary.py` und schickt eine kurze Push-Nachricht über [ntfy](https://ntfy.sh). Ein Regimewechsel erhöht die Priorität. |
| `canary.yml` | GitHub-Actions-Workflow (gehört nach `.github/workflows/canary.yml`): installiert Pakete, führt `canary.py` aus, sendet den Push und meldet Fehler. Wird extern gestartet (siehe Einrichtung). |
| `yf_data.py` | Gemeinsame Kursdaten-Logik für alle Skripte: Abruf über yfinance mit Konsens-Abfrage, Kalender-Vollständigkeitsprüfung, Lückenfüllung aus zuvor bekannten Werten und Korrektur von Kurssprüngen. Kein Datei-Cache, damit rückwirkende Korrekturen von Yahoo ankommen. |
| `backtest.py` | **Backtest** der Strategie (Hybrid, nur TIP, nur SMA) gegen Buy & Hold, jeweils für 1x und 2x. Enthält die deutsche Steuerlogik, die Jahres- und Defensivphasen-Tabellen und Kennzahlen (CAGR, Drawdown, Sharpe, Capture). Konfiguration der Ticker, Kosten und Datenbereinigung steht im Kopf der Datei. |
| `backtest_diagnose.py` | Diagnose und **Kalibrierung** des synthetischen Risk-Assets gegen den realen Fonds: Jahresvergleich, Regression (Währungs- und Hebelfaktor), Kostenkalibrierung und Datenprüfung. |
| `backtest_smaensemble.py` | Test: SMA-Abstimmung über mehrere Längen statt einer einzelnen SMA200. |
| `stats.py` | **Depotauswertung:** liest CSV-Exporte der eigenen Käufe und Verkäufe (`stats/*.csv`), rekonstruiert den Bestand, berechnet Rendite und vergleicht mit Buy-&-Hold-Referenzen inklusive Vorabpauschale. Erzeugt `results.txt` und Plots. |
| `example.csv` | Beispiel für das CSV-Format von `stats.py` (`date;action;ticker;shares;sum`, Semikolon, Dezimalkomma). |
| `requirements.txt` | Festgelegte Paketversionen. `yfinance` ist bewusst nur nach unten begrenzt, weil Yahoo seine Schnittstelle regelmäßig ändert. |

---

## Modellannahmen des Backtests

- **Synthetisches Risk-Asset** für die Zeit vor den ETF-Notierungen: `SPY` (angepasster Schlusskurs,
  enthält Dividenden), in EUR umgerechnet und **danach** gehebelt (der echte 2x-Fonds hebelt in EUR),
  mit Kostenabzug p. a. aus der Kalibrierung gegen die realen Fonds ab 2011: **2x ≈ 2,0 %, 1x ≈ 0,5 %**.
- **Ab der Notierung** der ETFs (18MF.DE 2010-03-04, SXR4.DE ab 2011-01-01) laufen Strategie und
  Buy & Hold auf denselben echten Kursen, ohne zusätzliche Kosten.
  `SXR4.DE` ist vor 2011 wegen fehlerhafter Daten ausgeschlossen.
- **Steuern:** 26,375 % Kapitalertragsteuer auf realisierte Gewinne nach Teilfreistellung (30 % bei Aktienfonds),
  Vorabpauschale (Basiszins 2,5 %) zum Jahresende. Strategie und Buy & Hold nutzen dasselbe Steuermodell.
- **Jahresdeltas** in der Tabelle zeigen auch Steuerverschiebungen: Verkäufe realisieren Gewinne früher
  als Buy & Hold. Für die Gesamtbewertung zählt das Endergebnis.
- Nicht modelliert: Spread, Orderkosten, Zinsen auf Cash.

---

## Einrichtung des Live-Signals

1. Repository auf GitHub anlegen und die Dateien hochladen. `canary.yml` nach `.github/workflows/canary.yml`.
2. In ntfy ein geheimes Topic wählen, in GitHub unter *Settings → Secrets → Actions* als `NTFY_TOPIC` speichern
   und das Topic in der ntfy-App abonnieren.
3. Den Workflow von außen starten (z. B. [cron-job.org](https://cron-job.org), werktags um 22:06 Uhr deutscher Zeit)
   per `workflow_dispatch`-Aufruf der GitHub-API. Ein eigener Zeitplan in GitHub ist bewusst nicht gesetzt,
   weil GitHub Zeitpläne stark verzögern kann.
4. Manuell testen: *Actions → TIP-Canary → Run workflow*.

Lokal: `pip install -r requirements.txt`, dann `python canary.py`. Backtest: `python backtest.py`.

---

## Quellen

- **Gayed, M. A. & Bilello, C. (2016):** *Leverage for the Long Run – A Systematic Approach to Managing Risk
  and Magnifying Returns in Stocks.* Charles H. Dow Award 2016, CMT Association.
  Begründung für gehebelte Anlagen mit systematischem Risikomanagement über gleitende Durchschnitte
  (Basis des SMA-Ansatzes).
  [cmtassociation.org](https://cmtassociation.org/?p=75350)
- **Keller, W. J. & Keuning, J. W. (2023):** *Dual and Canary Momentum with Rising Yields/Inflation:
  Hybrid Asset Allocation (HAA).* SSRN. Quelle des Canary-Konzepts mit TIP und des 13612U-Momentums.
  [papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4346906)
- **philosophicaleconomics (2016):** *Growth and Trend: A Simple, Powerful Technique for Timing the Stock Market*
  (Growth-Trend Timing, GTT). Vorbild für den Hybrid-Ansatz: die Kombination eines Makro-Filters
  (dort Wirtschaftswachstum, hier das TIP-Canary) mit einem Trend-Filter.
  [philosophicaleconomics.com](https://www.philosophicaleconomics.com/?p=6785)

Die Strategie in diesem Repository ist eine eigene Weiterentwicklung und nicht identisch mit den genannten Arbeiten.
