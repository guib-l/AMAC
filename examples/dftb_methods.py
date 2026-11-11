"""Single-point energy of a water molecule with DFTB-1, DFTB-2, DFTB-3 and
CI-DFTB, run with DFTB+ and deMonNano.

The same canonical description is given to both programs; only the basis
differs. CI-DFTB is not available in DFTB+, and its deMonNano equivalence
is not written yet: both cases are reported instead of stopping the script.
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

water = molecule("H2O")
dimer = water + water.copy()
dimer.positions[3:] += [-0.2, 0.0, 2.7]

amac.configure_from_file("config-amac.json")

BASIS = {
    "dftb+": {
        "directory": "~/Téléchargements/mio-1-1",
    },
    "deMonNano": {
        "directory": "~/Téléchargements/deMonNano/basis",
        "ptype": "BIO",
    },
}

SCC = {
    "scc-max": 999,
    # "scc-tol": 1e-5,
    "filling": 50,
}

# Hubbard derivatives of the 3OB parameter set (a.u.).
HUBBARD_DERIVS = {"H": -0.1857, "O": -0.1575}

METHODS = {
    # "dftb-1": (water, {}),
    "dftb-2": (water, SCC),
    "dftb-3": (
        water,
        {
            **SCC,
            "h-correction": {"value": "damping", "exponent": 4.0},
            "hubbard-derivs": HUBBARD_DERIVS,
        },
    ),
    "ci-dftb": (
        dimer,
        {
            **SCC,
            "size-ci": 2,
            "fragments": [3, 3],
        },
    ),
}


for software, basis in BASIS.items():
    for method, (image, method_args) in METHODS.items():
        calc = AMAC(
            software=software,
            workdir=f".run/{software}/{method}",
            label=f"water-{method}",
        )
        calc.handler_register("lowest-energy")
        calc.parameters_register(
            method=method,
            method_args={"basis": basis, **method_args},
            module="single-point",
            module_args={},
        )
        try:
            calc.run(image)
        except (NotImplementedError, KeyError) as error:
            print(f"{software:10s} {method:8s} not available: {error}")
            continue
        print(f"{software:10s} {method:8s} done")
        calc.instance.pretty_print()
