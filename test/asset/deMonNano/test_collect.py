"""Tests of the deMonNano asset: collect() and prepare() (nothing is run)."""

from pathlib import Path

import pytest
from ase.build import bulk


@pytest.fixture
def collect(demonnano, make_instance):
    """Return a function running deMonNano collect() on an instance."""

    def run(method, method_args, module="sp", module_args=None, **props):
        instance = make_instance(
            demonnano,
            method=method,
            method_args=method_args,
            module=module,
            module_args=module_args or {},
            **props,
        )
        return demonnano.collect(instance)

    return run


def test_collect_executable_and_basis(collect, bio_basis, offline_config):
    """The executable and the basis directory come from the configuration."""
    section = offline_config["software"]["deMonNano"]
    params = collect("dftb-2", {"basis": bio_basis})
    assert params["DEMON_EXECUTABLE"] == section["executable"]
    assert params["BASIS"]["SKFILE"] == section["basis"]
    assert params["BASIS"]["PTYPE"] == "BIO"


def test_collect_forces_single_point(collect, bio_basis):
    """Forces on a single point need the OPT SP keyword."""
    params = collect("dftb-2", {"basis": bio_basis}, "single-point", handler=("forces",))
    assert params["DEMON_MODULE"]["ACTIVE"]["OPT"] == {"SP": True}


@pytest.mark.parametrize("module", ["sp", "single", "SINGLE-POINT"])
def test_collect_forces_single_point_alias(collect, bio_basis, module):
    """Aliases of single-point, any case, behave as "single-point"."""
    params = collect("dftb-2", {"basis": bio_basis}, module, handler=("forces",))
    assert params["DEMON_MODULE"]["ACTIVE"]["OPT"] == {"SP": True}


@pytest.mark.parametrize("module", ["single-point", "opt", None])
def test_collect_module_marker_removed(collect, bio_basis, module):
    """The AMAC_MODULE marker never reaches deMonPy."""
    assert "AMAC_MODULE" not in collect("dftb-2", {"basis": bio_basis}, module)


def test_collect_forces_other_module(collect, bio_basis):
    """Forces on another module do not add the OPT SP keyword."""
    params = collect("dftb-2", {"basis": bio_basis}, "freq", handler=("forces",))
    assert "DEMON_MODULE" not in params


def test_collect_no_forces(collect, bio_basis):
    """Without the forces handler, no OPT keyword."""
    params = collect("dftb-2", {"basis": bio_basis}, "single-point")
    assert "DEMON_MODULE" not in params


def test_collect_hubbard_derivatives(demonnano, collect, bio_basis):
    """DFTB-3 Hubbard derivatives are kept apart for the 3ord_param file."""
    hubbard = {"H": -0.1857, "O": -0.1575}
    params = collect("dftb-3", {"basis": bio_basis, "hubbard-derivs": hubbard})
    assert "ORB_PARAMS" not in params
    assert demonnano.orb_params == hubbard


def test_collect_periodic(collect, bio_basis):
    """A periodic image with k-points gets a GENERAL PBC block."""
    params = collect("dftb-2", {"basis": bio_basis, "kpoints": [2, 2, 2]}, image=bulk("Si"))
    assert params["DEMON_PARAMETERS"]["ACTIVE"]["PBC"] == {"KPTS": [2, 2, 2], "TYPE": "GENERAL"}


def test_collect_periodic_without_kpoints(collect, bio_basis):
    """A periodic image needs k-points."""
    with pytest.raises(ValueError, match="requires a kpoints grid"):
        collect("dftb-2", {"basis": bio_basis}, image=bulk("Si"))


def test_collect_kpoints_without_periodicity(collect, bio_basis):
    """k-points need a periodic image."""
    with pytest.raises(ValueError, match="kpoints requires a periodic image"):
        collect("dftb-2", {"basis": bio_basis, "kpoints": [1, 1, 1]})


def test_collect_td_periodic_gamma(collect, bio_basis):
    """Periodic TD-DFTB is accepted at the gamma point only."""
    args = {"basis": bio_basis, "kpoints": [1, 1, 1]}
    params = collect("dftb-2", args, "td-dftb", {"excitations": 3}, image=bulk("Si"))
    assert params["DEMON_PARAMETERS"]["ACTIVE"]["TD-DFTB"] == {"LRESP": 3}
    args["kpoints"] = [2, 2, 2]
    with pytest.raises(ValueError, match="TD-DFTB is molecular"):
        collect("dftb-2", args, "td-dftb", {"excitations": 3}, image=bulk("Si"))


def test_collect_frequencies_periodic(collect, bio_basis):
    """Frequencies are refused for periodic systems."""
    args = {"basis": bio_basis, "kpoints": [1, 1, 1]}
    with pytest.raises(ValueError, match="frequencies are not supported for periodic"):
        collect("dftb-2", args, "freq", image=bulk("Si"))


def test_prepare_writes_3ord_param(demonnano, make_instance, bio_basis):
    """prepare() writes the Hubbard derivatives into 3ord_param."""
    instance = make_instance(
        demonnano,
        method="dftb-3",
        method_args={"basis": bio_basis, "hubbard-derivs": {"H": -0.1857, "O": -0.1575}},
        module="sp",
    )
    demonnano.parameters = demonnano.collect(instance)
    demonnano.prepare(instance)
    path = Path(instance.ctx.workdir) / "3ord_param"
    assert path.read_text() == "H -0.1857\nO -0.1575\n"


def test_prepare_keeps_existing_3ord_param(demonnano, make_instance, bio_basis):
    """An existing, non-empty 3ord_param file is kept."""
    instance = make_instance(
        demonnano,
        method="dftb-3",
        method_args={"basis": bio_basis, "hubbard-derivs": {"H": -0.1857}},
        module="sp",
    )
    path = Path(instance.ctx.workdir) / "3ord_param"
    path.parent.mkdir(parents=True)
    path.write_text("H -0.2\n")
    demonnano.parameters = demonnano.collect(instance)
    demonnano.prepare(instance)
    assert path.read_text() == "H -0.2\n"


def test_prepare_nothing_without_dftb3(demonnano, make_instance, bio_basis):
    """Without Hubbard derivatives, prepare() writes nothing."""
    instance = make_instance(demonnano, method="dftb-2", method_args={"basis": bio_basis}, module="sp")
    demonnano.parameters = demonnano.collect(instance)
    demonnano.prepare(instance)
    assert not Path(instance.ctx.workdir).exists()
