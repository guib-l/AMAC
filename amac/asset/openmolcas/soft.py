from fractions import Fraction
from math import gcd, lcm
from pathlib import Path

import amac.asset.openmolcas.handler  # noqa: F401
from amac.asset.openmolcas.parser import (
    read_frequencies,
    read_geometry,
    read_output,
    to_input,
    xyz_block,
)
from amac.asset.solvation import SolvationSettings, solvation_settings
from amac.engine.software import Software
from amac.engine.timeout import time_limited

# The project name is the input file name without its suffix.
PROJECT = "openmolcas"
SCRATCH = "scratch"
# Program blocks of the methods, in execution order.
METHOD_BLOCKS = ("scf", "rasscf", "caspt2", "mbpt2", "chcc", "cht3")


def flag(enabled: bool) -> bool | None:
    """Keyword without value: written when true, omitted otherwise."""
    return True if enabled else None


def frozen_core(enabled: bool) -> int | None:
    """MBPT2 freezes the core by default: ``Frozen = 0`` turns it off."""
    return None if enabled else 0


def scf_thresholds(energy: float) -> str:
    """SCF ``THREsholds``: energy threshold, other defaults of the manual."""
    return f"{energy:.2E} 1.0E-04 1.5E-04 1.0E-03"


def integer_weights(weights: list[float]) -> list[int]:
    """RASSCF state-average weights are integers: smallest proportional ones.

    Raises:
        ValueError: A weight is not positive.
    """
    if any(weight <= 0 for weight in weights):
        raise ValueError(f"OpenMolcas asset: state weights must be positive, got {weights}")
    fractions = [Fraction(weight).limit_denominator(1000) for weight in weights]
    scale = lcm(*(fraction.denominator for fraction in fractions))
    values = [int(fraction * scale) for fraction in fractions]
    divisor = gcd(*values)
    return [value // divisor for value in values]


def ciroot(roots: int, weights: list[float] | None) -> str | None:
    """RASSCF ``CIRoot`` value: ``n n 1`` for equal weights, the full form else.

    Raises:
        ValueError: The number of weights differs from the number of roots.
    """
    if weights is not None and len(weights) != roots:
        raise ValueError(f"OpenMolcas asset: {len(weights)} weights for {roots} roots")
    values = integer_weights(weights) if weights else [1] * roots
    if roots == 1:
        return None
    if len(set(values)) == 1:
        return f"{roots} {roots} 1"
    return "\n".join(
        [f"{roots} {roots}", " ".join(str(i) for i in range(1, roots + 1)), " ".join(map(str, values))]
    )


def active_space(active: dict, nelec: int, multiplicity: int) -> dict:
    """RASSCF orbital spaces and state from the catalog active space.

    ``Inactive`` is deduced from the number of electrons, so ``Charge`` is
    not given to RASSCF (the manual forbids it together with ``Nactel``).

    Raises:
        ValueError: Active space incompatible with the electrons or the spin.
    """
    norb, nact = active["orbitals"], active["electrons"]
    unpaired = multiplicity - 1
    if nact > 2 * norb or nact > nelec or (nelec - nact) % 2:
        raise ValueError(
            f"OpenMolcas asset: CAS({nact},{norb}) incompatible with {nelec} electrons"
        )
    if unpaired > min(nact, 2 * norb - nact) or (nact - unpaired) % 2:
        raise ValueError(
            f"OpenMolcas asset: multiplicity {multiplicity} impossible in CAS({nact},{norb})"
        )
    block = {
        "Spin": multiplicity,
        "Nactel": f"{nact} 0 0",
        "Inactive": (nelec - nact) // 2,
        "Ras2": norb,
    }
    root = ciroot(active.get("roots", 1), active.get("weights"))
    if root is not None:
        block["CIRoot"] = root
    return block


def core_orbitals(numbers) -> int:
    """Number of core orbitals: the previous noble-gas shell of each atom."""
    shells = ((2, 0), (10, 1), (18, 5), (36, 9), (54, 18), (86, 27))
    total = 0
    for number in numbers:
        total += next((core for limit, core in shells if number <= limit), 43)
    return total


def roots_list(roots: int) -> str:
    """``N 1 2 ... N``: every CASSCF root, for the CASPT2 state keywords."""
    return f"{roots} " + " ".join(str(root) for root in range(1, roots + 1))


def perturbation(method: str, pt2: dict, block: dict, roots: int) -> dict:
    """&CASPT2 block of CASPT2 or of the CAS-based NEVPT2.

    ``single`` treats each root on its own (``NOMUlt``); ``ms``, ``xms`` and
    ``rms`` couple all the roots.

    Raises:
        ValueError: Imaginary and real level shifts together.
    """
    if "IMAGinary" in block and "SHIFt" in block:
        raise ValueError("OpenMolcas asset: give either an imaginary or a real shift, not both")
    block = dict(block)
    if method == "nevpt2":
        block[pt2["variant"]] = True
    multistate = pt2.get("multistate", "single")
    if multistate != "single":
        block[multistate] = roots_list(roots)
    elif roots > 1:
        block["MULTistate"] = roots_list(roots)
        block["NOMUlt"] = True
    return block


def loop(body: list[str], iterations: int | None) -> list[str]:
    """``>> DO WHILE`` loop around ``body``, capped by ``MOLCAS_MAXITER``.

    GATEWAY stays outside the loop: it recreates the RUNFILE.
    """
    head = [] if iterations is None else [f">> EXPORT MOLCAS_MAXITER={iterations}"]
    return [*head, ">> DO WHILE", *body, ">> ENDDO"]


def analytic_hessian(method: str, blocks: dict, roots: int) -> bool:
    """McKinley analytic Hessian: closed-shell HF or single-root CASSCF.

    Not used with KS-DFT, UHF or RICD (not covered by McKinley); the other
    methods get a numerical Hessian.
    """
    if blocks["gateway"].get("RICD"):
        return False
    if method == "scf":
        scf = blocks["scf"]
        return "KSDFT" not in scf and not scf.get("UHF")
    return method == "casscf" and roots == 1


def reaction_field(solv: SolvationSettings) -> dict:
    """GATEWAY ``RF-Input`` block: conductor-like PCM (C-PCM).

    Raises:
        ValueError: Model other than cpcm.
    """
    if solv.model != "cpcm":
        raise ValueError(f"OpenMolcas asset: solvation model {solv.model} unavailable, use cpcm")
    block = {"PCM-model": True, "Conductor version": True}
    if solv.solvent is not None:
        block["Solvent"] = solv.solvent
    else:
        block["Dielectric constant"] = solv.epsilon
    return block


class software_openmolcas(Software):
    name = "openmolcas"
    alias = ("OpenMolcas", "molcas")
    requires_executable = True
    transforms = {"flag": flag, "frozen_core": frozen_core, "scf_thresholds": scf_thresholds}

    input_file = f"{PROJECT}.input"
    output_file = "output-openmolcas.log"

    @time_limited
    def collect(self, instance):
        params = super().collect(instance)
        image = instance.props.image
        system = params.pop("system")
        method = params.pop("method")
        task = params.pop("task", "single-point")
        active = params.pop("active", None)
        solvation = params.pop("solvation", None)
        scf = params.pop("scf", {})

        charge = int(round(system["charge"]))
        multiplicity = system["multiplicity"]
        nelec = int(image.numbers.sum()) - charge
        if nelec < 0 or (nelec - multiplicity + 1) % 2:
            raise ValueError(
                f"OpenMolcas asset: multiplicity {multiplicity} impossible with {nelec} electrons"
            )

        # No symmetry and no reorientation: atoms keep the order and frame of the image.
        gateway = {"Coord": xyz_block(image), "Group": "NoSym", "NoMove": True}
        gateway.update(params.pop("gateway", {}))
        if solvation is not None:
            gateway["RF-Input"] = reaction_field(solvation_settings(solvation))
        blocks = {"gateway": gateway, "seward": params.pop("seward", {})}

        if method in ("casscf", "caspt2", "nevpt2"):
            # Spin-adapted CASSCF: "reference" is ignored. A closed-shell SCF
            # gives the start orbitals; with an odd number of electrons,
            # GUESSORB (run by SEWARD) gives them.
            if nelec % 2 == 0:
                blocks["scf"] = {"Charge": charge, **scf}
            blocks["rasscf"] = active_space(active, nelec, multiplicity)
            if method != "casscf":
                blocks["caspt2"] = perturbation(
                    method, params.pop("pt2", {}), params.pop("caspt2", {}), active.get("roots", 1)
                )
        else:
            reference = system.get("reference") or (
                "restricted" if multiplicity == 1 else "unrestricted"
            )
            if reference == "restricted" and multiplicity > 1:
                raise ValueError("OpenMolcas asset: a restricted reference needs multiplicity 1")
            if method != "scf" and reference != "restricted":
                raise ValueError(f"OpenMolcas asset: {method} is closed-shell (restricted) only")
            spin = {"UHF": True, "Spin": multiplicity} if reference == "unrestricted" else {}
            blocks["scf"] = {"Charge": charge, **spin, **scf}
            if method == "mp2":
                blocks["mbpt2"] = params.pop("mbpt2", {})
            if method in ("ccsd", "ccsd(t)"):
                # CHCC/CHT3 need Cholesky vectors and freeze nothing by default:
                # the core is frozen unless "frozen-core" is false.
                frozen = params.pop("correlation", {}).get("frozen-core", True)
                ncore = core_orbitals(image.numbers) if frozen else 0
                blocks["seward"]["Cholesky"] = True
                blocks["chcc"] = {"FROZen": ncore, **params.pop("chcc", {})}
                if method == "ccsd(t)":
                    blocks["cht3"] = {"FROZen": ncore}

        if self.program.process == "mpi":
            raise NotImplementedError("OpenMolcas asset: MPI runs are not supported yet")

        # Program blocks of the method, in execution order.
        body = ["seward", *(name for name in METHOD_BLOCKS if name in blocks)]
        if task == "single-point":
            sequence = ["gateway", *body]
            if "forces" in instance.props.handler:
                blocks["alaska"] = {}
                sequence.append("alaska")
        elif task == "optimization":
            blocks["slapaf"] = params.pop("slapaf", {})
            sequence = ["gateway", *loop(body + ["slapaf"], blocks["slapaf"].get("ITERations"))]
        elif analytic_hessian(method, blocks, (active or {}).get("roots", 1)):
            blocks["mckinley"] = {}
            sequence = ["gateway", *body, "mckinley"]
        else:
            # Finite differences of gradients: one loop iteration per
            # displacement (2 per Cartesian coordinate), plus margin.
            blocks["slapaf"] = {"NUMErical": True}
            sequence = ["gateway", *loop(body + ["slapaf"], 6 * len(image) + 10)]

        blocks.update(params)
        blocks["sequence"] = sequence
        # Read back by calculate() to select the final energy and the files.
        self.method = method
        self.task = task
        return blocks

    @time_limited
    def prepare(self, instance):
        workdir = Path(instance.ctx.workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / self.input_file).write_text(to_input(self.parameters))

    @time_limited
    def calculate(self, instance):
        workdir = Path(instance.ctx.workdir)
        image = instance.props.image
        # Explicit, emptied scratch: never restart from an old RUNFILE.
        self.execute_program(
            workdir,
            "-new",
            f"WorkDir={workdir / SCRATCH}",
            self.input_file,
            output=self.output_file,
        )
        variant = "PC" if "PC-Nevpt2" in self.parameters.get("caspt2", {}) else "SC"
        results = read_output(workdir / self.output_file, image, self.method, variant)
        if self.task == "optimization":
            results["output_geometry"] = read_geometry(workdir / f"{PROJECT}.geo.molden", image)
        results["frequencies"] = None
        if self.task == "frequencies":
            results["frequencies"] = read_frequencies(workdir / f"{PROJECT}.freq.molden")
        return results
