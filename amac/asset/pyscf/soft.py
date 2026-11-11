from pathlib import Path

from ase import Atoms

import amac.asset.pyscf.handler  # noqa: F401
from amac.engine.software import Software
from amac.engine.timeout import time_limited


def build_mol(image: Atoms, params: dict, output: Path):
    """Build the PySCF molecule (Angstrom)."""
    from pyscf import gto

    mol = params["mol"]
    basis = mol["basis"]
    return gto.M(
        atom=[(symbol, tuple(xyz)) for symbol, xyz in zip(image.get_chemical_symbols(), image.positions)],
        unit="Angstrom",
        basis=basis,
        # def2 bases carry ECPs beyond Kr: PySCF needs them explicitly.
        ecp=basis if basis.lower().startswith("def2") else None,
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

        forces = None
        if "forces" in instance.props.handler:
            forces = -solver.nuc_grad_method().kernel()
        final = image.copy()
        final.positions = mol.atom_coords(unit="Angstrom")
        return {
            "errors": [],
            "energy": {"energy": float(energy), "scf_energy": float(mf.e_tot)},
            "forces": forces,
            "charges": list(mf.mulliken_pop(verbose=0)[1]),
            "dipole": list(mf.dip_moment(unit="AU", verbose=0)),
            "input_geometry": image.copy(),
            "output_geometry": final,
        }
