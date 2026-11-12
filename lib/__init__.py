"""Hilfsmodule des Projekts (werden nicht direkt aufgerufen).

  pfade.py      zentrale Ordner (daten/, ergebnisse/) relativ zum Hauptverzeichnis
  parameter.py  liest und prüft strategie.toml (zentrale Strategie-Parameter)
  band.py       SMA-Rohsignal mit Band (gemeinsam für canary.py und backtest.py)
  yf_data.py    Kursdaten (Yahoo Finance) mit Prüfungen
  fred_data.py  Zinsreihen (FRED) mit Cache
  ntfy_push.py  Push-Nachricht aus der Ausgabe von canary.py (im GitHub-Workflow)
"""
