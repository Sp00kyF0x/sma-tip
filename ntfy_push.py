"""
Schickt das Ergebnis eines canary.py-Laufs als Push-Nachricht über ntfy.

Aufruf (siehe .github/workflows/canary.yml):
    python ntfy_push.py canary_output.txt

Das Thema (Topic) kommt aus der Umgebungsvariable NTFY_TOPIC (in GitHub
als Secret hinterlegt). Optional: NTFY_SERVER (Standard https://ntfy.sh).

Die Nachricht enthält:
  - Titel: Regime bzw. "Regimewechsel: A -> B" (hohe Priorität), wenn sich
    das Regime gegenüber dem Vortag der Signal-Historie geändert hat,
  - den gewählten Ziel-Ticker (bei RISK/DEFENSIVE),
  - Warnhinweise ([warn]-Zeilen der Ausgabe, z.B. Lauf vor dem Cutoff,
    korrigierte Kurssprünge in den letzten Tagen),
  - den Hinweis zu einem im Aufbau befindlichen Regimewechsel und das
    FAZIT.
ntfy erlaubt maximal ca. 4 KB pro Nachricht; die komplette Ausgabe steht
im Protokoll des GitHub-Laufs.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request

MAX_BYTES = 3900


def parse_output(text: str) -> dict:
    lines = text.splitlines()
    info: dict = {"regime": None, "stand": None, "target": None,
                  "changed_from": None, "warnings": [], "hints": [], "fazit": []}

    for line in lines:
        m = re.match(r"Aktuell bestätigtes Regime \(Stand Schlusskurs ([\d-]+)\): (\w+)", line)
        if m:
            info["stand"], info["regime"] = m.group(1), m.group(2)
        if "<- heute gewählt" in line:
            m = re.match(r"\s*(\S+)\s+(.*?)\s{2,}", line)
            if m:
                info["target"] = f"{m.group(1)} - {m.group(2)}"
        if line.startswith("[warn]"):
            info["warnings"].append(line)
        if line.startswith("[Hinweis]"):
            info["hints"].append(line)

    # Regime der letzten beiden Zeilen der Signal-Historie
    rows: list[str] = []
    in_table = False
    for line in lines:
        if re.match(r"^-+\+-+", line):
            in_table, rows = True, []
            continue
        if in_table:
            if re.match(r"^\d{4}-\d{2}-\d{2} \|", line):
                rows.append(line.rsplit("|", 1)[1].strip())
            else:
                in_table = False
    if len(rows) >= 2 and rows[-1] != rows[-2]:
        info["changed_from"] = rows[-2]

    # FAZIT-Block: alles nach der zweiten "====="-Zeile
    marks = [i for i, l in enumerate(lines) if l.startswith("=" * 20)]
    if len(marks) >= 2:
        info["fazit"] = [l for l in lines[marks[1] + 1:] if l.strip()]
    return info


def build_message(text: str) -> tuple[str, str, int]:
    """Gibt (Titel, Nachricht, Priorität 1-5) zurück."""
    info = parse_output(text)
    if info["regime"] is None:
        raise ValueError("Regime in der Ausgabe nicht gefunden - Lauf unvollständig?")

    if info["changed_from"]:
        title = f"Regimewechsel: {info['changed_from']} -> {info['regime']}"
        priority = 4
    else:
        title = f"TIP-Canary: {info['regime']}"
        priority = 3

    parts = [f"Regime: {info['regime']}  (Stand {info['stand']})"]
    if info["target"]:
        parts.append(f"Ziel: {info['target']}")
    if info["warnings"]:
        parts.append("\n" + "\n".join(info["warnings"]))
    if info["hints"]:
        parts.append("\n" + "\n".join(info["hints"]))
    if info["fazit"]:
        parts.append("\n" + "\n".join(info["fazit"]))
    body = "\n".join(parts)

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
