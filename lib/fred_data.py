"""
Gemeinsame Zinsreihen-Abfrage (FRED) für backtest.py und kalibrierung_hebel.py
=============================================================================

Dieses Modul bündelt Abruf, Prüfung und Zwischenspeicherung der FRED-Zinsreihen (ECBDFR, DFF) an einer
Stelle, wie yf_data.py es für die Kurse tut. Fehlerbehandlung und Meldungen gelten damit für alle Skripte.

Ablauf von load_fred_rate(series_id):
  1. Abruf der CSV (https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>), bis zu ATTEMPTS Versuche mit
     Wartezeit dazwischen und TIMEOUT_S Sekunden je Versuch. Jeder Fehlversuch wird mit Dauer und Ursache gemeldet.
  2. Format-Prüfung der Antwort VOR dem Speichern: Eine Fehlerseite (HTML, Sperre, leere Antwort) wird erkannt und
     gelangt nie in den Cache. Zusätzlich darf die neue Reihe nicht kürzer sein als der vorhandene Cache
     (abgeschnittene Antwort) - sonst gilt der Abruf als fehlgeschlagen und der Cache bleibt unangetastet.
  3. Bei Erfolg wird die CSV in daten/FRED_<ID>.csv zwischengespeichert und eine [ok]-Zeile ausgegeben
     (Zeitraum, Zeilenzahl, Zahl der neuen Zeilen gegenüber dem Cache, ggf. Zahl der Versuche).
  4. Bei Misserfolg wird der Cache genutzt (mit Warnung inklusive letztem Datum und Alter; ist er älter als
     STALE_AFTER_DAYS, kommt ein deutlicher Hinweis, dass die jüngsten Tage fehlen). Ohne gültigen Cache bricht
     die Funktion mit FredUnavailableError ab (wird in den Skripten ohne Traceback gemeldet).
  Anders als bei Kursen ist ein Cache hier unkritisch: Zinssätze werden praktisch nie rückwirkend geändert.
  Meldungsstufen wie in yf_data.py: [ok] Abruf in Ordnung, [info] Hinweis ohne Folgen (Fehlversuch mit
  Wiederholung; Reihe beginnt erst nach dem angefragten Zeitraum), [warn] Cache statt frischer Daten.
  Mit dem Parameter needed_from sagt der Aufrufer, ab wann er Werte braucht; beginnt die Reihe später, kommt
  eine [info]-Zeile (die Aufrufer brechen in diesem Fall selbst mit einer eigenen Meldung ab).

WARUM der Accept-Header gesetzt ist (Diagnose vom 2026-11-10, fred_diagnose.py / fred_diagnose2.py):
FRED beantwortete Python-Abrufe ohne Accept-Header nicht (Verbindung steht, aber keine Antwort -> "The read
operation timed out"), während derselbe Abruf mit "Accept: text/csv,*/*" in unter 0,2 s ankam. Ein Chrome-User-Agent
wird dagegen mit einem Verbindungsabbruch abgewiesen, deshalb bleibt der User-Agent bewusst schlicht. ALPN,
IPv4/IPv6 und Proxy spielten keine Rolle. Sollte der Abruf wieder hängen, zeigt die Meldung je Versuch Dauer und
Ursache; ein erneuter Lauf von fred_diagnose2.py grenzt den Unterschied ein.
"""

from __future__ import annotations

import io
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

from lib.pfade import data_dir

FRED_CACHE_DIR = data_dir()      # daten/ im Hauptverzeichnis, gemeinsam für alle Skripte (lib/pfade.py)
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (taa-backtest)", "Accept": "text/csv,*/*"}
ATTEMPTS = 3                       # Versuche je Reihe
TIMEOUT_S = 20                     # Sekunden je Versuch (ein funktionierender Abruf dauert unter einer Sekunde)
WAIT_BETWEEN_S = (2.0, 5.0)        # Wartezeit vor Versuch 2 und 3
STALE_AFTER_DAYS = 10              # ab diesem Alter des letzten Wertes gilt ein Cache als veraltet
SHRINK_TOLERANCE_ROWS = 3          # die neue Reihe darf höchstens so viele Zeilen weniger haben als der Cache


class FredUnavailableError(RuntimeError):
    """FRED nicht erreichbar bzw. liefert keine CSV, und es gibt keinen brauchbaren Cache.
    Wird in den Skripten (__main__) ohne Traceback gemeldet."""


def describe_failure(exc: Exception) -> str:
    """Kurze, lesbare Ursache statt Roh-Antwort: bei einer HTML-Seite deren <title>
    (z. B. 'Site Maintenance | St. Louis Fed'), bei Zeitüberschreitung ein klarer Satz, sonst die Meldung."""
    msg = str(exc)
    m = re.search(r"<title>\s*(.*?)\s*<", msg.replace("\\n", " "), re.I)
    if m and m.group(1):
        return f"FRED antwortet mit einer Webseite statt Daten: „{m.group(1)}“"
    if "keine FRED-CSV" in msg:
        return "FRED antwortet mit einer Webseite statt Daten"
    if isinstance(exc, TimeoutError) or "timed out" in msg.lower():
        return f"keine Antwort innerhalb von {TIMEOUT_S} s"
    return msg


def parse_fred_csv(text: str, series_id: str) -> pd.Series:
    """Liest eine FRED-CSV (zwei Spalten: Datum, Wert; Werte in PROZENT p. a.) und prüft vorher das Format.
    Eine Fehlerseite (HTML, Sperre, leere Antwort) wird so erkannt, statt als kaputte CSV zu scheitern oder in
    den Cache zu gelangen. Fehlende Werte (".") werden verworfen."""
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    if "," not in first or series_id not in first or "<" in first:
        raise ValueError(f"keine FRED-CSV für {series_id} (Anfang der Antwort: {text.strip()[:120]!r})")
    df = pd.read_csv(io.StringIO(text))
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    out = pd.Series(values.to_numpy(dtype=float), index=pd.to_datetime(df.iloc[:, 0])).dropna().sort_index()
    if out.empty:
        raise ValueError(f"FRED {series_id}: keine Werte.")
    return out


def _download(series_id: str) -> tuple[str, int]:
    """Lädt die CSV mit Wiederholungen; gibt den geprüften Text und die Zahl der benötigten Versuche zurück
    oder wirft den letzten Fehler."""
    url = FRED_URL.format(series_id=series_id)
    last_exc: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        t0 = time.perf_counter()
        try:
            request = urllib.request.Request(url, headers=REQUEST_HEADERS)
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as resp:
                text = resp.read().decode("utf-8")
            parse_fred_csv(text, series_id)                      # nur prüfen, Ergebnis nicht benötigt
            return text, attempt
        except Exception as exc:                                  # noqa: BLE001
            last_exc = exc
            if attempt < ATTEMPTS:
                wait = WAIT_BETWEEN_S[min(attempt - 1, len(WAIT_BETWEEN_S) - 1)]
                print(f"[info]     FRED {series_id}: Versuch {attempt}/{ATTEMPTS} fehlgeschlagen nach "
                      f"{time.perf_counter() - t0:.1f} s ({describe_failure(exc)}), neuer Versuch in {wait:g} s.")
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def _read_cache(cache: Path, series_id: str) -> pd.Series | None:
    if not cache.exists():
        return None
    try:
        return parse_fred_csv(cache.read_text(encoding="utf-8"), series_id)
    except ValueError:
        return None


def _coverage_info(series_id: str, series: pd.Series, needed_from) -> None:
    """[info], wenn der Aufrufer Werte ab einem Datum braucht, das VOR dem Beginn der Reihe liegt."""
    if needed_from is None:
        return
    needed = pd.Timestamp(needed_from).normalize()
    first = series.index.min()
    if first > needed:
        print(f"[info]     FRED {series_id}: Reihe beginnt erst am {first.date()} "
              f"(angefragt ab {needed.date()}, davor liegen keine Werte vor).")


def load_fred_rate(series_id: str, needed_from=None) -> pd.Series:
    """Zinsreihe (Prozent p. a., Tageswerte) von FRED; Ablauf siehe Modul-Docstring.
    needed_from: optional, ab wann der Aufrufer Werte braucht (nur für die [info]-Meldung)."""
    url = FRED_URL.format(series_id=series_id)
    cache = FRED_CACHE_DIR / f"FRED_{series_id}.csv"
    cached = _read_cache(cache, series_id)
    try:
        text, attempts = _download(series_id)
        out = parse_fred_csv(text, series_id)
        if cached is not None and len(out) + SHRINK_TOLERANCE_ROWS < len(cached):
            raise ValueError(f"die geladene Reihe ist kürzer als der Cache ({len(out)} statt {len(cached)} Zeilen)")
        FRED_CACHE_DIR.mkdir(exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        _coverage_info(series_id, out, needed_from)
        if cached is None:
            delta = "Cache neu angelegt"
        elif len(out) > len(cached):
            n_new = len(out) - len(cached)
            delta = f"{n_new} neue Zeile(n) gegen\u00fcber dem Cache"
        else:
            delta = "keine neuen Zeilen gegen\u00fcber dem Cache"
        tries = "" if attempts == 1 else f" nach {attempts} Versuchen"
        print(f"[ok]       FRED {series_id}: Abruf erfolgreich{tries} ({out.index.min().date()} - "
              f"{out.index.max().date()}, {len(out)} Zeilen, {delta}).")
        return out
    except Exception as exc:                                       # noqa: BLE001
        reason = describe_failure(exc)
        if cached is None:
            had_cache = cache.exists()
            raise FredUnavailableError(
                f"FRED-Daten {series_id}: Abruf fehlgeschlagen ({reason}) und "
                + ("der lokale Cache ist ungültig.\n" if had_cache else "lokal ist kein Cache vorhanden.\n")
                + (f"  Was tun: {cache} löschen und später erneut starten, oder\n" if had_cache
                   else "  Was tun: später erneut starten, oder\n")
                + f"  die CSV im Browser von {url} laden\n"
                  f"  und als {cache} speichern.") from None
        last = cached.index.max().date()
        age = (datetime.now().date() - last).days
        note = (f"[warn]     FRED {series_id}: Abruf fehlgeschlagen ({reason}), nutze Cache {cache.name} "
                f"(letzter Wert {last}, {age} Tage alt).")
        if age > STALE_AFTER_DAYS:
            note += " ACHTUNG: Der Cache ist veraltet, die jüngsten Tage fehlen."
        print(note)
        _coverage_info(series_id, cached, needed_from)
        return cached
