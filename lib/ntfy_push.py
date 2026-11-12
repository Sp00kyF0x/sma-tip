"""
Schickt das Ergebnis eines canary.py-Laufs als kurze Push-Nachricht über ntfy.

Aufruf (siehe .github/workflows/canary.yml):
    python lib/ntfy_push.py canary_output.txt

Das Thema (Topic) kommt aus der Umgebungsvariable NTFY_TOPIC (in GitHub
als Secret hinterlegt). Optional: NTFY_SERVER (Standard https://ntfy.sh).

Die Werte werden aus der Textausgabe von canary.py gelesen (letzte Zeile
der Signal-Historie, Zeile "Aktuell bestätigtes Regime", Zeile
"Heute vorn:", Zeile "Risk-Phase seit", [warn]-Zeilen). Ändert sich das
Ausgabeformat von canary.py, muss dieses Script angepasst werden; kann es
die Ausgabe nicht lesen, bricht es ab (der Workflow meldet das per Push).

Nachricht:
  Das Regime ist RISK oder DEFENSIVE (im Regime DEFENSIVE wird nur
  Tagesgeld gehalten; es gibt keine Defensiv-ETFs und keinen Cash-Zustand).
  Titel:    "<Regime>: <Asset>", also "RISK: <Ticker>" oder "DEFENSIVE:
            Tagesgeld". Bei einem Regimewechsel "Wechsel zu <Regime>:
            <Asset>" (hohe Priorität). Ein Wechsel liegt nur vor, wenn
            sich das Regime gegenüber dem Vortag ändert. Titel und
            Empfehlung nennen den heutigen Spitzenreiter im Momentum
            ("Heute vorn" in der Ausgabe von canary.py), nur zur
            Information; er kann sich innerhalb einer Phase ändern. Das
            tatsächlich gehaltene Asset (Wahl zum Phasenbeginn) steht nur
            in der Ausgabe von canary.py.
            Börse geschlossen (Wochentag nach dem Cutoff, aber der letzte
            Kurs ist nicht von heute, z.B. US-Feiertag): Titel mit
            Präfix "Börse zu: ", niedrige Priorität, kein "Wechsel zu"
            (der Stand ist der des letzten Handelstags, ein damaliger Wechsel
            wurde schon gemeldet).
  Inhalt:   TIP-Wert, SMA-Abstand (NDX zur SMA200), Regime, Empfehlung
            (bei RISK der Name des Assets, nicht der Ticker), bei RISK der Beginn der Risk-Phase, Stand, bei Bedarf
            Warnzeilen (z.B. Lauf vor dem Cutoff, korrigierter Kurssprung).
Die vollständige Ausgabe steht im Protokoll des GitHub-Laufs.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

MAX_BYTES = 3900


REGIME_LABELS = {"RISK": "RISK", "DEFENSIVE": "DEFENSIVE"}


def _fmt_pct(text: str) -> str:
    """'-2.13%' -> '-2,13 %' (Vorzeichen immer sichtbar, Komma)."""
    value = float(text.strip().rstrip("%"))
    return f"{value:+.2f}".replace(".", ",") + " %"


def _fmt_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def _run_date_ny(text: str) -> datetime:
    """Zeitpunkt des Laufs in New Yorker Zeit, gelesen aus der ersten Zeile von
    canary.py ("Aktuelle Zeit: 2026-11-26 22:06:00 (Berlin) / ..."), sonst jetzt."""
    m = re.search(r"Aktuelle Zeit: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \(Berlin\)", text)
    ny = ZoneInfo("America/New_York")
    if m:
        berlin = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo("Europe/Berlin"))
        return berlin.astimezone(ny)
    return datetime.now(ny)


def _market_closed(info: dict, text: str) -> bool:
    """Wochentag in New York, Lauf nach dem Cutoff, aber der Stand ist nicht
    von heute -> heute gab es keinen Handel (Feiertag)."""
    if info["stand"] is None or "[warn] Es ist noch vor" in text:
        return False
    run = _run_date_ny(text)
    return run.weekday() < 5 and info["stand"] != run.date().isoformat()


def parse_output(text: str) -> dict:
    lines = text.splitlines()
    info: dict = {"state": None, "stand": None, "target": None,
                  "phase_since": None, "prev_state": None, "tip": None,
                  "gap": None, "warnings": []}

    for line in lines:
        m = re.match(r"Aktuell bestätigtes Regime \(Stand Schlusskurs ([\d-]+)\): (\w+)", line)
        if m:
            info["stand"], info["state"] = m.group(1), m.group(2)
        m = re.match(r"Heute vorn: (\S+) \| (.+?)\s*$", line)
        if m:
            info["target"] = (m.group(1), m.group(2))
        m = re.match(r"Risk-Phase (?:mindestens )?seit ([\d-]+)", line)
        if m:
            info["phase_since"] = m.group(1)
        if line.startswith("[warn]"):
            info["warnings"].append(line)

    # Signal-Historie: Zeilen "DATUM | TIP-Mom  TIP best. | Abstand  SMA best. | Regime"
    rows = []
    for line in lines:
        if re.match(r"^\d{4}-\d{2}-\d{2} \|", line):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 4:
                rows.append((parts[1].split()[0], parts[2].split()[0], parts[3]))
    if not rows:
        raise ValueError("Signal-Historie in der Ausgabe nicht gefunden.")
    info["tip"], info["gap"] = rows[-1][0], rows[-1][1]
    if len(rows) >= 2:
        info["prev_state"] = rows[-2][2]
    return info


def _short_warning(line: str) -> str:
    m = re.search(r"vor (\d\d:\d\d) Uhr", line)
    if line.startswith("[warn] Es ist noch vor") and m:
        return f"Achtung: Lauf vor {m.group(1)} Uhr New Yorker Zeit, Stand ist der Vortag"
    m = re.match(r"\[warn\]\s+(\S+): extremer Kurssprung am ([\d-]+)", line)
    if m:
        return f"Achtung: Kurssprung bei {m.group(1)} am {_fmt_date(m.group(2))} korrigiert"
    return "Achtung: " + line[len("[warn]"):].strip()[:150]


def build_message(text: str) -> tuple[str, str, int]:
    """Gibt (Titel, Nachricht, Priorität 1-5) zurück."""
    info = parse_output(text)
    if info["state"] is None:
        raise ValueError("Regime in der Ausgabe nicht gefunden - Lauf unvollständig?")

    if info["state"] not in REGIME_LABELS:
        raise ValueError(f"Unbekanntes Regime in der Ausgabe: {info['state']!r}")
    regime = info["state"]
    if regime == "RISK":
        if info["target"] is None:
            raise ValueError("Zeile 'Heute vorn' (Risk-Asset) in der Ausgabe nicht gefunden - Lauf unvollständig?")
        asset_short, asset_full = info["target"]
        headline = f"RISK: {asset_short}"
        change_headline = f"Wechsel zu RISK: {asset_short}"
        recommendation = asset_full
    else:
        headline = "DEFENSIVE: Tagesgeld"
        change_headline = "Wechsel zu DEFENSIVE: Tagesgeld"
        recommendation = "Tagesgeld"

    closed = _market_closed(info, text)
    changed = (not closed and info["prev_state"] is not None
               and info["prev_state"] != regime)
    if closed:
        title, priority = f"Börse zu: {headline}", 2
    else:
        title = change_headline if changed else headline
        priority = 4 if changed else 3

    lines = [f"TIP: {_fmt_pct(info['tip'])}",
             f"SMA: {_fmt_pct(info['gap'])}",
             f"Regime: {REGIME_LABELS[regime]}",
             f"Empfehlung: {recommendation}"]
    if regime == "RISK" and info["phase_since"] is not None:
        lines.append(f"Risk-Phase seit: {_fmt_date(info['phase_since'])}")
    lines.append(f"Stand: {_fmt_date(info['stand'])}"
                 + (" (Börse geschlossen, keine neuen Kurse)" if closed else ""))

    lines += [_short_warning(w) for w in info["warnings"]]

    body = "\n".join(lines)
    raw = body.encode("utf-8")
    if len(raw) > MAX_BYTES:
        body = raw[:MAX_BYTES].decode("utf-8", errors="ignore") + "\n[gekürzt - Details im GitHub-Protokoll]"
    return title, body, priority


def post(server: str, topic: str, title: str, body: str, priority: int) -> None:
    req = urllib.request.Request(
        f"{server.rstrip('/')}/{topic}",
        data=body.encode("utf-8"),
        headers={"Title": title, "Priority": str(priority)},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"ntfy antwortete mit Status {resp.status}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python ntfy_push.py <canary_output.txt>")
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        raise SystemExit("Umgebungsvariable NTFY_TOPIC fehlt (GitHub-Secret anlegen).")
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
    title, body, priority = build_message(text)
    post(server, topic, title, body, priority)
    print(f"[ok] Push gesendet: {title}")


if __name__ == "__main__":
    main()
