"""Serial and parallel DFTB-2 single point of a water cluster with deMonNano.

``process_unit`` fills the "{process_unit}" placeholder of the "launcher"
given in config-amac.json (e.g. ["/usr/bin/mpirun", "-np", "{process_unit}"]).

Usage:
    python examples/deMonNano/10_parallel.py
"""

import json
import time
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

# 3x3x3 cube of water molecules, 3 Å apart.
cluster = molecule("H2O")
for x in range(3):
    for y in range(3):
        for z in range(3):
            if x or y or z:
                water = molecule("H2O")
                water.translate([3.0 * x, 3.0 * y, 3.0 * z])
                cluster += water

for process_unit in (1, 4):
    calc = AMAC(
        software="deMonNano",
        process_unit=process_unit,
        workdir=f".run/deMonNano/parallel/{process_unit}",
        label="cluster",
    )
    calc.handler_register("lowest-energy")
    calc.parameters_register(method="dftb-2", method_args={"basis": BASIS}, module="single-point")
    start = time.perf_counter()
    calc.run(cluster)
    elapsed = time.perf_counter() - start
    energy = calc.instance.res.product["lowest-energy"]
    print(f"{process_unit} process(es): {energy:.8f} Ha in {elapsed:.1f} s")
