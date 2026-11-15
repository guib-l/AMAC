"""Tests of the DFTB+ asset: helpers, collect() and prepare() (nothing is run)."""

from pathlib import Path

import numpy as np
import pytest
from ase.build import bulk

from amac.asset.dftbplus.soft import (
    cosmo,
    is_periodic,
    kpoints_supercell_folding,
    merge_filling,
    skf_type2filenames,
    supercell_folding_kpoints,
    velocity_verlet,
)
from amac.asset.md import md_settings
from amac.asset.solvation import solvation_settings

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def test_skf_type2filenames(tmp_path):
    """The directory is absolute with a trailing "/"; options are kept."""
    block = skf_type2filenames({"directory": str(tmp_path), "suffix": ".SKF", "lower-case": True})
    assert block["Type2FileNames"] == {
        "Prefix": f"{tmp_path.resolve()}/",
        "Separator": "-",
        "Suffix": ".SKF",
        "LowerCaseTypeName": True,
    }


@pytest.mark.parametrize(
    ("grid", "shifts"),
    [([1, 1, 1], [0.0, 0.0, 0.0]), ([2, 2, 2], [0.5, 0.5, 0.5]), ([4, 3, 1], [0.5, 0.0, 0.0])],
)
def test_kpoints_supercell_folding(grid, shifts):
    """Diagonal folding matrix; 0.5 shift along even directions."""
    values = kpoints_supercell_folding(grid)["SupercellFolding"][""]
    assert values[:9] == [grid[0], 0, 0, 0, grid[1], 0, 0, 0, grid[2]]
    assert values[9:] == shifts


def test_supercell_folding_kpoints():
    """The k-points of a folding matrix, in fractional coordinates."""
    kpoints = supercell_folding_kpoints([2, 0, 0, 0, 1, 0, 0, 0, 1, 0.5, 0.0, 0.0])
    assert np.allclose(kpoints, [[0.25, 0.0, 0.0], [0.75, 0.0, 0.0]])


@pytest.mark.parametrize(
    ("matrix", "message"),
    [
        ([1, 0, 0, 0, 1, 0, 0, 0, 1], "needs 12 numbers"),
        ([1, 1, 0, 0, 1, 0, 0, 0, 1, 0.0, 0.0, 0.0], "not diagonal"),
        ([0, 0, 0, 0, 1, 0, 0, 0, 1, 0.0, 0.0, 0.0], "positive integers"),
        ([1, 0, 0, 0, 1, 0, 0, 0, 1, 0.25, 0.0, 0.0], "shifts must be 0.0 or 0.5"),
    ],
)
def test_supercell_folding_kpoints_invalid(matrix, message):
    """Invalid folding matrices are refused."""
    with pytest.raises(ValueError, match=message):
        supercell_folding_kpoints(matrix)


def test_is_periodic(water):
    """A periodic image needs a cell and a periodic direction."""
    assert is_periodic(bulk("Si"))
    assert not is_periodic(water)
    boxed = water.copy()
    boxed.cell = [10, 10, 10]
    assert not is_periodic(boxed)


def test_merge_filling():
    """The Fermi temperature moves into the chosen smearing scheme."""
    params = {
        "Hamiltonian": {
            "DFTB": {"Filling": {"Fermi": {"Temperature [K]": 300.0}, "Gaussian": {}}}
        }
    }
    merge_filling(params)
    assert params["Hamiltonian"]["DFTB"]["Filling"] == {"Gaussian": {"Temperature [K]": 300.0}}


def test_cosmo_solvent():
    """A named solvent with the ddCOSMO solver."""
    block = cosmo(solvation_settings({"model": "cpcm", "solvent": "water"}))
    assert block["Cosmo"]["Solvent"] == {"FromName": "water"}


def test_cosmo_epsilon():
    """A dielectric constant gives a FromConstants solvent."""
    block = cosmo(solvation_settings({"model": "cpcm", "epsilon": 78.4}))
    assert block["Cosmo"]["Solvent"]["FromConstants"]["Epsilon"] == 78.4


@pytest.mark.parametrize("model", ["smd", "gbsa"])
def test_cosmo_other_models(model):
    """Only cpcm is supported."""
    with pytest.raises(ValueError, match=f"solvation model {model} is not supported"):
        cosmo(solvation_settings({"model": model, "solvent": "water"}))


def test_velocity_verlet_nve():
    """Without thermostat: InitialTemperature, 0 K by default."""
    driver = velocity_verlet(md_settings({"steps": 5, "dt": 0.5}))
    assert driver == {
        "Steps": 5,
        "TimeStep [fs]": 0.5,
        "MDRestartFrequency": 1,
        "Thermostat": {"None": {"InitialTemperature [K]": 0.0}},
    }


def test_velocity_verlet_berendsen():
    """The Berendsen thermostat keeps temperature and time scale."""
    md = {"steps": 5, "dt": 0.5, "temperature": 300.0, "thermostat": {"berendsen": {"time_constant": 50.0}}}
    driver = velocity_verlet(md_settings(md))
    assert driver["Thermostat"] == {"Berendsen": {"Temperature [K]": 300.0, "Timescale [fs]": 50.0}}


# ----------------------------------------------------------------------
# collect
# ----------------------------------------------------------------------


@pytest.fixture
def collect(dftbplus, make_instance):
    """Return a function running DFTB+ collect() on an instance."""

    def run(method, method_args, module="sp", module_args=None, **props):
        instance = make_instance(
            dftbplus,
            method=method,
            method_args=method_args,
            module=module,
            module_args=module_args or {},
            **props,
        )
        return dftbplus.collect(instance)

    return run


def test_collect_geometry_and_momenta(collect, sk_basis):
    """The geometry file is included; angular momenta per element."""
    params = collect("dftb-2", {"basis": sk_basis})
    assert params["Geometry"] == {"GenFormat": {"<<<": "geo.gen"}}
    assert params["Hamiltonian"]["DFTB"]["MaxAngularMomentum"] == {"O": "p", "H": "s"}


def test_collect_angular_momenta_from_config(dftbplus, make_instance, sk_basis):
    """The "max-angular-momenta" option overrides the defaults."""
    dftbplus.options["max-angular-momenta"] = {"O": "d"}
    instance = make_instance(dftbplus, method="dftb-2", method_args={"basis": sk_basis}, module="sp")
    params = dftbplus.collect(instance)
    assert params["Hamiltonian"]["DFTB"]["MaxAngularMomentum"] == {"O": "d", "H": "s"}


def test_collect_smearing(collect, sk_basis):
    """filling + smearing give one Filling scheme with its temperature."""
    args = {"basis": sk_basis, "filling": 300.0, "smearing": "methfessel-paxton"}
    filling = collect("dftb-2", args)["Hamiltonian"]["DFTB"]["Filling"]
    assert filling == {"MethfesselPaxton": {"Temperature [K]": 300.0}}


def test_collect_lennard_jones(collect, sk_basis):
    """lj-uff gets the UFF parameters block."""
    dispersion = collect("dftb-2", {"basis": sk_basis, "dispersion": "lj-uff"})["Hamiltonian"][
        "DFTB"
    ]["Dispersion"]
    assert dispersion == {"LennardJones": {"Parameters": {"UFFParameters": {}}}}


def test_collect_md_driver(collect, sk_basis):
    """The MD module becomes a VelocityVerlet driver."""
    module_args = {"steps": 3, "time-step": 0.5}
    params = collect("dftb-2", {"basis": sk_basis}, "md", module_args)
    assert "md" not in params
    assert params["Driver"]["VelocityVerlet"]["Steps"] == 3


def test_collect_solvation(collect, sk_basis):
    """The solvation option becomes a Cosmo block of the Hamiltonian."""
    options = {"solvation": {"model": "cpcm", "solvent": "water"}}
    params = collect("dftb-2", {"basis": sk_basis}, options=options)
    assert "solvation" not in params
    assert params["Hamiltonian"]["DFTB"]["Solvation"]["Cosmo"]["Solvent"] == {"FromName": "water"}


def test_collect_xtb(collect):
    """xTB keeps its Hamiltonian, without angular momenta."""
    params = collect("xtb", {})
    assert params["Hamiltonian"] == {"xTB": {"Method": "GFN2-xTB"}}


def test_collect_xtb_multiplicity(collect):
    """xTB with DFTB+: only singlets."""
    with pytest.raises(ValueError, match="only multiplicity 1"):
        collect("xtb", {"multiplicity": 2})


def test_collect_xtb_periodic(collect):
    """xTB with DFTB+: no periodic image."""
    with pytest.raises(ValueError, match="periodic images are not supported"):
        collect("xtb", {}, image=bulk("Si"))


def test_collect_periodic_kpoints(collect, sk_basis):
    """A periodic image with a k-point grid."""
    params = collect("dftb-2", {"basis": sk_basis, "kpoints": [2, 2, 2]}, image=bulk("Si"))
    assert "SupercellFolding" in params["Hamiltonian"]["DFTB"]["KPointsAndWeights"]


def test_collect_periodic_without_kpoints(collect, sk_basis):
    """A periodic image needs a k-point grid."""
    with pytest.raises(ValueError, match="requires a kpoints grid"):
        collect("dftb-2", {"basis": sk_basis}, image=bulk("Si"))


def test_collect_kpoints_without_periodicity(collect, sk_basis):
    """A k-point grid needs a periodic image."""
    with pytest.raises(ValueError, match="kpoints requires a periodic image"):
        collect("dftb-2", {"basis": sk_basis, "kpoints": [1, 1, 1]})


def test_collect_td_disables_forces(collect, sk_basis):
    """TD-DFTB (Casida) turns off the forces set by default."""
    params = collect("dftb-2", {"basis": sk_basis}, "td-dftb", {"excitations": 3})
    assert params["Analysis"]["CalculateForces"] is False


def test_collect_forces_still_on_without_td(collect, sk_basis):
    """Without TD-DFTB, forces stay on."""
    assert collect("dftb-2", {"basis": sk_basis})["Analysis"]["CalculateForces"] is True


def test_collect_td_refuses_forces_handler(collect, sk_basis):
    """The forces handler is refused with TD-DFTB."""
    with pytest.raises(ValueError, match="forces are not available"):
        collect("dftb-2", {"basis": sk_basis}, "td-dftb", {"excitations": 3}, handler=("forces",))


def test_collect_td_needs_scc(collect, sk_basis):
    """TD-DFTB needs SCC (not DFTB-1)."""
    with pytest.raises(ValueError, match="requires SCC"):
        collect("dftb-1", {"basis": sk_basis}, "td-dftb", {"excitations": 3})


def test_collect_td_periodic_gamma_only(collect, sk_basis):
    """Periodic TD-DFTB at the gamma point only."""
    args = {"basis": sk_basis, "kpoints": [2, 2, 2]}
    with pytest.raises(ValueError, match="requires the gamma point"):
        collect("dftb-2", args, "td-dftb", {"excitations": 3}, image=bulk("Si"))


# ----------------------------------------------------------------------
# prepare
# ----------------------------------------------------------------------


def test_prepare_writes_inputs(dftbplus, make_instance, sk_basis):
    """prepare() writes geo.gen and dftb_in.hsd in the working directory."""
    instance = make_instance(dftbplus, method="dftb-2", method_args={"basis": sk_basis}, module="sp")
    dftbplus.parameters = dftbplus.collect(instance)
    dftbplus.prepare(instance)
    workdir = Path(instance.ctx.workdir)
    hsd = (workdir / "dftb_in.hsd").read_text()
    assert 'Geometry = GenFormat {\n  <<< "geo.gen"\n}' in hsd
    assert "Hamiltonian = DFTB {" in hsd
    assert "Scc = Yes" in hsd
    assert (workdir / "geo.gen").read_text().split()[:2] == ["3", "C"]
