"""Implicit solvation settings shared by the assets."""

from dataclasses import dataclass


@dataclass
class SolvationSettings:
    """Canonical solvation settings.

    ``solvent`` is the software name (translated by its equiv.json, or the
    name given by the user when the software list does not have it).
    """

    model: str
    solvent: str | None
    epsilon: float | None


def solvation_settings(node: dict) -> SolvationSettings:
    """Read the ``solvation`` node written by the equiv.json of an asset.

    Raises:
        ValueError: Neither or both of solvent and epsilon, or epsilon with
            a model other than cpcm.
    """
    settings = SolvationSettings(node["model"], node.get("solvent"), node.get("epsilon"))
    if (settings.solvent is None) == (settings.epsilon is None):
        raise ValueError("solvation: give either a solvent or an epsilon")
    if settings.epsilon is not None and settings.model != "cpcm":
        raise ValueError(f"solvation: epsilon is only allowed with cpcm, not {settings.model}")
    return settings
