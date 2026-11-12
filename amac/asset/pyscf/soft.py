from pathlib import Path

import numpy as np
from ase import Atoms

import amac.asset.pyscf.handler  # noqa: F401
from amac.engine.software import Software
from amac.engine.timeout import time_limited


def build_mol(image: Atoms, params: dict, output: Path):
    """Build the PySCF molecule (Angstrom)."""
    from pyscf import gto

    mol = params["mol"]
    basis = mol["basis"]
    # def2 bases carry ECPs beyond Kr (Z > 36): PySCF needs them explicitly.
    heavy = any(number > 36 for number in image.numbers)
    return gto.M(
        atom=[(symbol, tuple(xyz)) for symbol, xyz in zip(image.get_chemical_symbols(), image.positions)],
        unit="Angstrom",
        basis=basis,
        ecp=basis if heavy and basis.lower().startswith("def2") else None,
        charge=int(round(mol["charge"])),
        spin=mol["multiplicity"] - 1,
        output=str(output),
        verbose=4,
    )


def mean_field(mol, params: dict):
    """Build the HF or KS object with its SCF settings."""
    from pyscf import dft, scf

    settings = params.get("scf", {})
    xc = params.get("dft", {})
    ref = settings.get("reference") or ("R" if mol.spin == 0 else "U")
    if "xc" in xc:
        mf = getattr(dft, f"{ref}KS")(mol)
        mf.xc = xc["xc"]
        if "grids_level" in xc:
            mf.grids.level = xc["grids_level"]
        if "disp" in xc:
            mf.disp = xc["disp"]
    else:
        mf = getattr(scf, f"{ref}HF")(mol)
    for key in ("conv_tol", "max_cycle", "level_shift"):
        if key in settings:
            setattr(mf, key, settings[key])
    if settings.get("density_fit"):
        mf = mf.density_fit(auxbasis=settings.get("auxbasis"))
    return mf


def solve(mol, params: dict):
    """Run the method; return (mean field, solver giving the energy, energy)."""
    from pyscf import cc, mcscf, mp
    from pyscf.data.elements import chemcore

    mf = mean_field(mol, params)
    mf.run()
    post = params.get("post", {})
    method = post.get("method")
    frozen = chemcore(mol) if post.get("frozen_core") else None
    if method is None:
        return mf, mf, mf.e_tot
    if method == "mp2":
        solver = mp.MP2(mf, frozen=frozen).run()
        return mf, solver, solver.e_tot
    if method in ("ccsd", "ccsd(t)"):
        solver = cc.CCSD(mf, frozen=frozen)
        for key in ("conv_tol", "max_cycle"):
            if key in post:
                setattr(solver, key, post[key])
        solver.run()
        energy = solver.e_tot + (solver.ccsd_t() if method == "ccsd(t)" else 0.0)
        return mf, solver, energy
    if method == "casscf":
        solver = mcscf.CASSCF(mf, post["ncas"], post["nelecas"])
        nroots = post.get("nroots", 1)
        if nroots > 1:
            solver.state_average_(post.get("weights") or [1.0 / nroots] * nroots)
        solver.run()
        return mf, solver, solver.e_tot
    raise ValueError(f"unknown post-HF method: {method!r}")


def frequencies(mf, mol) -> np.ndarray:
    """Harmonic frequencies (cm^-1, imaginary ones negative), shape (n, 2).

    The second column (IR intensity) is NaN: PySCF core does not compute it.
    """
    from pyscf.hessian import thermo

    wavenumbers = thermo.harmonic_analysis(mol, mf.Hessian().kernel())["freq_wavenumber"]
    wavenumbers = np.asarray(wavenumbers)
    # Imaginary modes come back as complex numbers.
    values = np.where(np.abs(wavenumbers.imag) > 0, -np.abs(wavenumbers.imag), wavenumbers.real)
    return np.column_stack([values, np.full(len(values), np.nan)])


def excited_states(mf, settings: dict) -> dict:
    """Linear-response TDHF/TDDFT states: ``w`` (eV) and ``oscillator``."""
    from pyscf import tdscf
    from pyscf.data.nist import HARTREE2EV

    symmetry = settings.get("symmetry", "singlet")
    singlets = {"singlet": [True], "triplet": [False], "both": [True, False]}[symmetry]
    states = {}
    for singlet in singlets:
        td = tdscf.TDDFT(mf)
        td.nstates = settings.get("nstates", 3)
        td.singlet = singlet
        td.kernel()
        # Triplets have no oscillator strength from a closed-shell ground state.
        oscillator = td.oscillator_strength() if singlet else np.zeros(len(td.e))
        states["singlet" if singlet else "triplet"] = {
            f"state_{index}": {"w": float(energy * HARTREE2EV), "oscillator": float(strength)}
            for index, (energy, strength) in enumerate(zip(td.e, oscillator))
        }
    return states


class software_pyscf(Software):
    name = "pyscf"
    alias = ("PySCF",)
    requires_executable = False

    output_file = "output-pyscf.log"

    @time_limited
    def calculate(self, instance):
        from pyscf import lib

        lib.num_threads(self.program.process_unit)
        workdir = Path(instance.ctx.workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        params = self.parameters
        image = instance.props.image
        mol = build_mol(image, params, workdir / self.output_file)

        if params.get("run") == "optimization":
            # Needs the "geometric" package.
            from pyscf.geomopt import geometric_solver

            _, solver, _ = solve(mol, params)
            mol = geometric_solver.optimize(solver, **params.get("opt", {}))
        mf, solver, energy = solve(mol, params)
        run = params.get("run")
        if run in ("frequencies", "excited-states") and solver is not mf:
            raise ValueError(f"PySCF asset: {run} is available for HF and DFT only")

        forces = None
        if "forces" in instance.props.handler:
            forces = -solver.nuc_grad_method().kernel()
        final = image.copy()
        final.positions = mol.atom_coords(unit="Angstrom")
        return {
            "errors": [],
            "energy": {"energy": float(energy), "scf_energy": float(mf.e_tot)},
            "forces": forces,
            "charges": mf.mulliken_pop(verbose=0)[1].tolist(),
            "dipole": mf.dip_moment(unit="AU", verbose=0).tolist(),
            "frequencies": frequencies(mf, mol) if run == "frequencies" else None,
            "excited-states": excited_states(mf, params.get("td", {})) if run == "excited-states" else None,
            "input_geometry": image.copy(),
            "output_geometry": final,
        }
