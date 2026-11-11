from ase.build import molecule

import amac
from amac.amac import AMAC
from amac.asset import Software

water = molecule("H2O")


amac.configure_from_file("config-amac.json")

calc = AMAC(
    software="deMonNano", process_unit=1, workdir=".run/", label="water", process="inprocess"
)

calc.handler_register("lowest-energy")

calc.parameters_register(
    method="dftb-2",
    method_args={
        "basis": {
            # "directory":"/home/vboxuser/Téléchargements/mio-1-1",
            "directory": "/home/vboxuser/Téléchargements/deMonNano/basis",
            "ptype": "BIO",
        },
        "scc-max": 999,
        "scc-tol": 1e-5,
        "filling": 50,
    },
    module="single-point",
    module_args={},
)


calc.run(water)
print(calc.instance)

calc.instance.pretty_print()

# calc.new_instance()
# print(calc.instance)


soft = Software.create("deMonNano", process_unit=2)
soft.pretty_print()
