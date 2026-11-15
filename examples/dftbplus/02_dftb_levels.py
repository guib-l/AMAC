"""DFTB-1, DFTB-2 and DFTB-3 single-point energies of water with DFTB+.

DFTB-3 uses the 3OB Hubbard derivatives and the damped H correction; with
the mio-1-1 parameters this only illustrates the syntax.

Usage:
    python examples/dftbplus/02_dftb_levels.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

METHODS = {
    "dftb-1": {},
    "dftb-2": {"scc-tol": 1e-6},
    "dftb-3": {
        "scc-tol": 1e-6,
        "hubbard-derivs": {"H": -0.1857, "O": -0.1575},
        "h-correction": {"value": "damping", "exponent": 4.0},
    },
}

for method, args in METHODS.items():
    calc = AMAC(software="dftb+", workdir=f".run/dftbplus/levels/{method}", label="water")
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method=method,
        method_args={"basis": BASIS, **args},
        module="single-point",
    )
    calc.run(molecule("H2O"))
    print(f"{method}: {calc.instance.res.product['lowest-energy']:.8f} Ha")
