"""Periodic DFTB-2 single-point energy on 1x1 graphene with both programs.

The same structure and k-points grid are computed in DFTB+ and deMonNano;
the total energies and the k-points used are printed. A filling
temperature is needed because graphene is metallic, and an energy offset
between the programs is expected (different parameter sets: mio-1-1 for
DFTB+, BIO for deMonNano).

deMonNano reference energy for this geometry and grid: -3.47255044 Ha
(DeMonNanoPy test reference).

Usage:
    python examples/periodic.py
"""

import numpy as np
from ase.atoms import Atoms

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

KP = [25, 25, 2]

SCC = {
    "scc-max": 999,
    "scc-tol": 1e-5,
    # "filling": 50,
}

# Same 1x1 graphene as DeMonNanoPy's example_periodic.py.
CELL = np.array(
    [
        [2.460000, 0.000000, 0.000000],
        [-1.230000, 2.130422, 0.000000],
        [0.000000, 0.000000, 100.00000],
    ]
)
POSITIONS = np.array(
    [
        [0.000000, 0.000000, 0.000000],
        [1.230000, 0.710000, 0.000000],
    ]
)

graphene = Atoms(["C", "C"], positions=POSITIONS, cell=CELL, pbc=True)

amac.configure_from_file("config-amac.json")

results = {}
for software in ("dftb+", "deMonNano"):
    try:
        calc = AMAC(
            software=software,
            workdir=f".run/periodic/{software}",
            label="graphene",
        )
        calc.handler_register("lowest-energy", "k-points")
        calc.parameters_register(
            method="dftb-2",
            method_args={"basis": BASIS[software], "kpoints": KP, **SCC},
            module="single-point",
            module_args={},
            software_args={
                "deMonNano": {"DEMON_PARAMETERS.ACTIVE.DFTB.FHUB": True},
            },
        )
        calc.run(graphene)
        product = calc.instance.res.product
        results[software] = (
            float(product["lowest-energy"]),
            np.asarray(product["k-points"]),
        )
    except Exception as error:
        print(f"{software:10s} failed: {error}")
        continue

print(f"\n{'software':10s} {'E (Ha)':>12s} {'k-points':>10s}   ")
for software in ("dftb+", "deMonNano"):
    if software not in results:
        continue
    energy, kpoints = results[software]
    print(f"{software:10s} {energy:12.8f} {len(kpoints):10d} ")

if {"dftb+", "deMonNano"} <= results.keys():
    difference = results["deMonNano"][0] - results["dftb+"][0]
    print(
        f"\nEnergy difference (deMonNano - dftb+) = {difference:+.8f} Ha; "
        "an offset is not expected "
    )
