"""Compare DFTB-2 total energies computed by DFTB+ and deMonNano.

Every structure of a multi-frame (ext)XYZ file gets a single-point DFTB-2
calculation with both programs, from the same canonical description; only
the basis differs. The script prints the energies side by side, the mean
absolute error and the Pearson correlation between the two programs, and
draws a parity plot.

The two programs use different parameter sets (mio-1-1 for DFTB+, BIO for
deMonNano), so an offset between the absolute energies is expected: the
correlation tells how well the two follow each other.

Usage:
    python examples/compare_dftb.py [molecules.xyz]

The structure label is read from ``name=`` in the extXYZ comment line, or
falls back to the chemical formula.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from ase.io import read

import amac
from amac.amac import AMAC

DATA = Path(__file__).parent / "data" / "molecules.xyz"

BASIS = {
    "dftb+": {
        "directory": "/home/vboxuser/Téléchargements/mio-1-1",
    },
    "deMonNano": {
        "directory": "/home/vboxuser/Téléchargements/deMonNano/basis",
        "ptype": "BIO",
    },
}

SCC = {
    "scc-max": 999,
    "scc-tol": 1e-5,
}


def total_energy(software, label, image):
    """Return the DFTB-2 total energy (Hartree) of ``image``, or NaN on failure."""
    calc = AMAC(
        software=software,
        workdir=f".run/compare/{software}/{label}",
        label=label,
    )
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dftb-2",
        method_args={"basis": BASIS[software], **SCC},
        module="single-point",
        module_args={},
        software_args={
            "deMonNano": {"DEMON_PARAMETERS.ACTIVE.DFTB.FHUB": True},
        },
    )
    try:
        calc.run(image)
        return float(calc.instance.res.product["lowest-energy"])
    except Exception as error:
        print(f"{software:10s} {label:12s} failed: {error}")
        return float("nan")


path = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA
images = read(path, index=":")
labels = [str(image.info.get("name", image.get_chemical_formula())) for image in images]

amac.configure_from_file("config-amac.json")

energies = {
    software: np.array(
        [total_energy(software, label, image) for label, image in zip(labels, images)]
    )
    for software in BASIS
}
e_dftbplus, e_demon = energies["dftb+"], energies["deMonNano"]

print(f"\n{'structure':12s} {'E dftb+ (Ha)':>16s} {'E deMonNano (Ha)':>18s} {'diff (Ha)':>12s}")
for label, a, b in zip(labels, e_dftbplus, e_demon):
    print(f"{label:12s} {a:16.8f} {b:18.8f} {b - a:12.6f}")

ok = ~(np.isnan(e_dftbplus) | np.isnan(e_demon))
if ok.sum() < 2:
    sys.exit("Fewer than two structures succeeded with both programs.")

mae = np.mean(np.abs(e_demon[ok] - e_dftbplus[ok]))
r = np.corrcoef(e_dftbplus[ok], e_demon[ok])[0, 1]
print(f"\nMAE = {mae:.6f} Ha   Pearson r = {r:.6f}   ({ok.sum()}/{len(labels)} structures)")

fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(e_dftbplus[ok], e_demon[ok])
for label, a, b in zip(np.array(labels)[ok], e_dftbplus[ok], e_demon[ok]):
    ax.annotate(label, (a, b), textcoords="offset points", xytext=(4, 4), fontsize=8)
low = min(e_dftbplus[ok].min(), e_demon[ok].min())
high = max(e_dftbplus[ok].max(), e_demon[ok].max())
ax.plot([low, high], [low, high], "k--", linewidth=1, label="y = x")
ax.set_xlabel("E total DFTB+ (Ha)")
ax.set_ylabel("E total deMonNano (Ha)")
ax.set_title(f"DFTB-2 — MAE = {mae:.4f} Ha, r = {r:.4f}")
ax.legend()
fig.tight_layout()

output = Path(".run/compare/parity.png")
output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(output, dpi=150)
print(f"Parity plot written to {output}")
