"""Save AMAC results in txt, JSON and SQLite files, then read them back.

A DFTB-2 single point is run with DFTB+ on a few molecules; each result is
saved in the three formats with one ``Store`` object per file:

- ``energies.txt``: one line per calculation (index, formula, chosen
  columns), plus ``calc.json`` describing the calculation;
- ``results.json`` and ``results.db``: every metadata, the geometry and
  every product of the handlers.
"""

from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC
from amac.store import Store

OUTPUT = Path(".run/store")

amac.configure_from_file("config-amac.json")

stores = [
    Store(OUTPUT / "energies.txt", columns=["lowest-energy"], calc_file=True),
    Store(OUTPUT / "results.json"),
    Store(OUTPUT / "results.db"),
]

for name in ("H2O", "NH3", "CH4"):
    calc = AMAC(software="dftb+", workdir=OUTPUT / name, label=name)
    calc.handler_register("lowest-energy", "energy_resume")
    calc.parameters_register(
        method="dftb-2",
        method_args={
            "basis": {"directory": "/home/vboxuser/Téléchargements/mio-1-1"},
            "scc-tol": 1e-5,
        },
        module="single-point",
    )
    calc.run(molecule(name))
    for store in stores:
        calc.store(store)

print((OUTPUT / "energies.txt").read_text())

# Read back: every store returns a list of flat dicts.
for record in Store(OUTPUT / "results.db").load(software="dftb+"):
    print(f"{record['formula']:6s} {record['lowest-energy']:14.8f} Ha  {record['image']}")
