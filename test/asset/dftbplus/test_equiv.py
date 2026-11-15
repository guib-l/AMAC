"""DFTB+ equiv.json: canonical methods and modules -> DFTB+ parameters."""

import pytest

BASIS = {"directory": "/sk"}
HUBBARD = {"H": -0.1857, "O": -0.1575}

SUPPORTED = [
    ("dftb-1", {"basis": BASIS}, "sp", {}),
    ("dftb-2", {"basis": BASIS}, "sp", {}),
    ("dftb-3", {"basis": BASIS, "hubbard-derivs": HUBBARD}, "sp", {}),
    ("xtb", {}, "sp", {}),
    ("dftb-2", {"basis": BASIS}, "optimization-geometry", {}),
    ("dftb-2", {"basis": BASIS}, "td-dftb", {"excitations": 4}),
    ("dftb-2", {"basis": BASIS}, "md", {"steps": 3, "time-step": 0.5}),
]

UNSUPPORTED = [
    ("ci-dftb", {"basis": BASIS, "size-ci": 2, "fragments": [3, 3]}, "sp"),
    ("hf", {"basis": "sto-3g"}, "sp"),
    ("dftb-2", {"basis": BASIS}, "freq"),
    ("dftb-2", {"basis": BASIS}, "ts"),
]


@pytest.mark.parametrize(
    ("method", "method_args", "module", "module_args"),
    SUPPORTED,
    ids=[f"{case[0]}/{case[2]}" for case in SUPPORTED],
)
def test_supported(dftbplus, method, method_args, module, module_args):
    """Supported combinations translate, with the default values first."""
    params = dftbplus.build_parameters(method, method_args, module, module_args)
    assert params["Options"]["WriteResultsTag"] is True
    assert params["Analysis"]["CalculateForces"] is True
    assert "Hamiltonian" in params


@pytest.mark.parametrize(
    ("method", "method_args", "module"),
    UNSUPPORTED,
    ids=[f"{case[0]}/{case[2]}" for case in UNSUPPORTED],
)
def test_unsupported(dftbplus, method, method_args, module):
    """Unsupported methods and modules are refused."""
    with pytest.raises(NotImplementedError, match="is not supported"):
        dftbplus.build_parameters(method, method_args, module, {})


def test_dftb1_no_scc(dftbplus):
    """DFTB-1: no SCC; Slater-Koster files from the basis directory."""
    dftb = dftbplus.build_parameters("dftb-1", {"basis": BASIS}, "sp")["Hamiltonian"]["DFTB"]
    assert "Scc" not in dftb
    assert dftb["SlaterKosterFiles"]["Type2FileNames"] == {
        "Prefix": "/sk/",
        "Separator": "-",
        "Suffix": ".skf",
        "LowerCaseTypeName": False,
    }


def test_dftb2_scc(dftbplus):
    """DFTB-2: SCC with its tolerance and maximum of iterations."""
    args = {"basis": BASIS, "scc-tol": 1e-6, "scc-max": 50}
    dftb = dftbplus.build_parameters("dftb-2", args, "sp")["Hamiltonian"]["DFTB"]
    assert dftb["Scc"] is True
    assert dftb["SccTolerance"] == 1e-6
    assert dftb["MaxSccIterations"] == 50


def test_dftb3_third_order(dftbplus):
    """DFTB-3: full third order and Hubbard derivatives."""
    args = {"basis": BASIS, "hubbard-derivs": HUBBARD}
    dftb = dftbplus.build_parameters("dftb-3", args, "sp")["Hamiltonian"]["DFTB"]
    assert dftb["ThirdOrderFull"] is True
    assert dftb["HubbardDerivs"] == HUBBARD


def test_xtb(dftbplus):
    """xTB: GFN2-xTB Hamiltonian."""
    params = dftbplus.build_parameters("xtb", {}, "sp")
    assert params["Hamiltonian"] == {"xTB": {"Method": "GFN2-xTB"}}


def test_mixer_children(dftbplus):
    """A mixer becomes a node with its parameters."""
    args = {"basis": BASIS, "mixer": {"value": "broyden", "mixing-parameter": 0.2}}
    dftb = dftbplus.build_parameters("dftb-2", args, "sp")["Hamiltonian"]["DFTB"]
    assert dftb["Mixer"] == {"Broyden": {"MixingParameter": 0.2}}


def test_kpoints(dftbplus):
    """A k-point grid becomes a SupercellFolding block."""
    dftb = dftbplus.build_parameters("dftb-2", {"basis": BASIS, "kpoints": [2, 1, 1]}, "sp")[
        "Hamiltonian"
    ]["DFTB"]
    assert dftb["KPointsAndWeights"] == {
        "SupercellFolding": {"": [2, 0, 0, 0, 1, 0, 0, 0, 1, 0.5, 0.0, 0.0]}
    }


def test_optimization(dftbplus):
    """The optimization module selects the GeometryOptimization driver."""
    params = dftbplus.build_parameters("dftb-2", {"basis": BASIS}, "opt")
    assert params["Driver"] == {"GeometryOptimization": {}}


def test_td_dftb(dftbplus):
    """TD-DFTB fills the Casida block."""
    module_args = {"excitations": 4, "symmetry": "singlet", "diagonalizer": "arpack"}
    params = dftbplus.build_parameters("dftb-2", {"basis": BASIS}, "td-dftb", module_args)
    casida = params["ExcitedState"]["Casida"]
    assert casida["NrOfExcitations"] == 4
    assert casida["Symmetry"] == "singlet"
    assert "Arpack" in casida["Diagonaliser"]


def test_md_node(dftbplus):
    """MD writes a canonical "md" node, turned into a driver by collect()."""
    module_args = {"steps": 3, "time-step": 0.5, "temperature": 300.0}
    params = dftbplus.build_parameters("dftb-2", {"basis": BASIS}, "md", module_args)
    assert params["md"] == {"steps": 3, "dt": 0.5, "temperature": 300.0}


def test_solvation_node(dftbplus):
    """Solvation writes a canonical "solvation" node."""
    options = {"solvation": {"model": "cpcm", "solvent": "water"}}
    params = dftbplus.build_parameters("dftb-2", {"basis": BASIS}, "sp", {}, options)
    assert params["solvation"] == {"model": "cpcm", "solvent": "water"}
