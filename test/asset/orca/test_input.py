"""Tests of the ORCA input: helpers, collect(), to_inp() and prepare().

Nothing is run: these tests do not need ORCA.
"""

from pathlib import Path

import pytest

from amac.asset import Software
from amac.asset.md import md_settings
from amac.asset.orca.parser import to_inp
from amac.asset.orca.soft import MD_TRAJECTORY, frozen_core, md_block, ri, solvent_keyword
from amac.asset.solvation import solvation_settings

STO3G = {"basis": "sto-3g"}

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def test_ri():
    assert ri(True) == "RIJCOSX"
    assert ri(False) == "NoRIJCOSX"


def test_frozen_core():
    assert frozen_core(True) == "FrozenCore"
    assert frozen_core(False) == "NoFrozenCore"


def test_md_block_nve():
    """NVE: time step, dump and run, in this order."""
    block = md_block(md_settings({"steps": 5, "dt": 0.5}))
    assert list(block) == ["Timestep", "Dump", "Run"]
    assert block["Timestep"] == "0.5_fs"
    assert block["Dump"] == f'Position Stride 1 Filename "{MD_TRAJECTORY}"'
    assert block["Run"] == 5


def test_md_block_berendsen():
    """Initial velocities and Berendsen thermostat; Run stays last."""
    md = {"steps": 5, "dt": 0.5, "temperature": 300.0, "thermostat": {"berendsen": {"time_constant": 50.0}}}
    block = md_block(md_settings(md))
    assert block["Initvel"] == "300.0_K"
    assert block["Thermostat"] == "Berendsen 300.0_K Timecon 50.0_fs"
    assert list(block)[-1] == "Run"


@pytest.mark.parametrize(
    ("node", "method", "keyword", "cpcm"),
    [
        ({"model": "cpcm", "solvent": "water"}, "HF", "CPCM(water)", None),
        ({"model": "smd", "solvent": "water"}, "HF", "SMD(water)", None),
        ({"model": "cpcm", "epsilon": 78.4}, "HF", "CPCM", {"epsilon": 78.4}),
        ({"model": "gbsa", "solvent": "water"}, "XTB2", "ALPB(water)", None),
    ],
)
def test_solvent_keyword(node, method, keyword, cpcm):
    """Solvation keyword of the "!" line, and %cpcm for a dielectric constant."""
    params = {"!": {"method": method}}
    solvent_keyword(params, solvation_settings(node))
    assert params["!"]["solvation"] == keyword
    assert params.get("%cpcm") == cpcm


def test_solvent_keyword_gbsa_needs_xtb():
    """ALPB (gbsa) is available with xTB only."""
    with pytest.raises(ValueError, match="available with xTB only"):
        solvent_keyword({"!": {"method": "HF"}}, solvation_settings({"model": "gbsa", "solvent": "water"}))


# ----------------------------------------------------------------------
# collect
# ----------------------------------------------------------------------


@pytest.fixture
def collect(orca, make_instance):
    """Return a function running ORCA collect() on an instance."""

    def run(method, method_args, module="sp", module_args=None, soft=None, **props):
        soft = soft or orca
        instance = make_instance(
            soft,
            method=method,
            method_args=method_args,
            module=module,
            module_args=module_args or {},
            **props,
        )
        return soft.collect(instance)

    return run


def test_collect_integer_charge(collect):
    """ORCA expects an integer charge."""
    params = collect("hf", {**STO3G, "charge": 1.0, "multiplicity": 2})
    assert params["*"] == {"charge": 1, "mult": 2}
    assert isinstance(params["*"]["charge"], int)


def test_collect_forces_engrad(collect):
    """Forces on a single point need EnGrad."""
    assert collect("hf", STO3G, handler=("forces",))["!"]["run"] == "EnGrad"
    assert collect("hf", STO3G)["!"]["run"] == "SP"


def test_collect_md(collect):
    """The MD node becomes a %md block."""
    params = collect("hf", STO3G, "md", {"steps": 5, "time-step": 0.5})
    assert "md" not in params
    assert params["%md"]["Run"] == 5


def test_collect_solvation(collect):
    """The solvation option becomes a keyword."""
    options = {"solvation": {"model": "cpcm", "solvent": "water"}}
    params = collect("hf", STO3G, options=options)
    assert "solvation" not in params
    assert params["!"]["solvation"] == "CPCM(water)"


def test_collect_pal(collect, offline_config):
    """Several process units give a %pal block (no MPI launcher)."""
    soft = Software.create("orca", process_unit=4)
    assert collect("hf", STO3G, soft=soft)["%pal"] == {"nprocs": 4}
    assert "%pal" not in collect("hf", STO3G)


# ----------------------------------------------------------------------
# to_inp and prepare
# ----------------------------------------------------------------------


def test_to_inp(water):
    """Keywords, blocks (nested and indexed keys), then the coordinates."""
    params = {
        "!": {"method": "HF", "basis": "sto-3g", "empty": None, "run": "SP"},
        "%pal": {"nprocs": 2},
        "%casscf": {"norb": 4, "weights[0]": [0.5, 0.5], "sub": {"flag": True}},
        "*": {"charge": 0, "mult": 1},
    }
    assert to_inp(params, water) == (
        "! HF sto-3g SP\n"
        "%pal\n"
        "  nprocs 2\n"
        "end\n"
        "%casscf\n"
        "  norb 4\n"
        "  weights[0] = 0.5, 0.5\n"
        "  sub\n"
        "    flag true\n"
        "  end\n"
        "end\n"
        "* xyz 0 1\n"
        "O      0.0000000000     0.0000000000     0.1192620000\n"
        "H      0.0000000000     0.7632390000    -0.4770470000\n"
        "H      0.0000000000    -0.7632390000    -0.4770470000\n"
        "*\n"
    )


def test_prepare_writes_input(orca, make_instance):
    """prepare() writes input-orca.inp in the working directory."""
    instance = make_instance(orca, method="hf", method_args=STO3G, module="sp")
    orca.parameters = orca.collect(instance)
    orca.prepare(instance)
    text = (Path(instance.ctx.workdir) / "input-orca.inp").read_text()
    assert text.startswith("! HF sto-3g SP\n")
    assert "* xyz 0 1\n" in text
