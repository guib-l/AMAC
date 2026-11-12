"""Molecular-dynamics settings shared by the assets."""

from dataclasses import dataclass

# Berendsen coupling time used when "time-constant" is not given (fs).
DEFAULT_TIME_CONSTANT = 100.0


@dataclass
class MDSettings:
    """Canonical MD settings (time in fs, temperature in K)."""

    steps: int
    time_step: float
    temperature: float | None
    thermostat: str
    time_constant: float


def md_settings(md: dict) -> MDSettings:
    """Read the ``md`` node written by the equiv.json of an asset.

    Raises:
        ValueError: Berendsen thermostat without a temperature.
    """
    thermostat, options = next(iter((md.get("thermostat") or {"none": {}}).items()))
    temperature = md.get("temperature")
    if thermostat == "berendsen" and temperature is None:
        raise ValueError("the berendsen thermostat needs a temperature")
    return MDSettings(
        steps=md["steps"],
        time_step=md["dt"],
        temperature=temperature,
        thermostat=thermostat,
        time_constant=(options or {}).get("time_constant", DEFAULT_TIME_CONSTANT),
    )
