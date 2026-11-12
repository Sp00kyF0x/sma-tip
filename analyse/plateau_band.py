"""
plateau_band.py - Grafische Auswertung des SMA-Band-Plateaus und seiner Stabilität (realistisches Modell)

Rechnet für ein Raster aus Ausstiegs- und Einstiegsschwelle (TREND_BAND_EXIT_PCT / TREND_BAND_ENTRY_PCT,
Bedeutung wie in backtest.py) jeweils den kompletten Backtest der Strategie MODE (Hybrid oder reine SMA). Referenz
ist der Standard ohne Band (0 / 0). Nur Zellen mit Ausstieg + Einstieg >= 0 (sonst überkreuzte Schwellen).

Modelle (MODEL):
  "backtest"  wie backtest.py: primäre Variante SP500_2x (Hebelwährung nach LEVER_CURRENCY in backtest.py,
              "EUR" oder "USD"), Tagesgeld ECBDFR, Start am ersten TIP-Signal (Dez. 2004). Mit APPLY_TAXES = True
              identisch zu backtest.py. Hybrid und reine SMA möglich.
  "usd"       längere Historie: nur reine SMA (vor 2003 gibt es weder TIP noch EUR/USD), S&P 500 2x synthetisch in
              USD (Wechselkurs konstant), Finanzierung und Tagesgeld zum US-Zins DFF, Start ab START_DATE, automatisch
              begrenzt (SPY ab 29.01.1993).
APPLY_TAXES = False rechnet ohne Kapitalertragsteuer und Vorabpauschale (Tagesgeld brutto), Spread bleibt. Damit
sieht man die reine Signalqualität des Bandes; mit Steuern zusätzlich den Vorteil seltener Verkäufe.
EVAL_RANGE wertet nur einen Teilzeitraum aus (die Rechnung läuft trotzdem ab Anfang, das Band hat ein Gedächtnis),
z. B. ("1993-01-01", "2004-12-06") für den Zeitraum, den die Tests im Modell "backtest" nie gesehen haben.

Grafik 1 (Plateau): CAGR-Differenz zur Referenz in Prozentpunkten p. a. Die gestrichelte Diagonale
(Ausstieg = -Einstieg) sind einzelne Schwellen, z. B. -1/+1 = raus und rein bei SMA * 1,01; rechts davon echte Bänder.

Grafik 2 (Stabilität), drei Karten mit derselben Achse:
  a) Vorsprung OHNE das beste Jahr (Hauptkriterium): Die Differenz zur Referenz wird in Jahresbeiträge zerlegt
     (Änderung von 100 * ln(Kurve Band / Kurve Referenz) je Kalenderjahr; die Summe ergibt exakt den
     Gesamtunterschied). Dann wird das Jahr mit dem größten Beitrag gestrichen und der Rest auf die Jahre verteilt.
     Bleibt das positiv, hängt der Vorteil nicht an einem einzelnen Ereignis. Mit DROP_BEST = 2 werden die zwei
     besten Jahre gestrichen (strenger).
  b) Bootstrap über die Jahre: Die Jahresbeiträge werden BOOTSTRAP_N-mal zufällig mit Zurücklegen neu gezogen;
     gezeigt wird, in welchem Anteil die Summe positiv ist. 50 % = kein erkennbarer Vorteil, 90 %+ = recht stabil.
  c) Trefferquote: Anteil der Jahre mit Vorteil unter den Jahren, in denen sich Band und Referenz überhaupt
     unterscheiden (|Beitrag| >= YEAR_TOL_PP). Anschaulich, aber ohne Größenordnung und bei wenigen Jahren grob.
  Warum a) das Hauptkriterium ist: Die Trefferquote zählt einen Vorteil von 0,5 Prozentpunkten genauso wie einen
  Nachteil von 8; der Bootstrap mischt die Größen, ist aber bei rund 8 abweichenden Jahren unsicher. a) beantwortet
  direkt die Frage "hängt der Vorteil an einem Jahr?" und ist in derselben Einheit wie Grafik 1.

Ausgabe: Konsole und im Ordner plateau_band/ je Lauf: <Kennung>_ergebnisse.txt, <Kennung>.csv,
         <Kennung>_1_rendite.png, <Kennung>_2_stabilitaet.png; die Kennung enthält MODE, MODEL, Hebelwährung,
         SMA-Filter (a/b aus strategie.toml), Steuern und Zeitraum,
         z. B. plateau_band_hybrid_backtest_EUR_a1b2_mitSteuern_2004-2026.
Aufruf:  python analyse/plateau_band.py   (aus dem Hauptverzeichnis; nutzt backtest.py und lib/)
Laufzeit: ein Backtest je Zelle (bei den Standardwerten gut 300 Zellen, je nach Rechner einige Minuten).
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

# Hauptverzeichnis in den Suchpfad, damit lib/ und backtest.py gefunden werden - egal von wo gestartet.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backtest as bt                                   # noqa: E402
from backtest import np, pd, plt                        # noqa: E402
from lib.pfade import results_dir                       # noqa: E402

# ----------------------------------------------------------------------
# Einstellungen
# ----------------------------------------------------------------------
MODE = "hybrid"                      # "hybrid" (SMA-TIP) oder "sma" (reine SMA-Strategie, mehr Wechsel)
MODEL = "backtest"                   # "backtest" (wie backtest.py, ab Dez. 2004) oder "usd" (nur "sma", ab 1993)
APPLY_TAXES = True                   # False = ohne Kapitalertragsteuer/Vorabpauschale (reine Signalqualität)
START_DATE = "1990-01-01"            # nur MODEL "usd": gewünschter Beginn, wird durch die Daten begrenzt
EVAL_RANGE: tuple[str | None, str | None] = (None, None)   # Auswertungszeitraum, z. B. ("1993-01-01", "2004-12-06")
EXIT_RANGE = (-2.0, 0.0)             # Ausstieg (Prozent der SMA, negativ = Ausstieg schon ÜBER der SMA)
ENTRY_RANGE = (0.0, 2.5)             # Einstieg (Prozent der SMA über der SMA)
STEP = 0.1
MARK_CELLS = ((-1.0, 1.0), (-1.0, 1.5), (-0.8, 0.8), (-0.5, 1.0))   # in den Grafiken markiert (nur gültige)
FOCUS_CELL = (-0.7, 2.0)             # Kandidat (Stern)
DROP_BEST = 1                        # so viele beste Jahre werden in Kriterium a) gestrichen
YEAR_TOL_PP = 0.1                    # ab diesem Jahresbeitrag (Prozentpunkte) gilt ein Jahr als abweichend
BOOTSTRAP_N = 5000
EXCLUDE_YEARS: tuple[int, ...] = ()  # z. B. (2026,), um ein im Nachhinein bekanntes Jahr auszublenden
OUTPUT_DIR = results_dir("plateau_band")   # ergebnisse/plateau_band/; Dateinamen enthalten die Einstellungen


def axis(lo: float, hi: float) -> np.ndarray:
    n = int(round((hi - lo) / STEP))
    return np.round(lo + STEP * np.arange(n + 1), 4)


def year_contrib(eq: pd.Series, ref: pd.Series) -> pd.Series:
    """Beitrag je Kalenderjahr zu 100 * ln(eq / ref); Summe = Gesamtunterschied."""
    lr = np.log(eq / ref) * 100.0
    year_end = lr.groupby(lr.index.year).last()
    contrib = year_end.diff()
    contrib.iloc[0] = year_end.iloc[0]
    return contrib.drop(index=[y for y in EXCLUDE_YEARS if y in contrib.index])


def metrics(contrib: pd.Series, rng: np.random.Generator) -> dict:
    d = contrib.to_numpy()
    n = len(d)
    total = float(d.sum())
    best = np.sort(d)[::-1][:DROP_BEST]
    dev = np.abs(d) >= YEAR_TOL_PP
    draws = rng.integers(0, n, size=(BOOTSTRAP_N, n))
    if not dev.any():                                   # identisch zur Referenz (z. B. 0/0)
        return {"per_year": 0.0, "ohne_beste": 0.0, "bootstrap": np.nan, "n_abw": 0, "n_besser": 0,
                "treffer": np.nan, "schlechtestes": 0.0, "bestes": 0.0, "bestes_jahr": 0}
    return {
        "per_year": total / n,
        "ohne_beste": (total - best.sum()) / (n - DROP_BEST),
        "bootstrap": float((d[draws].sum(axis=1) > 0).mean()) if n else np.nan,
        "n_abw": int(dev.sum()),
        "n_besser": int((d[dev] > 0).sum()),
        "treffer": float((d[dev] > 0).mean()) if dev.any() else np.nan,
        "schlechtestes": float(d.min()), "bestes": float(d.max()),
        "bestes_jahr": int(contrib.index[int(np.argmax(d))]),
    }


class Model:
    """Lädt die Daten einmal und rechnet je Zelle Position und Wertentwicklung (Steuern über APPLY_TAXES)."""

    def __init__(self):
        self.variant = next(iter(bt.RISK_TICKERS))
        if MODEL == "backtest":
            data = bt.load_market_data()
            self.canary, self.trend = data["canary_adj"], data["trend_adj"]
            self.risky = data["risky_adj_by_ticker"][self.variant]
            self.cost_text = data["cost_text_by_variant"][self.variant]
            net = data["cash_net_return"]
            if net is None:
                gross = pd.Series(0.0, index=self.risky.index)
            else:                                   # zurück auf brutto, Steuer unten nach APPLY_TAXES
                gross = net / (1.0 - bt.ABGELTUNGSTEUER_BASISSATZ) if bt.APPLY_CAPITAL_GAINS_TAX else net
            start = bt.backtest_tip_canary(self.canary, self.risky, self.trend, mode="hybrid")["first_valid_date"]
            self.cash_text = f"Tagesgeld {bt.TAGESGELD_RATE}"
            self.limit = "erstes TIP-Signal (wie backtest.py)"
        elif MODEL == "usd":
            if MODE != "sma":
                raise ValueError('MODEL "usd" geht nur mit MODE "sma" (vor 2003 gibt es kein TIP-Signal).')
            now_berlin = datetime.now(bt.BERLIN_TZ)
            end = bt.compute_query_end_date(now_berlin)
            self.canary = None
            self.trend = bt.get_adj_close(bt.TREND_TICKER, end)
            info = bt.RISK_TICKERS[self.variant]
            spy = bt.get_adj_close(info["ticker"], end)
            usd = bt.LEVER_PARAMS["USD"]
            dff = bt.load_fred_rate(usd["funding_rate"], needed_from=spy.index.min())
            if info["leverage"] != 1.0:
                self.risky, self.cost_text = bt.build_synthetic_eur(
                    spy, pd.Series(1.0, index=spy.index), info["leverage"], usd["fixed_cost_pa"], dff, "USD")
            else:
                self.risky, self.cost_text = bt.build_synthetic_eur(
                    spy, pd.Series(1.0, index=spy.index), 1.0, info["fixed_cost_pa"], None, "USD")
            rate = dff.reindex(self.risky.index, method="ffill")
            gross = (rate / 100.0 - bt.TAGESGELD_ABSCHLAG).clip(lower=0.0) / bt.TRADING_DAYS_PER_YEAR
            sma_start = self.trend.rolling(bt.TREND_SMA_DAYS).mean().dropna().index[0] + pd.Timedelta(days=1)
            cands = {"Wunsch START_DATE": pd.Timestamp(START_DATE), "erster SMA-Wert": sma_start,
                     f"Beginn {info['ticker']}": self.risky.index[0], "Beginn DFF": dff.index.min()}
            self.limit = max(cands, key=cands.get)
            start = cands[self.limit]
            self.cash_text = "Tagesgeld DFF"
        else:
            raise ValueError('MODEL muss "backtest" oder "usd" sein.')
        cal = self.risky.index
        self.calendar = cal[cal >= cal[cal.searchsorted(start)]]
        self.returns = self.risky.pct_change().fillna(0.0).reindex(self.calendar)
        g = gross.reindex(self.calendar).fillna(0.0)
        self.cash = g * (1.0 - bt.ABGELTUNGSTEUER_BASISSATZ) if APPLY_TAXES else g
        self.tax = {"RISK": bt.capital_gains_tax_rate_for_ticker(self.variant)}
        self.vp = {"RISK": bt.vorabpauschale_faktor_for_ticker(self.variant)}
        self.spread = {"RISK": bt.spread_for_ticker(self.variant)}
        lo, hi = EVAL_RANGE
        self.eval_lo = pd.Timestamp(lo) if lo else self.calendar[0]
        self.eval_hi = pd.Timestamp(hi) if hi else self.calendar[-1]

    def run(self, x: float, y: float) -> dict:
        bt.TREND_BAND_EXIT_PCT, bt.TREND_BAND_ENTRY_PCT = x, y
        if self.canary is not None:
            pos = bt.backtest_tip_canary(self.canary, self.risky, self.trend, mode=MODE)["daily_position"]
            pos = pos.reindex(self.calendar)
        else:
            sig = bt.trend_signal_position(self.trend, bt.TREND_SMA_DAYS, bt.TREND_CONFIRMATION_A,
                                           bt.TREND_CONFIRMATION_B)
            risk = bt.signal_to_master_calendar(sig, self.calendar) == "RISK"
            pos = pd.Series(np.where(risk, "RISK", "CASH"), index=self.calendar, dtype=object)
        bt.TREND_BAND_EXIT_PCT = bt.TREND_BAND_ENTRY_PCT = 0.0
        eq, *_ = bt.apply_taxes(pos, {"RISK": self.returns}, tax_rate_by_position=self.tax,
                                vorabpauschale_faktor_by_position=self.vp, spread_by_position=self.spread,
                                cash_return=self.cash, apply_capital_gains_tax=APPLY_TAXES,
                                apply_vorabpauschale=APPLY_TAXES)
        m = (eq.index >= self.eval_lo) & (eq.index <= self.eval_hi)
        eq, pos = eq[m] / eq[m].iloc[0], pos[m]
        r = pos == "RISK"
        return {"equity_after_tax": eq, "perf": bt.performance_stats(eq),
                "switches": max(int((r != r.shift(1)).sum() - 1), 0)}


def heat(ax, xs, ys, grid, title, cmap, vmin, vmax, fmt, cbar_label, zero_contour=None):
    im = ax.imshow(np.ma.masked_invalid(grid), origin="lower", aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax,
                   extent=(ys[0] - STEP / 2, ys[-1] + STEP / 2, xs[0] - STEP / 2, xs[-1] + STEP / 2))
    ax.set_facecolor("#dddddd")
    if zero_contour is not None and np.isfinite(grid).sum() > 3:
        ax.contour(ys, xs, np.where(np.isfinite(grid), grid, np.nan), levels=[zero_contour], colors="black",
                   linewidths=1.0)
    d = np.array([max(ys[0], -xs[-1]), min(ys[-1], -xs[0])])
    ax.plot(d, -d, "--", color="#555555", lw=1.0)                   # Diagonale = eine einzelne Schwelle
    for (mx, my) in MARK_CELLS:
        ax.plot(my, mx, "o", mfc="none", mec="black", ms=9, mew=1.2)
    ax.plot(FOCUS_CELL[1], FOCUS_CELL[0], "*", color="black", ms=13)
    ax.plot(0.0, 0.0, "s", mfc="white", mec="black", ms=8)
    ax.set_xlabel("Einstieg (% über SMA)")
    ax.set_ylabel("Ausstieg (% der SMA; negativ = schon über der SMA)")
    ax.set_title(title, fontsize=10)
    cb = plt.colorbar(im, ax=ax)
    cb.set_label(cbar_label)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model = Model()
    variant = model.variant
    xs, ys = axis(*EXIT_RANGE), axis(*ENTRY_RANGE)
    cells = [(float(x), float(y)) for x in xs for y in ys if x + y >= -1e-9]
    cells = list(dict.fromkeys((round(x, 4), round(y, 4))
                               for x, y in cells + list(MARK_CELLS) + [FOCUS_CELL, (0.0, 0.0)]
                               if x + y >= -1e-9))                      # überkreuzte Schwellen auslassen
    name = bt.STRATEGY_NAMES[MODE]
    tax_txt = "mit Steuern" if APPLY_TAXES else "ohne Steuern"
    period = f"{model.eval_lo.date()} bis {model.eval_hi.date()}"
    # Hebelwährung und SMA-Filter gehören in Kennung und Titel, damit Läufe mit anderen Werten
    # (LEVER_CURRENCY in backtest.py, bestaetigung_* in strategie.toml) sich nicht überschreiben.
    ccy = "USD" if MODEL == "usd" else bt.RISK_TICKERS[variant]["lever_currency"]
    filt = f"a{bt.TREND_CONFIRMATION_A}b{bt.TREND_CONFIRMATION_B}"
    tag = (f"plateau_band_{MODE}_{MODEL}_{ccy}_{filt}_{'mitSteuern' if APPLY_TAXES else 'ohneSteuern'}"
           f"_{model.eval_lo.year}-{model.eval_hi.year}")
    desc = (f"{name}, {variant}, Hebel in {ccy}, SMA-Filter a={bt.TREND_CONFIRMATION_A}/b={bt.TREND_CONFIRMATION_B}, "
            f"Modell {MODEL}, {tax_txt}, {period}")
    print(f"\n{len(cells)} Backtests ({desc}) ...")

    ref = model.run(0.0, 0.0)
    ref_eq = ref["equity_after_tax"]
    ref_cagr = ref["perf"]["CAGR"]
    rng = np.random.default_rng(2026)
    rows, t0 = [], time.perf_counter()
    for k, (x, y) in enumerate(cells, 1):
        r = ref if (x, y) == (0.0, 0.0) else model.run(x, y)
        m = metrics(year_contrib(r["equity_after_tax"], ref_eq), rng)
        rows.append({"ausstieg": x, "einstieg": y, "cagr": r["perf"]["CAGR"],
                     "d_cagr_pp": (r["perf"]["CAGR"] - ref_cagr) * 100.0, "max_dd": r["perf"]["Max DD"],
                     "sortino": r["perf"]["Sortino"], "wechsel": r["switches"], **m})
        if k % 25 == 0 or k == len(cells):
            el = time.perf_counter() - t0
            print(f"  {k}/{len(cells)} fertig ({el:.0f} s, noch ca. {el / k * (len(cells) - k):.0f} s)")
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_DIR / f"{tag}.csv", index=False, float_format="%.5f")

    def grid(col: str) -> np.ndarray:
        g = np.full((len(xs), len(ys)), np.nan)
        for _, r in df.iterrows():
            i = np.flatnonzero(np.isclose(xs, r["ausstieg"]))
            j = np.flatnonzero(np.isclose(ys, r["einstieg"]))
            if len(i) and len(j):
                g[i[0], j[0]] = r[col]
        return g

    # --- Grafik 1 ---
    g1 = grid("d_cagr_pp")
    lim = np.nanmax(np.abs(g1)) or 1.0
    fig, ax = plt.subplots(figsize=(10, 7))
    heat(ax, xs, ys, g1, f"Plateau: CAGR-Differenz zum Standard ohne Band\n({desc})\n"
         "Quadrat = Standard 0/0, Stern = Kandidat, Kreise = Nachbarn, schwarze Linie = Nulllinie,\n"
         "gestrichelt = eine einzelne Schwelle (Ausstieg = -Einstieg), grau = ungültig (überkreuzt)",
         "RdYlGn", -lim, lim, "", "Prozentpunkte p. a.", zero_contour=0.0)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / f"{tag}_1_rendite.png", dpi=150)
    plt.close(fig)

    # --- Grafik 2 ---
    fig, axes = plt.subplots(1, 3, figsize=(21, 6.5))
    g_a = grid("ohne_beste")
    la = np.nanmax(np.abs(g_a)) or 1.0
    heat(axes[0], xs, ys, g_a, f"a) Vorsprung ohne die {DROP_BEST} besten Jahr(e) (Hauptkriterium)\n"
         "Ø Prozentpunkte (log) je übrigem Jahr; Linie = 0", "RdYlGn", -la, la, "", "Prozentpunkte p. a.",
         zero_contour=0.0)
    heat(axes[1], xs, ys, grid("bootstrap") * 100, f"b) Bootstrap über die Jahre: Anteil Ziehungen mit Vorteil\n"
         "Linie = 80 %", "RdYlGn", 0, 100, "", "%", zero_contour=80.0)
    heat(axes[2], xs, ys, grid("treffer") * 100, "c) Trefferquote: Anteil besserer Jahre unter den abweichenden\n"
         "Linie = 50 %", "RdYlGn", 0, 100, "", "%", zero_contour=50.0)
    fig.suptitle(f"Stabilität des Band-Vorteils ({desc}; gleiche Achsen wie Grafik 1)")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / f"{tag}_2_stabilitaet.png", dpi=150)
    plt.close(fig)

    # --- Text ---
    years_note = f", ohne Jahre {', '.join(map(str, EXCLUDE_YEARS))}" if EXCLUDE_YEARS else ""
    lines = ["=" * 118,
             f"SMA-Band-Plateau ({desc}; Referenz ohne Band: CAGR {ref_cagr:.2%}{years_note})",
             "=" * 118,
             f"Risk: {model.cost_text}; {model.cash_text}; Rechnung ab {model.calendar[0].date()} "
             f"(begrenzt durch: {model.limit}).",
             f"Raster Ausstieg {EXIT_RANGE[0]:+g} bis {EXIT_RANGE[1]:+g}, Einstieg {ENTRY_RANGE[0]:+g} bis "
             f"{ENTRY_RANGE[1]:+g}, Schritt {STEP:g}; {len(df)} Zellen.",
             f"Zellen mit CAGR-Vorteil: {(df['d_cagr_pp'] > 0).mean():.0%}; mit Vorteil auch ohne die {DROP_BEST} "
             f"besten Jahr(e): {(df['ohne_beste'] > 0).mean():.0%}; Bootstrap >= 80 %: {(df['bootstrap'] >= 0.8).mean():.0%}.",
             ""]
    hdr = (f"  {'Aus':>5}{'Ein':>6}{'dCAGR':>8}{'ohne best':>11}{'Bootstr.':>10}{'Treffer':>10}{'schlecht.':>11}"
           f"{'bestes (Jahr)':>16}{'Max DD':>9}{'Wechsel':>9}")

    def line(r) -> str:
        head = f"  {r['ausstieg']:>+5.2f}{r['einstieg']:>+6.2f}"
        tail = f"{r['max_dd']:>9.1%}{int(r['wechsel']):>9d}"
        if int(r["n_abw"]) == 0:
            return head + f"{'Referenz (kein Band bzw. identisch)':>66}" + tail
        return (head + f"{r['d_cagr_pp']:>+8.2f}{r['ohne_beste']:>+11.2f}{r['bootstrap']:>10.0%}"
                f"{f'{int(r.n_besser)}/{int(r.n_abw)}':>10}{r['schlechtestes']:>+11.1f}"
                f"{f'{r.bestes:+.1f} ({int(r.bestes_jahr)})':>16}" + tail)

    lines += ["Markierte Zellen:", hdr]
    for c in [(0.0, 0.0), FOCUS_CELL] + list(MARK_CELLS):
        sel = df[np.isclose(df["ausstieg"], c[0]) & np.isclose(df["einstieg"], c[1])]
        if len(sel):
            lines.append(line(sel.iloc[0]))
    lines += ["", f"Die 15 Zellen mit dem größten Vorsprung ohne die {DROP_BEST} besten Jahr(e):", hdr]
    for _, r in df[df["n_abw"] > 0].sort_values("ohne_beste", ascending=False).head(15).iterrows():
        lines.append(line(r))
    lines += ["",
              "Spalten: dCAGR = CAGR-Differenz (Prozentpunkte p. a.); ohne best = Ø Jahresbeitrag ohne die besten "
              "Jahre (log-Prozentpunkte); Bootstr. = Anteil Bootstrap-Ziehungen mit Vorteil; Treffer = bessere / "
              f"abweichende Jahre (ab {YEAR_TOL_PP:g}); schlecht./bestes = Jahresbeitrag."]
    text = "\n".join(lines)
    print("\n" + text)
    (OUTPUT_DIR / f"{tag}_ergebnisse.txt").write_text(text + "\n", encoding="utf-8")
    print(f"\nErgebnisse, CSV und Grafiken in {OUTPUT_DIR}/ gespeichert.")


if __name__ == "__main__":
    try:
        main()
    except bt.FredUnavailableError as err:
        print(f"\nFehler: {err}")
    if sys.stdin.isatty():
        input("\nEnter zum Beenden drücken...")
