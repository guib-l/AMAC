"""DFTB-1, DFTB-2 and DFTB-3 single-point energies of water with deMonNano.

DFTB-3 uses the 3OB Hubbard derivatives (written to the "3ord_param" file)
and the damped H correction; with the BIO parameters this only illustrates
the syntax.

Usage:
    python examples/deMonNano/02_dftb_levels.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

# BIO parameters are SCC-only: DFTB-1 (non-SCC) needs the NSC ones.
METHODS = {
    "dftb-1": {"basis": {**BASIS, "ptype": "NSC"}},
    "dftb-2": {"scc-tol": 1e-6},
    "dftb-3": {
        "scc-tol": 1e-6,
        "hubbard-derivs": {"H": -0.1857, "O": -0.1575},
        "h-correction": {"value": "damping", "exponent": 4.0},
    },
}

for method, args in METHODS.items():
    calc = AMAC(software="deMonNano", workdir=f".run/deMonNano/levels/{method}", label="water")
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method=method,
        method_args={"basis": BASIS, **args},  # args may override "basis"
        module="single-point",
    )
    calc.run(molecule("H2O"))
    print(f"{method}: {calc.instance.res.product['lowest-energy']:.8f} Ha")
