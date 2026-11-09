"""DFTB-2 single-point energies with dispersion corrections on the
1000-molecule ANI-1 sample, run with DFTB+ and deMonNano.

Every molecule is run in DFTB-2 with each dispersion solution (DFTB+:
no correction, Lennard-Jones UFF, D3-BJ, D4; deMonNano: model-1 and
model-2); one bar chart compares the MAE of every solution against the
ANI-1 reference energies. DFTB absolute energies sit on a different
scale than the ANI-1 DFT reference, so the MAE values are dominated by
that offset; the chart compares the dispersion solutions relative to
each other. Run failures are reported per run and the script keeps
going.

Run the full set (1000 molecules) from the AMAC directory:

    python examples/dispersion.py

or a quick subset of the first molecules:

    python examples/dispersion.py 20
"""

import sys
from pathlib import Path

# The venv also holds an older, installed copy of amac (without its
# catalog/ directory); prefer the local package next to this examples/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from ase import Atoms

import amac
from amac.amac import AMAC

NMAX = 100

XYZ_PATH = Path("..") / "ANI-1" / "xyz" / "ani1_xyz_01.xyz"

BASIS = {
    "dftb+": {
        "directory": "~/Téléchargements/parameters_dftb/mio-1.1.0/skfiles",
    },
    "deMonNano": {
        "directory": "~/Téléchargements/deMonNano/basis",
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
            "s6": 1.0,
            "s8": 0.5883,
            "a1": 0.5719,
            "a2": 3.6017,
        },
        # D4, mio set without three-body term (appendix H).
        "d4": {
            "value": "d4",
            "s6": 1.0,
            "s8": 1.1948145,
            "s9": 0.0,
            "a1": 0.6074567,
            "a2": 4.9336133,
        },
    },
    "deMonNano": {
        # No "none" entry: deMonNano cannot switch its dispersion off
        # through AMAC (default is DISP=1 = model-1), so a "none" entry
        # would be a misleading duplicate of model-1.
        "model-1": "model-1",
        "model-2": "model-2",
    },
}

FIGURE_PATH = Path("figures/dispersion-mae-ani1.png")
COLORS = {"dftb+": "blue", "deMonNano": "orange"}


def load_molecules(path: Path) -> list[tuple[Atoms, float]]:
    """Parse the ANI-1 xyz file into (atoms, reference_energy_eV) pairs.

    Each frame is an atom count, a comment line whose first float is the
    ANI-1 reference energy in eV, and one ``Sym x y z`` line per atom.
    """
    molecules = []
    with path.open() as file:
        lines = file.readlines()
    idx = 0
    while idx < len(lines):
        count = int(lines[idx].split()[0])
        energy_eV = float(lines[idx + 1].split()[0])
        symbols, positions = [], []
        for line in lines[idx + 2 : idx + 2 + count]:
            symbol, x, y, z = line.split()
            symbols.append(symbol)
            positions.append([float(x), float(y), float(z)])
        atoms = Atoms(symbols=symbols, positions=positions)
        molecules.append((atoms, energy_eV))
        idx += 2 + count
    return molecules


def mean_absolute_error(energy_by_idx: dict[int, float], references: dict[int, float]) -> float:
    """Mean absolute error (eV) of the successful runs against the reference."""
    errors = [abs(energy_by_idx[idx] - references[idx]) for idx in energy_by_idx]
    return sum(errors) / len(errors)


def make_figure(path: Path, title: str, data: list[tuple[str, str, float]]) -> None:
    """Save the bar chart of the MAE of every dispersion solution."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(9, 5))
    for position, (software, name, mae_value) in enumerate(data):
        axis.bar(position, mae_value, color=COLORS[software])
        axis.annotate(
            f"{mae_value:.2f}",
            (position, mae_value),
            textcoords="offset points",
            xytext=(0, 3),
            ha="center",
        )
    axis.set_xticks(range(len(data)))
    axis.set_xticklabels([f"{software} {name}" for software, name, _ in data])
    axis.set_ylabel("MAE (eV)")
    axis.set_title(title)
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in COLORS.values()]
    axis.legend(legend_handles, list(COLORS), title="software")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
molecules = load_molecules(XYZ_PATH)
if limit is not None:
    molecules = molecules[:limit]

references = {idx: energy_eV for idx, (_, energy_eV) in enumerate(molecules)}

amac.configure_from_file("config-amac.json")

energies = {
    software: {name: {} for name in dispersions} for software, dispersions in DISPERSIONS.items()
}

for idx, (atoms, _) in enumerate(molecules[:NMAX]):
    for software, dispersions in DISPERSIONS.items():
        for name, dispersion in dispersions.items():
            method_args = {"basis": dict(BASIS[software]), **SCC}
            if dispersion is not None:
                method_args["dispersion"] = dispersion
            calc = AMAC(
                software=software,
                workdir=f".run/dispersion/{software}/{name}/{idx:04d}",
                label=f"ani-{idx:04d}",
            )
            calc.handler_register("lowest-energy")
            calc.parameters_register(
                method="dftb-2",
                method_args=method_args,
                module="single-point",
                module_args={},
            )
            try:
                calc.run(atoms)
            except (NotImplementedError, KeyError) as error:
                print(f"{software} {name} molecule {idx}: not available ({error})")
                continue
            except Exception as error:
                print(f"{software} {name} molecule {idx}: failed ({error})")
                continue
            energies[software][name][idx] = float(calc.instance.res.product["lowest-energy"])

total = len(molecules)
solutions = [
    (software, name) for software, dispersions in DISPERSIONS.items() for name in dispersions
]

print(f"{'solution':20s} {'succeeded':>10s} {'MAE (eV)':>12s}")
data = []
no_data = []
for software, name in solutions:
    by_idx = energies[software][name]
    if not by_idx:
        no_data.append((software, name))
        print(f"{software + ' ' + name:20s} {0}/{total:>4d} {'-':>12s}")
        continue
    mae_value = mean_absolute_error(by_idx, references)
    print(f"{software + ' ' + name:20s} {len(by_idx)}/{total:>4d} {mae_value:>12.4f}")
    data.append((software, name, mae_value))

for software, name in no_data:
    print(f"{software} {name}: no successful runs, bar omitted")

make_figure(
    FIGURE_PATH,
    f"DFTB-2 + dispersion vs ANI-1 reference ({total} molecules)",
    data,
)
