"""Dispersion correction on a water dimer with DFTB-2, run with DFTB+ and
deMonNano.

DFTB+ takes a dispersion model and its parameters (here taken from the
DFTB+ manual, appendices G and H, for the mio set); deMonNano offers two
ready-made models, "model-1" (DISP=1) and "model-2" (DISP=2), without
parameters.
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

water = molecule("H2O")
dimer = water + water.copy()
dimer.positions[3:] += [-0.2, 0., 2.7]

amac.configure_from_file("config-amac.json")

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

DISPERSIONS = {
    "dftb+": {
        "none": None,
        # Universal Force Field Lennard-Jones, no parameter needed.
        "lj-uff": "lj-uff",
        # D3 with Becke-Johnson damping ("old default" column, appendix G).
        "d3-bj": {
            "value": "d3-bj",
            "s6": 1.0, "s8": 0.5883, "a1": 0.5719, "a2": 3.6017,
        },
        # D4, mio set without three-body term (appendix H).
        "d4": {
            "value": "d4",
            "s6": 1.0, "s8": 1.1948145, "s9": 0.0,
            "a1": 0.6074567, "a2": 4.9336133,
        },
    },
    "deMonNano": {
        "none": None,
        "model-1": "model-1",
        "model-2": "model-2",
    },
}


for software, dispersions in DISPERSIONS.items():
    for name, dispersion in dispersions.items():
        method_args = {"basis": BASIS[software], **SCC}
        if dispersion is not None:
            method_args["dispersion"] = dispersion

        calc = AMAC(
            software=software,
            workdir=f".run/{software}/dispersion-{name}",
            label=f"dimer-{name}",
        )
        calc.handler_register("lowest-energy")
        calc.parameters_register(
            method="dftb-2",
            method_args=method_args,
            module="single-point",
            module_args={},
        )
        calc.run(dimer)
        print(f"{software:10s} {name:8s} {calc.instance.res.product}")
