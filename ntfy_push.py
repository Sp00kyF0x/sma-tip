"""
Schickt das Ergebnis eines canary.py-Laufs als kurze Push-Nachricht über ntfy.

Aufruf (siehe .github/workflows/canary.yml):
    python ntfy_push.py canary_output.txt

Das Thema (Topic) kommt aus der Umgebungsvariable NTFY_TOPIC (in GitHub
als Secret hinterlegt). Optional: NTFY_SERVER (Standard https://ntfy.sh).

Die Werte werden aus der Textausgabe von canary.py gelesen (letzte Zeile
der Signal-Historie, Zeile "Aktuell bestätigtes Regime", Markierung
"<- heute gewählt", [warn]-Zeilen). Ändert sich das
Ausgabeformat von canary.py, muss dieses Script angepasst werden; kann es
die Ausgabe nicht lesen, bricht es ab (der Workflow meldet das per Push).

Nachricht:
  Titel:    "<Regime>: <Asset>", bei einem Regimewechsel
            "Wechsel zu <Regime>: <Asset>" (hohe Priorität). Das Regime ist
            nur RISK oder DEFENSIVE; Cash ist ein Asset der Defensiv-Seite.
            Ein Wechsel liegt nur vor, wenn sich das Regime gegenüber dem
            Vortag ändert (nicht bei DEFENSIVE <-> Cash).
  Inhalt:   TIP-Wert, SMA-Abstand (NDX zur SMA200), Regime, Empfehlung, Stand,
            bei Bedarf Warnzeilen (z.B. Lauf vor dem Cutoff, korrigierter
            Kurssprung).
Die vollständige Ausgabe steht im Protokoll des GitHub-Laufs.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request

MAX_BYTES = 3900


def _two_state(state: str) -> str:
    """CASH ist ein Asset der Defensiv-Seite, kein eigenes Regime."""
    return "RISK" if state == "RISK" else "DEFENSIVE"


def _fmt_pct(text: str) -> str:
    """'-2.13%' -> '-2,13 %' (Vorzeichen immer sichtbar, Komma)."""
    value = float(text.strip().rstrip("%"))
    return f"{value:+.2f}".replace(".", ",") + " %"


def _fmt_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def parse_output(text: str) -> dict:
    lines = text.splitlines()
    info: dict = {"state": None, "stand": None, "target": None,
                  "prev_state": None, "tip": None, "gap": None,
                  "warnings": []}

    for line in lines:
        m = re.match(r"Aktuell bestätigtes Regime \(Stand Schlusskurs ([\d-]+)\): (\w+)", line)
        if m:
            info["stand"], info["state"] = m.group(1), m.group(2)
        if "<- heute gewählt" in line:
            m = re.match(r"\s*(\S+)\s+(.*?)\s{2,}", line)
            if m:
                info["target"] = (m.group(1), m.group(2))
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
        return f"Achtung: Lauf vor {m.group(1)} Uhr, Stand ist der Vortag"
    m = re.match(r"\[warn\]\s+(\S+): extremer Kurssprung am ([\d-]+)", line)
    if m:
        return f"Achtung: Kurssprung bei {m.group(1)} am {_fmt_date(m.group(2))} korrigiert"
    return "Achtung: " + line[len("[warn]"):].strip()[:150]


def build_message(text: str) -> tuple[str, str, int]:
    """Gibt (Titel, Nachricht, Priorität 1-5) zurück."""
    info = parse_output(text)
    if info["state"] is None:
        raise ValueError("Regime in der Ausgabe nicht gefunden - Lauf unvollständig?")

    regime = _two_state(info["state"])
    if info["state"] == "CASH" or info["target"] is None:
        asset_short, asset_full = "Cash", "Cash"
    else:
        asset_short = info["target"][0]
        asset_full = info["target"][1]

    changed = info["prev_state"] is not None and _two_state(info["prev_state"]) != regime
    title = f"Wechsel zu {regime}: {asset_short}" if changed else f"{regime}: {asset_short}"
    priority = 4 if changed else 3

    lines = [f"TIP: {_fmt_pct(info['tip'])}",
             f"SMA: {_fmt_pct(info['gap'])}",
             f"Regime: {regime}",
             f"Empfehlung: {asset_full}",
             f"Stand: {_fmt_date(info['stand'])}"]

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
