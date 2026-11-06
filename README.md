# SMA-TIP: steuerbewusste taktische Allokation

**SMA-TIP** ist ein regelbasiertes Signal, das börsentäglich sagt, ob ein (gehebelter) Aktien-ETF
oder Tagesgeld gehalten werden soll. Das Repository enthält

- das **Live-Signal** (`canary.py`), das nach US-Börsenschluss läuft und eine Push-Nachricht schickt,
- einen **Backtest** mit deutscher Steuerlogik (`backtest.py`, rein synthetisch),
- ein Werkzeug für die **Depotauswertung**.

> **Hinweis:** Dies ist ein Entscheidungshilfe-Projekt und keine Anlageberatung.
> Alle Ergebnisse beruhen auf historischen Daten und einem vereinfachten Modell.
> Qualitative Aussagen (Richtung, Rangfolge) sind belastbarer als exakte Zahlen.
> Hebelprodukte können hohe Verluste erzeugen (im Backtest bis über 50 % Drawdown).

---

## Die Strategie

### Idee in einem Satz

Man ist investiert (**RISK**), solange *mindestens eines* von zwei Signalen grünes Licht gibt,
und geht erst ins Tagesgeld, wenn *beide* schlecht stehen.

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
Regime = DEFENSIV   nur wenn beide Signale nicht RISK melden (gehalten wird dann Tagesgeld)
```

Die ODER-Verknüpfung ist der Kern: Das Trendsignal wirkt praktisch nur dann, wenn das
TIP-Signal bereits defensiv ist. Dadurch wechselt der Hybrid mit etwa **2 Wechseln pro Jahr**
deutlich seltener als die Einzelsignale (TIP rund 6, SMA rund 5).

### Whipsaw-Filter (Bestätigung)

Ein neues Signal gilt erst nach mehreren aufeinanderfolgenden Handelstagen als bestätigt:

| Signal | Weg von RISK | Hin zu RISK |
|---|---|---|
| TIP | 1 Tag | 2 Tage |
| SMA | 1 Tag | 2 Tage |

Hysterese-Bänder um den SMA wurden getestet und bewusst **nicht** übernommen (siehe „Robustheit“).

### Was gehalten wird

- **RISK:** ein Risk-ETF aus der Kandidatenliste in `canary.py` (`RISK_TICKERS`: 2x-ETFs auf S&P 500, MSCI USA,
  MSCI World und MSCI ACWI). Gewählt wird **einmal zu Beginn der Risk-Phase** der Kandidat mit dem höchsten
  13612U-Momentum, gehalten wird er bis zum Phasenende.
- **DEFENSIV:** Gehalten wird Tagesgeld. Die Defensiv-Seite besteht nur noch daraus. Es gibt keine Defensiv-ETFs, keine Defensiv-Kurse und keinen
  Cash-Zustand. Der Backtest (`backtest.py`) rechnet Risk-off-Phasen als Tagesgeld (EZB-Einlagensatz abzüglich 0,25 %,
  nie unter 0 %, täglich nach Abgeltungsteuer gutgeschrieben). Ein Defensiv-ETF lohnt sich bei den vielen kurzen Phasen und
  den Spreads nicht.

**Momentum der Risk-Kandidaten:** normales 13612U-Momentum auf den Kursen der letzten 21/63/126/252 Handelstage, wie beim
Canary TIP (Fallbackkette 136U → 13U → 1U → längste Historie, wenn die Historie eines Kandidaten nicht reicht). Es ist
unabhängig vom Regime, auch über Tagesgeld-Phasen hinweg.

- **Zweistufige Abfrage:** Stufe 1 lädt TIP und `^NDX` über eine lange Historie (`REGIME_HISTORY_YEARS` = 10 plus Einlaufzeit)
  und liefert die Regime-Historie. Stufe 2 bestimmt daraus den Beginn der aktuellen Risk-Phase und lädt die Kandidaten ab
  einem Datum rund 252 Handelstage davor. Im Regime DEFENSIVE werden keine Kandidaten abgefragt.
- **Auswahl zum Phasenbeginn:** Das Script leitet den Phasenbeginn bei jedem Lauf aus der Regime-Historie ab (kein
  gespeicherter Zustand) und gibt als „Gehalten“ das Asset aus, das zu Phasenbeginn vorn lag. Daneben steht „Heute vorn“ (heutiger Spitzenreiter, nur zur
  Information) und die Momentum-Tabelle mit beiden Markierungen. Die Push-Nachricht zeigt als „Empfehlung“ den heutigen Spitzenreiter
  (Ticker im Titel, Name im Text), nicht das gehaltene Asset.
- **Hebel:** Die Kandidaten werden ohne Hebel-Anpassung verglichen, der Pool enthält deshalb nur 2x-Produkte. Ein 1x-Produkt
  (z. B. `XDEM.DE`) wurde entfernt: In einem Test der Auswahl zu den Phasenbeginnen mit echten Kursen wurde es nach Crashs
  bevorzugt und kostete in der Erholung viel Rendite. Derselbe Test zeigte bei gleich gehebelten Kandidaten keinen belastbaren
  Unterschied zwischen Kalender-Momentum und einem Momentum nur aus Risk-Tagen, daher die einfachere Methode. Die Auswahl
  hat insgesamt wenig Einfluss (die Kandidaten sind sehr ähnlich), die Stichprobe umfasst nur rund 12 Phasen. Alle
  Backtests verwenden ein festes S&P-500-Asset.

### Ausführung

Das Script läuft nach US-Börsenschluss (Sicherheitspuffer bis 16:04 New Yorker Zeit).
Das mit dem **heutigen** Schlusskurs bestätigte Regime ist die Grundlage für die Order am Abend.
Im Backtest wirkt das Signal von Tag *d−1* an Tag *d* (kein Look-Ahead).

---

## Ergebnisse des Backtests (nach Steuern, seit Dezember 2004)

Quelle: `backtest.py` (rein synthetisches S&P 500 aus SPY in EUR, Stand 20. Oktober 2026,
Risk-off als Tagesgeld, Spreads und Steuern modelliert). Hauptfall: 2x-Hebel in EUR wie `18MF.DE`.

| Variante | CAGR | Max. Drawdown | Sortino |
|---|---|---|---|
| 2x TIPxSMA (Hybrid) | 23,1 % | −59,0 % | 1,11 |
| 2x Buy & Hold | 17,6 % | −81,7 % | 0,86 |
| 1x TIPxSMA (Hybrid) | 12,9 % | −32,3 % | 1,12 |
| 1x Buy & Hold | 11,3 % | −51,4 % | 0,91 |

Sortino = annualisierte Rendite geteilt durch die Abwärtsschwankung (nur Tage mit Verlust zählen als Risiko, ohne Risikofreizins gerechnet). Er passt besser zu einer Strategie, die gezielt Verluste vermeiden will, als der Sharpe-Wert, der auch Aufwärtsschwankungen bestraft. Der Sharpe-Wert steht weiter in der Ausgabe von `backtest.py`.

**Sensitivitäten (CAGR des 2x-Hybrids, Vorsprung gegenüber Buy & Hold):**

| Variante | 2x Hybrid | 2x B&H | Vorsprung | 1x Hybrid (Vorsprung) |
|---|---|---|---|---|
| Hauptfall (EUR-Hebel, Spread ×1) | 23,1 % | 17,6 % | +5,5 PP | 12,9 % (+1,6 PP) |
| Hebel in USD (wie `DBPG.DE`) | 21,7 % | 15,5 % | +6,2 PP | 12,9 % (+1,6 PP) |
| Spread ×2 | 22,9 % | 17,6 % | +5,3 PP | 12,8 % (+1,5 PP) |
| Spread ×3 | 22,6 % | 17,6 % | +5,0 PP | 12,7 % (+1,4 PP) |

Die Strategie heißt in der Ausgabe von `backtest.py` „TIPxSMA“. Zeitraum bis Oktober 2026. Die Grafiken zeigen nur die 2x-Varianten, die Textauswertung auch 1x.

**Einordnung:**
- Ältere Läufe mit realen ETFs (früheres Script, entfernt) zeigten 2x etwa 24,7 % CAGR. Das war zu optimistisch: Europäische ETFs
  werden um 17:30 (Xetra) bewertet, das Signal entsteht aber erst zum US-Schluss. Am Xetra-Schluss sind nur rund 60 %
  der US-Tagesbewegung eingepreist, ein Verkauf zum Xetra-Kurs vermied deshalb einen Teil der Abendverluste.
  Der synthetische Kurs am US-Schluss entspricht einer Ausführung am Abend (z. B. Abendhandel).
- Der Vorsprung gegenüber Buy & Hold bleibt in allen Varianten klar: 2x +5,0 bis +6,2 PP, 1x +1,4 bis +1,6 PP,
  bei deutlich kleinerem Drawdown. Er kommt vor allem aus den Krisenphasen (2008, 2016, 2020, 2022). In einzelnen
  Jahren liegt Buy & Hold vorn (z. B. 2019, 2023).
- Spreads spielen wegen nur etwa 2,0 Wechseln pro Jahr kaum eine Rolle. Das reine TIP-Signal (rund 6 Wechsel pro Jahr)
  ist empfindlicher, das reine SMA-Signal liegt 2x bei rund 11 % und damit unter Buy & Hold.
- Die Hebelwährung ändert vor allem einzelne Jahre (EUR-Hebel verdoppelt auch die Wechselkursbewegung), kaum den Vorsprung.

### Robustheit

Diverse Tests haben keine zusätzlichen Parameter bestätigt, die über den Standard hinaus etwas verbessern:
Hysterese-Bänder um den SMA, Tagesfilter, mehrstimmige SMA-Abstimmung, Zeitverschiebung der Signale,
ein Drawdown-Signal (Kurs unter einem Anteil des k-Tage-Hochs) statt des SMA sowie Parameter-Overfitting-Prüfungen
(PBO, Walk-forward, Monte-Carlo). Die SMA-Länge von 50 bis 350 Tagen zeigt ein breites Plateau; die SMA200 liegt darauf
und bleibt der Standard. Gefundene Vorteile hingen jeweils an wenigen Episoden (z. B. Februar 2009, 2015/2022/2023).
Der einzige übernommene Wert aus dieser Suche ist die Bestätigung beim SMA-Wiedereinstieg (2 statt 1 Tag, weniger Wechsel).
Die Signale tragen im Hybrid nachweislich zum Ergebnis bei (Zeitverschiebungs-Test), der Standard liegt aber nahe an
einem Parametergipfel, daher sollten die Erwartungen für die Zukunft vorsichtiger sein als die Historie.

---

## Dateien

| Datei | Zweck |
|---|---|
| `canary.py` | **Live-Signal.** Stufe 1: lädt TIP und `^NDX`, berechnet TIP-Momentum und NDX-SMA200, filtert und kombiniert sie zur Regime-Historie (RISK oder DEFENSIVE). Stufe 2 (nur bei RISK): bestimmt den Phasenbeginn, lädt die Risk-Kandidaten und wählt den Kandidaten mit dem besten 13612U-Momentum zum Phasenbeginn. Gibt Signal-Historie (10 Tage) und Handlungsempfehlung aus. Enthält die Ticker-Konfiguration (`RISK_TICKERS`). |
| `ntfy_push.py` | Liest die Ausgabe von `canary.py` und schickt eine kurze Push-Nachricht über [ntfy](https://ntfy.sh): „RISK: <Ticker>“ oder „DEFENSIVE: Tagesgeld“. Ein Regimewechsel erhöht die Priorität. |
| `canary.yml` | GitHub-Actions-Workflow (gehört nach `.github/workflows/canary.yml`): installiert Pakete, führt `canary.py` aus, sendet den Push und meldet Fehler. Wird extern gestartet (siehe Einrichtung). |
| `yf_data.py` | Gemeinsame Kursdaten-Logik für alle Skripte: Abruf über yfinance mit Konsens-Abfrage, Kalender-Vollständigkeitsprüfung, Lückenfüllung aus zuvor bekannten Werten und Korrektur von Kurssprüngen. Kein Datei-Cache, damit rückwirkende Korrekturen von Yahoo ankommen. |
| `backtest.py` | **Backtest** mit rein synthetischem S&P 500 (SPY in EUR, 1x und 2x) statt realer ETF-Kurse. Vermeidet den Zeitversatz zwischen Xetra-Schluss (17:30) und US-Signal (nur rund 60 % der US-Bewegung sind am Xetra-Schluss eingepreist). Kosten zeitvariabel: fixe Kosten + (Hebel − 1) × Zins (FRED), Hebelwährung in `LEVER_CURRENCY` umschaltbar (EUR wie 18MF.DE, USD wie DBPG.DE); Wechselkurs wird von Datenfehlern bereinigt. Risk-off-Phasen ohne Defensiv-Asset werden mit Tagesgeld verzinst (EZB-Einlagensatz abzüglich 0,25 %, nie unter 0 %, täglich nach Abgeltungsteuer). Enthält die deutsche Steuerlogik, die Jahres- und Phasen-Tabellen und Kennzahlen (CAGR, Drawdown, Sharpe, Capture) für Hybrid, nur TIP und nur SMA gegen Buy & Hold, jeweils 1x und 2x. Konfiguration der Kosten und Datenbereinigung steht im Kopf der Datei. |
| `kalibrierung_hebel.py` | **Kalibrierung** des synthetischen Hebel-Modells: schätzt aus echten ETFs (18MF.DE, DBPG.DE, SXR8.DE, SXR4.DE) gegen SPY die fixen Kosten, die Zinsdurchleitung, die Hebelwährung und den Xetra-Zeitversatz (FRED-Zinsen, Newey-West-Regression). Liefert die Kostenparameter für `backtest.py`; Ausgabe unter `kalibrierung/`. |
| `stats.py` | **Depotauswertung:** liest CSV-Exporte der eigenen Käufe und Verkäufe (`stats/*.csv`), rekonstruiert den Bestand, berechnet Rendite und vergleicht mit Buy-&-Hold-Referenzen inklusive Vorabpauschale. Erzeugt `results.txt` und Plots. |
| `example.csv` | Beispiel für das CSV-Format von `stats.py` (`date;action;ticker;shares;sum`, Semikolon, Dezimalkomma). |
| `requirements.txt` | Festgelegte Paketversionen. `yfinance` ist bewusst nur nach unten begrenzt, weil Yahoo seine Schnittstelle regelmäßig ändert. |

---

## Modellannahmen des Backtests

- **`backtest.py`:** Das Risk-Asset ist durchgehend synthetisch: `SPY` (angepasster Schlusskurs,
  enthält Dividenden), in EUR umgerechnet (Wechselkurs `EUR=X`, eintägige Datenfehler bereinigt) und gehebelt.
  Keine realen ETF-Kurse und keine Verkettung. Kosten zeitvariabel, kalibriert gegen die realen Fonds ab 2011
  (18MF.DE, DBPG.DE, SXR8.DE, SXR4.DE; Script `kalibrierung_hebel.py`): Tagesrendite = Brutto − (fixe Kosten + (Hebel − 1) × Zins) / 252.
  **1x:** 0,25 % fix (iShares S&P 500). **2x, Hauptfall (EUR-Hebel wie `18MF.DE`):** 1,20 % fix + Euro-Zins (EZB-Einlagensatz,
  FRED `ECBDFR`), Zinsdurchleitung 97 %. **2x, Sensitivität (USD-Hebel wie `DBPG.DE`):** 1,58 % fix + US-Zins (`DFF`).
  Die 1,20 % enthalten rund 0,4 bis 0,5 PP Indexlücke MSCI USA gegen S&P 500 und sind auf SPY-Basis konservativ.
  Vor 2011 gibt es keine Kalibrierung, dort gelten dieselben Parameter als Annahme.
- **Frühere Läufe mit realen ETFs (Script entfernt):** Synthetisches Asset (2x ≈ 2,0 %, 1x ≈ 0,5 % flach) vor den ETF-Notierungen,
  ab Notierung (18MF.DE 2010-03-04, SXR4.DE ab 2011-01-01) die echten Kurse. Wegen des Xetra-Zeitversatzes optimistischer.
  `18MF.DE` hat am 2013-01-02 einen Kursbruch (Faktor ≈ 282), bei dem `yf_data.py` die Rendite des Bruchtags auf 0 % setzt;
  dadurch fehlen dort rund 9 %.
- **Steuern:** 26,375 % Kapitalertragsteuer auf realisierte Gewinne nach Teilfreistellung (30 % bei Aktienfonds),
  Vorabpauschale (Basiszins 2,5 %) zum Jahresende. Strategie und Buy & Hold nutzen dasselbe Steuermodell.
- **Jahrestabelle:** Jedes Jahr ist isoliert gerechnet (Steuerbasis 1.1., Kapitalertragsteuer nur auf Gewinne seit
  Jahresbeginn, Vorabpauschale enthalten). „Gesamt (echt)“ und „Durchschnitt p. a. (echt)“ beruhen auf dem
  durchgehenden Verlauf nach Steuern und enthalten die volle Steuerlast.
- **Spread:** Bei jedem Wechsel fällt die Hälfte des Geld-Brief-Spreads der verkauften und der gekauften Position an.
  Startwerte (voller Spread): 1x-ETF 0,05 %, 2x-ETF 0,20 %, Tagesgeld 0. Steuerlich wirkt er wie
  real (der Verkaufsabschlag mindert den Gewinn). `SPREAD_SCALE` skaliert alle Werte (0 = aus).
- **Tagesgeld:** In defensiven Phasen `max(EZB-Einlagensatz − 0,25 %, 0)`, täglich nach 26,375 % Steuer
  gutgeschrieben (ohne Teilfreistellung, ohne Spread, ohne Vorabpauschale). Wirkung rund +0,0 bis +0,2 PP CAGR.
- Nicht modelliert: Orderkosten, Slippage zwischen Signalschluss und Orderausführung, Sparer-Pauschbetrag, Kirchensteuer.

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
