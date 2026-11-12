"""DFTB-2 validation on randomly distorted 2-layer graphene supercells.

100 deterministically generated, randomly distorted 4-carbon 2-layer
graphene cells are each run as a single-point DFTB-2 calculation with
dftb+ and deMonNano (k-points 10x10x1, 50 K filling temperature because
graphene is metallic). The total energies and the atomic forces of the
two programs are compared and drawn on one 2x2 parity figure (E, Fx, Fy,
Fz) of deMonNano against dftb+. Run failures are reported per run and
the script keeps going.

Usage:
    python examples/periodic_validation.py [limit]

``limit`` restricts the validation to the first cells of the set (default:
all 100).
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from ase import Atoms

import amac
from amac.amac import AMAC

N_CELLS = 100

SOFTWARES = ("dftb+", "deMonNano")

BASIS = {
    "dftb+": {
        "directory": "~/Téléchargements/parameters_dftb/mio-1.1.0/skfiles",
    },
    "deMonNano": {
        "directory": "/home/pguibourg/Téléchargements/deMonNano/basis",
        "ptype": "BIO",
    },
}

A_REF = 2.46  # in-plane lattice constant of the reference cell (A)
D_LAYER = 3.35  # interlayer distance (A)
VACUUM = 14.5  # vacuum slab beyond the second layer (A)
C_REF = D_LAYER + VACUUM

# Reference AB-stacked 2-layer graphene (4 C): layer 1 (z = 0) at (0, 0)
# and (1/3, 2/3); layer 2 (z = D_LAYER) at (1/3, 2/3) and (2/3, 1/3).
# x and y are fractional coordinates, z is a Cartesian height in A.
FRACTIONS = np.array(
    [
        [0.0, 0.0, 0.0],
        [1 / 3.0, 2 / 3.0, 0.0],
        [1 / 3.0, 2 / 3.0, D_LAYER],
        [2 / 3.0, 1 / 3.0, D_LAYER],
    ]
)


def hex_cell(a: float, c: float) -> np.ndarray:
    """Return the hexagonal cell matrix (A) with in-plane a and c out of plane."""
    return np.array(
        [
            [a, 0.0, 0.0],
            [a / 2.0, a * np.sqrt(3.0) / 2.0, 0.0],
            [0.0, 0.0, c],
        ]
    )


def to_cartesian(fractions: np.ndarray, cell: np.ndarray) -> np.ndarray:
    """Convert fractional x/y (and Cartesian z height) positions to A."""
    positions = fractions[:, :2] @ cell[:2]
    positions[:, 2] = fractions[:, 2]
    return positions


def build_cell(rng: np.random.Generator) -> Atoms:
    """Build one randomly distorted 2-layer graphene cell (4 C, pbc)."""
    a = A_REF * rng.uniform(0.95, 1.05)
    c = C_REF * rng.uniform(0.90, 1.10)
    cell = hex_cell(a, c)
    positions = to_cartesian(FRACTIONS, cell)
    positions += rng.uniform(-0.05, 0.05, size=positions.shape)
    return Atoms(["C"] * 4, positions=positions, cell=cell, pbc=True)


limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
n_cells = min(N_CELLS, limit) if limit is not None else N_CELLS

amac.configure_from_file("config-amac.json")

rng = np.random.default_rng(42)
cells = [build_cell(rng) for _ in range(n_cells)]

data = {software: {} for software in SOFTWARES}
for idx, atoms in enumerate(cells):
    for software in SOFTWARES:
        calc = AMAC(
            software=software,
            workdir=f".run/periodic-val/{software}/{idx:03d}",
            label=f"pval-{idx:03d}",
        )
        calc.handler_register("lowest-energy", "forces")
        calc.parameters_register(
            method="dftb-2",
            method_args={
                "basis": BASIS[software],
                "kpoints": [10, 10, 1],
                "scc-max": 999,
                "scc-tol": 1e-5,
                # "filling": 50,
            },
            module="single-point",
            module_args={},
            software_args={
                "deMonNano": {"DEMON_PARAMETERS.ACTIVE.DFTB.FHUB": True},
            },
        )
        try:
            calc.run(atoms)
        except Exception as error:
            print(f"{software:10s} cell {idx:03d} failed: {error}")
            continue
        data[software][idx] = (
            float(calc.instance.res.product["lowest-energy"]),
            np.asarray(calc.instance.res.product["forces"]),
        )

for software in SOFTWARES:
    print(f"{software:10s}: {len(data[software])}/{n_cells} succeeded")

idxs = sorted(set(data["dftb+"]) & set(data["deMonNano"]))
if len(idxs) < 2:
    sys.exit("Fewer than two cells succeeded with both programs.")

e_dftb = np.array([data["dftb+"][idx][0] for idx in idxs])
e_demon = np.array([data["deMonNano"][idx][0] for idx in idxs])
f_dftb = np.concatenate([data["dftb+"][idx][1] for idx in idxs])
f_demon = np.concatenate([-data["deMonNano"][idx][1] for idx in idxs])

panels = (("E total (Ha)", e_dftb, e_demon), ("F (Ha/Bohr)", f_dftb.ravel(), f_demon.ravel()))

fig, axes = plt.subplots(1, 2, figsize=(10, 5))
for axis, (quantity, xs, ys) in zip(axes.ravel(), panels):
    mae = np.mean(np.abs(ys - xs))
    r = np.corrcoef(xs, ys)[0, 1]
    axis.scatter(xs, ys, marker="o", linestyle="none")
    low = min(xs.min(), ys.min())
    high = max(xs.max(), ys.max())
    axis.plot([low, high], [low, high], "k--", linewidth=1)
    axis.set_xlabel(f"{quantity} DFTB+")
    axis.set_ylabel(f"{quantity} deMonNano")
    axis.set_title(f"r = {r:.4f}")
fig.suptitle("DFTB-2 2-layer graphene — dftb+ vs deMonNano (kpts 10x10x1)")
fig.tight_layout()

output = Path("figures/periodic-validation-parity.png")
output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(output, dpi=150)
plt.close(fig)
print(f"Figure saved to {output}")
