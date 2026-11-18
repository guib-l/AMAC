"""DFTB-2 energies of the first five molecules of data/molecules.xyz,
computed by DFTB+ and deMonNano with the shell-resolved SCC off and on.

Each (software, molecule) pair gets two single-point calculations from
the same canonical description; only the basis and the "shell-dep"
attribute differ. The script prints the energies and the differences.

Usage:
    python examples/general/shell_dep_compare.py
"""

import json
from pathlib import Path

from ase.io import read
import numpy as np

import amac
from amac.amac import AMAC

DATA = Path(__file__).parents[1] / "data" / "molecules.xyz"
CONFIG = json.loads(Path("config-amac.json").read_text())
BASIS = {
    "dftb+": {
        "directory": CONFIG["software"]["dftb+"]["basis"],
    },
    "deMonNano": {
        "directory": CONFIG["software"]["deMonNano"]["basis"],
        "ptype": "BIO",
    },
}
SOFTWARES = ("dftb+", "deMonNano")

hubbard = {
    "off":{
        "C" : 0.38330,
        "H" : 0.4700,
        "O" : 0.5222,
        "N" : 0.4579
    },
    "on":{
        "C" : (0.4175,0.38330),
        "H" : 0.4700,
        "O" : (0.55640,0.5222),
        "N" : (0.49100,0.45790) 
    }
}

def total_energy(software, label, dep, image):
    """Return the DFTB-2 total energy (Hartree) of ``image``, or NaN on failure."""
    scc = "on" if dep else "off"
    hubbs = hubbard[scc]
    hubbs = dict(
        filter(lambda item: item[0] in np.unique(image.symbols), hubbs.items())
    )
    calc = AMAC(
        software=software,
        workdir=f".run/general/shell_dep/{software}/{label}/{scc}",
        label="on" if dep else "off",
    )
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dftb-2",
        method_args={"basis": BASIS[software],"scc-tol":1e-5,"scc-max":999, "shell-dep": dep},
        module="single-point",
        software_args={
            "dftb+":{"Hamiltonian.DFTB.CustomisedHubbards": hubbs}
        },
    )
    try:
        calc.run(image)
        return float(calc.instance.res.product["lowest-energy"])
    except Exception as error:
        print(f"{software:10s} {label:12s} shell-dep={dep!s:5s} failed: {error}")
        return float("nan")


images = read(DATA, index=":")[:5]
labels = [str(image.info.get("name", image.get_chemical_formula())) for image in images]

amac.configure_from_file("config-amac.json")

energies = {
    software: {
        dep: [total_energy(software, label, dep, image) for label, image in zip(labels, images)]
        for dep in (False, True)
    }
    for software in SOFTWARES
}

header = (
    f"{'structure':8s} | {'E+ off':>12s} {'E+ on':>12s} {'D+':>12s} | "
    f"{'E- off':>12s} {'E- on':>12s} {'D-':>12s} | {'off diff':>12s} {'on diff':>12s}"
)
print("\nE+ = DFTB+, E- = deMonNano, D+ / D- = on-off (Ha); all energies in Ha")
print(header)
for i, label in enumerate(labels):
    row = [energies[s][d][i] for s in SOFTWARES for d in (False, True)]
    a_off, a_on, b_off, b_on = row
    print(
        f"{label:8s} | {a_off:12.8f} {a_on:12.8f} {a_on - a_off:12.8f} | "
        f"{b_off:12.8f} {b_on:12.8f} {b_on - b_off:12.8f} | "
        f"{b_off - a_off:12.8f} {b_on - a_on:12.8f}"
    )
