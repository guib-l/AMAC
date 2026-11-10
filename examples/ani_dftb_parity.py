"""DFTB-1/2/3 single-point parity of dftb+ and deMonNano on the
1000-molecule ANI-1 sample.

Every molecule is run with DFTB-1, DFTB-2 and DFTB-3 using the same
canonical description in both programs; the two parity figures compare
deMonNano against dftb+ and against the ANI-1 reference energies.
Run failures are reported per run and the script keeps going.

Run the full set (1000 molecules) from the AMAC directory:

    python examples/ani_dftb_parity.py

or a quick subset of the first molecules:

    python examples/ani_dftb_parity.py 5
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


NMAX = 1999

XYZ_PATH = Path("../ANI-1/xyz/ani1_xyz_01.xyz")

SOFTWARES = ("deMonNano","dftb+")
METHODS = ("dftb-2", "dftb-3")

BASIS = {
    "deMonNano": {
        "directory": "~/Téléchargements/deMonNano/basis",
    },
    "dftb+": {
        "directory": "~/Téléchargements/parameters_dftb/mio-1.1.0/skfiles",
    },
}

SCC = {
    "scc-max": 999,
    #"filling": 50,
}

# Hubbard derivatives of the 3OB mio-1-1 parameter set (a.u.).
HUBBARD_DERIVS = {"H": -0.1857, "C": -0.1492, "N": -0.1535, "O": -0.1575}


def basis_args(software: str, method: str) -> dict[str, str]:
    """Return the basis attributes for one software/method combination."""
    basis = dict(BASIS[software])
    if software == "deMonNano":
        # DFTB-1 uses the NSC parameters, DFTB-2/3 the BIO ones.
        basis["ptype"] = "NSC" if method == "dftb-1" else "BIO"
    return basis


def method_args(method: str) -> dict[str, object]:
    """Return the method-specific arguments, excluding the basis."""
    match method:
        case "dftb-1":
            return {}
        case "dftb-2":
            return dict(SCC)
        case "dftb-3":
            return {
                **SCC,
                "h-correction": {"value": "damping", "exponent": 4.0},
                "hubbard-derivs": HUBBARD_DERIVS,
            }
    raise ValueError(f"unknown method: {method}")


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


def pair_energies(x: dict[int, float], y: dict[int, float]) -> tuple[list[float], list[float]]:
    """Return the (x, y) values for the molecule indices both runs succeeded on."""
    idxs = sorted(set(x) & set(y))
    return [x[i] for i in idxs], [y[i] for i in idxs]


def make_figure(
    path: Path,
    suptitle: str,
    x_label: str,
    data: dict[str, tuple[list[float], list[float]]],
) -> None:
    """Save one 1x3 parity figure; subplots without points stay blank."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(METHODS), figsize=(5*len(METHODS), 5))
    for axis, method in zip(axes, METHODS):
        axis.set_title(method)
        axis.set_xlabel(x_label)
        axis.set_ylabel("deMonNano (eV)")
        xs, ys = data[method]
        if not xs:
            continue
        axis.plot(xs, ys, marker="o", linestyle="none", markersize=3)
        a,b = min(xs)*1.05,max(xs)*0.95
        c,d = min(ys)*1.05,max(ys)*0.95
        axis.plot([a,b], [c,d], color="red", linewidth=1)
    fig.suptitle(suptitle)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
molecules = load_molecules(XYZ_PATH)
if limit is not None:
    molecules = molecules[:limit]

references = {idx: energy_eV for idx, (_, energy_eV) in enumerate(molecules)}

amac.configure_from_file("config-amac.json")

energies = {software: {method: {} for method in METHODS} for software in SOFTWARES}

for idx, (atoms, _) in enumerate(molecules[:NMAX]):
    for software in SOFTWARES:
        for method in METHODS:
            calc = AMAC(
                software=software,
                workdir=f".run/ani-dftb/{software}/{method}/{idx:04d}",
                label=f"ani-{idx:04d}",
            )
            calc.handler_register("lowest-energy")
            margs = method_args(method)
            if method=="dftb-3":
                keys = list(set(atoms.symbols))
                margs['hubbard-derivs'] = {k: HUBBARD_DERIVS[k] for k in keys if k in HUBBARD_DERIVS}
            calc.parameters_register(
                method=method,
                method_args={"basis": basis_args(software, method), **margs},
                module="single-point",
                module_args={},
                software_args={
                    "deMonNano": {"DEMON_PARAMETERS.ACTIVE.DFTB.FHUB": True},
                },
            )
            try:
                calc.run(atoms)
            except (NotImplementedError, KeyError) as error:
                print(f"{software} {method} molecule {idx}: not available ({error})")
                continue
            except Exception as error:
                print(f"{software} {method} molecule {idx}: failed ({error})")
                continue
            energies[software][method][idx] = float(calc.instance.res.product["lowest-energy"])

for software in SOFTWARES:
    for method in METHODS:
        print(f"{software} {method}: {len(energies[software][method])}/{len(molecules)} succeeded")

make_figure(
    Path("figures/ani-dftb-parity-demonnano-dftbplus.png"),
    "deMonNano vs DFTB+ (ANI-1)",
    "dftb+ (eV)",
    {
        method: pair_energies(energies["dftb+"][method], energies["deMonNano"][method])
        for method in METHODS
    },
)

make_figure(
    Path("figures/ani-dftb-parity-demonnano-ani1.png"),
    "deMonNano vs ANI-1 reference (ANI-1)",
    "ANI-1 reference (eV)",
    {
        method: (
            [references[idx] for idx in sorted(energies["deMonNano"][method])],
            [energies["deMonNano"][method][idx] for idx in sorted(energies["deMonNano"][method])],
        )
        for method in METHODS
    },
)
