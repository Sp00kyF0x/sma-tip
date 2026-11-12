"""
Zentrale Pfade des Projekts - unabhängig davon, von wo aus ein Skript gestartet wird.

  PROJECT_ROOT  Hauptverzeichnis (enthält backtest.py, canary.py, strategie.toml)
  DATA_DIR      daten/       Caches: bekannte Kurswerte (yf_data.py), FRED-Zinsreihen (fred_data.py)
  RESULTS_DIR   ergebnisse/  Ausgaben der Skripte, je Skript ein Unterordner

Umzug alter Caches: Früher lagen die Caches im Ordner "yf_data" (im Hauptverzeichnis). data_dir()
benennt ihn beim ersten Aufruf einmalig in "daten" um bzw. übernimmt fehlende Dateien, damit keine
bekannten Kurswerte verloren gehen.
"""

from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "daten"
RESULTS_DIR = PROJECT_ROOT / "ergebnisse"
_OLD_DATA_DIRS = (PROJECT_ROOT / "yf_data", Path(__file__).resolve().parent / "yf_data")
_migrated = False


def data_dir() -> Path:
    """DATA_DIR, nach einmaliger Übernahme eines alten yf_data-Ordners (siehe Modul-Docstring)."""
    global _migrated
    if not _migrated:
        _migrated = True
        for old in _OLD_DATA_DIRS:
            if not old.is_dir():
                continue
            if not DATA_DIR.exists():
                old.rename(DATA_DIR)
                print(f"[info]     Cache-Ordner {old.name}/ nach {DATA_DIR.name}/ umbenannt.")
                continue
            moved = 0
            for f in old.rglob("*"):
                target = DATA_DIR / f.relative_to(old)
                if f.is_file() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(target))
                    moved += 1
            if moved:
                print(f"[info]     {moved} Datei(en) aus {old} nach {DATA_DIR.name}/ übernommen "
                      f"(der alte Ordner kann gelöscht werden).")
    return DATA_DIR


def results_dir(name: str) -> Path:
    """Ausgabeordner ergebnisse/<name>/ (wird angelegt)."""
    path = RESULTS_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return path
