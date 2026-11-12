"""TD-DFTB (linear response) on water (H2O) with both programs.

The same water geometry gets a ground-state DFTB-2 single-point energy
plus four TD-DFTB excitations in DFTB+ and deMonNano (module ``td-dftb``,
``excitations=4``, ``symmetry="singlet"``, and for DFTB+ additionally
``diagonalizer="arpack"``); the lowest energy and the excited-state
tables are printed. An offset between the programs is expected
(different parameter sets: mio-1-1 for DFTB+, BIO for deMonNano).

Usage:
    python examples/tddftb.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

BASIS = {
    "dftb+": {
        "directory": "~/Téléchargements/parameters_dftb/mio-1.1.0/skfiles",
    },
    "deMonNano": {
        "directory": "/home/pguibourg/Téléchargements/deMonNano/basis",
        "ptype": "BIO",
    },
}

SCC = {
    "scc-max": 999,
    "scc-tol": 1e-5,
}

# "diagonalizer" is a DFTB+ option (the Casida block); deMonNano has none.
MODULE_ARGS = {
    "dftb+": {
        "excitations": 4,
        "symmetry": "singlet",
        "diagonalizer": "arpack",
    },
    "deMonNano": {
        "excitations": 4,
        "symmetry": "singlet",
    },
}

water = molecule("H2O")

amac.configure_from_file("config-amac.json")

results = {}
for software in ("dftb+", "deMonNano"):
    try:
        calc = AMAC(
            software=software,
            workdir=f".run/tddftb/{software}",
            label="water",
        )
        calc.handler_register("excited-states", "lowest-energy")
        calc.parameters_register(
            method="dftb-2",
            method_args={"basis": BASIS[software], **SCC},
            module="td-dftb",
            module_args=MODULE_ARGS[software],
        )
        calc.run(water)
        product = calc.instance.res.product
        results[software] = (
            float(product["lowest-energy"]),
            product["excited-states"],
        )
    except Exception as error:
        print(f"{software:10s} failed: {error}")
        continue

for software in ("dftb+", "deMonNano"):
    if software not in results:
        continue
    energy, states = results[software]
    print(f"\n{software}: lowest energy = {energy:.8f} Ha")
    for symmetry, table in states.items():
        print(f" {symmetry} states:")
        print(
            f"   {'state':>8s} {'w (eV)':>8s} {'oscillator':>11s} "
            f"{'from -> to':>10s} {'weight':>8s}"
        )
        for name, state in table.items():
            transition = f"{state['from']} -> {state['to']}"
            print(
                f"   {name:>8s} {state['w']:8.3f} {state['oscillator']:11.6f} "
                f"{transition:>10s} {state['weight']:8.3f}"
            )

first_singlet = {
    software: min(table["singlet"].values(), key=lambda state: state["w"])["w"]
    for software, (_, table) in results.items()
    if "singlet" in table and table["singlet"]
}
if len(first_singlet) == 2:
    difference = first_singlet["deMonNano"] - first_singlet["dftb+"]
    print(
        f"\nFirst singlet excitation difference (deMonNano - dftb+) = "
        f"{difference:+.3f} eV; an offset is expected (different parameter "
        "sets: mio-1-1 vs BIO)."
    )
