"""DFTB-2 single-point timing benchmark on (H2O)n water aggregates.

Every aggregate of the size grid (1, 2, 4, ..., 100 water molecules) is
built once — waters on a cubic lattice, each with an independent random
rotation to break the symmetry — and run as a DFTB-2 single point with
dftb+ and deMonNano, each serial (process_unit=1) and parallel
(process_unit=4). The wall time of each run is recorded and plotted
against the number of atoms on a log-log figure.
Run failures are reported per run and the script keeps going.

Run the full size grid from the AMAC directory:

    python examples/timing_water.py

or limit the grid to the aggregates with n waters or fewer:

    python examples/timing_water.py 4
"""

import sys
from pathlib import Path

# The venv also holds an older, installed copy of amac (without its
# catalog/ directory); prefer the local package next to this examples/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from ase import Atoms

import amac
from amac.amac import AMAC


SIZES = (1, 2, 4, 8, 16, 32, 64, )#100, 200, 400)

SOFTWARES = ("dftb+", "deMonNano")

UNITS = (1,)

BASIS = {
    "deMonNano": {"directory": "~/Téléchargements/deMonNano/basis", "ptype": "BIO"},
    "dftb+": {"directory": "~/Téléchargements/parameters_dftb/mio-1.1.0/skfiles"},
}

# Reference water geometry: O at the origin, OH = 0.9572 A, H-O-H = 104.52 deg.
OH = 0.9572
HOH_ANGLE = np.deg2rad(104.52)
LATTICE_SPACING = 3.5

STYLES = (
    ("tab:blue", "o", "-"),
    ("tab:orange", "s", "--"),
    ("tab:green", "^", "-."),
    ("tab:red", "D", ":"),
)


def reference_water() -> np.ndarray:
    """Return the (3, 3) water coordinates: O at the origin, H on the x/y axis."""
    half = HOH_ANGLE / 2
    return np.array(
        [
            [0.0, 0.0, 0.0],
            [OH * np.cos(half), OH * np.sin(half), 0.0],
            [OH * np.cos(half), -OH * np.sin(half), 0.0],
        ]
    )


def quaternion_matrix(q: np.ndarray) -> np.ndarray:
    """Return the 3x3 rotation matrix of the unit quaternion (x, y, z, w)."""
    x, y, z, w = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def random_rotation(rng: np.random.Generator) -> np.ndarray:
    """Return the rotation matrix of a random unit quaternion."""
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    return quaternion_matrix(q)


def build_water_cluster(n_waters: int, rng: np.random.Generator) -> Atoms:
    """Build a (H2O)n aggregate with an independent random rotation per water.

    The waters sit on the first ``n_waters`` sites (lexicographic (i, j, k)
    order) of a cubic lattice with 3.5 A spacing, translated so the
    occupied sites are centered on the origin.
    """
    side = int(np.ceil(n_waters ** (1.0 / 3.0)))
    sites = np.array(
        [
            [i, j, k]
            for i in range(side)
            for j in range(side)
            for k in range(side)
        ][:n_waters],
        dtype=float,
    ) * LATTICE_SPACING
    sites -= sites.mean(axis=0)

    reference = reference_water()
    positions = np.vstack(
        [reference @ random_rotation(rng).T + site for site in sites]
    )
    return Atoms(symbols=["O", "H", "H"] * n_waters, positions=positions)


def wall_time(software: str, units: int, n: int, atoms: Atoms) -> float | None:
    """Run the DFTB-2 single point of ``atoms`` and return its wall time (s).

    Returns None (and prints the failure) when the run raises.
    """
    calc = AMAC(
        software=software,
        workdir=f".run/timing/{software}/{units}/{n:03d}",
        label=f"timing-{software}-{n:03d}-{units}",
        process_unit=units,
    )
    calc.handler_register("lowest-energy","forces")
    calc.parameters_register(
        method="dftb-2",
        method_args={"basis": BASIS[software], "scc-max": 999, "scc-tol": 1e-5},
        module="single-point",
        module_args={},
    )
    try:
        calc.run(atoms)
    except Exception as error:
        print(f"{software} n={n} units={units}: failed ({error})")
        return None
    return float(calc.instance.duree.duree)


def print_summary(sizes: list[int], times: dict[tuple[str, int], dict[int, float | None]]) -> None:
    """Print the wall-time table and the per-column success counts."""
    columns = [(software, units) for software in SOFTWARES for units in UNITS]
    print(f"{'n':>4s} {'atoms':>6s}" + "".join(f" {software} {units}t" for software, units in columns))
    for n in sizes:
        row = f"{n:4d} {3 * n:6d}"
        for software, units in columns:
            value = times[(software, units)][n]
            row += f" {value:13.3f}" if value is not None else f" {'-':>13s}"
        print(row)
    for software, units in columns:
        values = times[(software, units)]
        succeeded = sum(1 for value in values.values() if value is not None)
        print(f"{software} units={units}: {succeeded}/{len(sizes)} succeeded")


def make_figure(path: Path, times: dict[tuple[str, int], dict[int, float | None]]) -> None:
    """Save the log-log wall time vs number of atoms, one curve per column."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(6, 5))
    columns = [(software, units) for software in SOFTWARES for units in UNITS]
    for (software, units), (color, marker, line) in zip(columns, STYLES):
        values = times[(software, units)]
        ns = sorted(n for n in values if values[n] is not None)
        if not ns:
            continue
        plural = "s" if units > 1 else ""
        axis.plot(
            [3 * n for n in ns],
            [values[n] for n in ns],
            marker=marker,
            linestyle=line,
            color=color,
            label=f"{software} ({units} thread{plural})",
        )
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("Number of atoms")
    axis.set_ylabel("Wall time (s)")
    axis.set_title(
        "DFTB-2 single point — (H2O)n: dftb+ vs deMonNano (serial)",
        fontsize=10,
    )
    axis.grid(True, which="both")
    axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


max_n = int(sys.argv[1]) if len(sys.argv) > 1 else None
sizes = [n for n in SIZES if max_n is None or n <= max_n]

amac.configure_from_file("config-amac.json")

times = {(software, units): {} for software in SOFTWARES for units in UNITS}
rng = np.random.default_rng(42)
for n in sizes:
    atoms = build_water_cluster(n, rng)
    for software in SOFTWARES:
        for units in UNITS:
            times[(software, units)][n] = wall_time(software, units, n, atoms)

print_summary(sizes, times)

figure = Path("figures/timing-water-h2o.png")
make_figure(figure, times)
print(f"Figure saved to {figure}")
