"""DFTB-2 single-point energy of water with DFTB+, shell-resolved SCC off
and on.

Needs the "dftb+" section of config-amac.json: absolute "executable" and
"basis" (directory of the mio-1-1 Slater-Koster files).

Usage:
    python examples/dftbplus/11_shell_dep.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

off = AMAC(software="dftb+", workdir=".run/dftbplus/shell_dep/off", label="off")
off.handler_register("lowest-energy", "energy-resume")
off.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS, "scc-tol": 1e-6, "shell-dep": False},
    module="single-point",
)
off.run(molecule("H2O"))

on = AMAC(software="dftb+", workdir=".run/dftbplus/shell_dep/on", label="on")
on.handler_register("lowest-energy", "energy-resume")
on.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS, "scc-tol": 1e-6, "shell-dep": True},
    module="single-point",
)
on.run(molecule("H2O"))

e_off = off.instance.res.product["energy-resume"]["energy"]
e_on = on.instance.res.product["energy-resume"]["energy"]
print(f"shell-dep = False   E = {e_off:.8f} Ha")
print(f"shell-dep = True    E = {e_on:.8f} Ha")
print(f"E(on) - E(off) = {e_on - e_off:.8f} Ha")
