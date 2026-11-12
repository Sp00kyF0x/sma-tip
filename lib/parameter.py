"""
Liest die zentralen Strategie-Parameter aus strategie.toml (Hauptverzeichnis) und prüft sie.

Andere Skripte verwenden die Werte über die Konstanten dieses Moduls, z. B.
    from lib import parameter as P
    P.TREND_SMA_DAYS, P.TREND_BAND_EXIT_PCT, ...
Fehlt die Datei, ist ein Wert falsch oder unplausibel, bricht das Laden mit einer klaren Meldung
(ParameterError) ab - lieber kein Signal als eines mit falschen Regeln.

Benötigt Python 3.11 oder neuer (Modul tomllib).
"""

from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:                                   # Python < 3.11
    raise SystemExit("Fehler: strategie.toml braucht Python 3.11 oder neuer (Modul tomllib).") from None

from lib.pfade import PROJECT_ROOT

PARAMETER_FILE = PROJECT_ROOT / "strategie.toml"


class ParameterError(ValueError):
    """strategie.toml fehlt oder enthält ungültige Werte."""


def _load() -> dict:
    if not PARAMETER_FILE.exists():
        raise ParameterError(f"{PARAMETER_FILE} fehlt - die Datei gehört ins Hauptverzeichnis.")
    try:
        with PARAMETER_FILE.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ParameterError(f"{PARAMETER_FILE.name} ist kein gültiges TOML: {exc}") from None


def _get(cfg: dict, section: str, key: str, kind):
    try:
        value = cfg[section][key]
    except KeyError:
        raise ParameterError(f"{PARAMETER_FILE.name}: Eintrag [{section}] {key} fehlt.") from None
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)
    if not isinstance(value, kind) or isinstance(value, bool):
        raise ParameterError(f"{PARAMETER_FILE.name}: [{section}] {key} = {value!r} hat den falschen Typ "
                             f"(erwartet {kind.__name__}).")
    return value


def _positive_int(cfg: dict, section: str, key: str) -> int:
    value = _get(cfg, section, key, int)
    if value < 1:
        raise ParameterError(f"{PARAMETER_FILE.name}: [{section}] {key} muss mindestens 1 sein (ist {value}).")
    return value


_cfg = _load()

CANARY_TICKER: str = _get(_cfg, "tip", "ticker", str)
CANARY_NAME: str = _get(_cfg, "tip", "name", str)
_lookbacks = _get(_cfg, "tip", "lookback_tage", list)
if (not _lookbacks or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in _lookbacks)
        or list(_lookbacks) != sorted(set(_lookbacks))):
    raise ParameterError(f"{PARAMETER_FILE.name}: [tip] lookback_tage muss eine aufsteigende Liste positiver "
                         f"ganzer Zahlen sein (ist {_lookbacks!r}).")
LOOKBACK_DAYS: tuple[int, ...] = tuple(_lookbacks)
CONFIRMATION_A: int = _positive_int(_cfg, "tip", "bestaetigung_aus")
CONFIRMATION_B: int = _positive_int(_cfg, "tip", "bestaetigung_ein")

TREND_TICKER: str = _get(_cfg, "sma", "ticker", str)
TREND_NAME: str = _get(_cfg, "sma", "name", str)
TREND_SMA_DAYS: int = _positive_int(_cfg, "sma", "tage")
TREND_CONFIRMATION_A: int = _positive_int(_cfg, "sma", "bestaetigung_aus")
TREND_CONFIRMATION_B: int = _positive_int(_cfg, "sma", "bestaetigung_ein")
TREND_BAND_EXIT_PCT: float = _get(_cfg, "sma", "band_ausstieg_pct", float)
TREND_BAND_ENTRY_PCT: float = _get(_cfg, "sma", "band_einstieg_pct", float)
if TREND_BAND_EXIT_PCT + TREND_BAND_ENTRY_PCT < 0:
    raise ParameterError(f"{PARAMETER_FILE.name}: band_ausstieg_pct + band_einstieg_pct muss >= 0 sein "
                         f"(ist {TREND_BAND_EXIT_PCT:+g} + {TREND_BAND_ENTRY_PCT:+g}); sonst liegen die "
                         f"Schwellen überkreuzt.")
for _name, _v in (("band_ausstieg_pct", TREND_BAND_EXIT_PCT), ("band_einstieg_pct", TREND_BAND_ENTRY_PCT)):
    if abs(_v) > 20:
        raise ParameterError(f"{PARAMETER_FILE.name}: [sma] {_name} = {_v:+g} ist unplausibel groß "
                             f"(Angabe in Prozent der SMA, z. B. -0.7).")


def band_text() -> str:
    """Kurzbeschreibung des Bandes für Ausgaben, z. B. 'raus <= SMA x 1,0070, rein > SMA x 1,0200'."""
    if TREND_BAND_EXIT_PCT == 0 and TREND_BAND_ENTRY_PCT == 0:
        return "kein Band (Kurs gegen SMA)"
    lo = 1.0 - TREND_BAND_EXIT_PCT / 100.0
    hi = 1.0 + TREND_BAND_ENTRY_PCT / 100.0
    return f"raus bei Kurs <= SMA x {lo:.4f}, rein bei Kurs > SMA x {hi:.4f}".replace(".", ",")
