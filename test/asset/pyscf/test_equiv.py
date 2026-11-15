"""PySCF equiv.json: canonical methods and modules -> PySCF settings.

These tests do not import PySCF.
"""

import pytest

SUPPORTED = [
    ("hf", {"basis": "sto-3g"}, "sp", {}),
    ("dft", {"basis": "sto-3g", "functional": "pbe"}, "sp", {}),
    ("mp2", {"basis": "sto-3g"}, "sp", {}),
    ("ccsd", {"basis": "sto-3g"}, "sp", {}),
    ("ccsd(t)", {"basis": "sto-3g"}, "sp", {}),
    ("casscf", {"basis": "sto-3g", "active-orbitals": 4, "active-electrons": 4}, "sp", {}),
    ("hf", {"basis": "sto-3g"}, "optimization-geometry", {}),
    ("hf", {"basis": "sto-3g"}, "frequencies", {}),
    ("hf", {"basis": "sto-3g"}, "excited-states", {"excitations": 3}),
    ("hf", {"basis": "sto-3g"}, "md", {"steps": 3, "time-step": 0.5}),
    ("hf", {"basis": "sto-3g"}, "transition-state", {}),
]

UNSUPPORTED = [
    ("xtb", {}),
    ("dftb-1", {"basis": {"directory": "/sk"}}),
]


@pytest.mark.parametrize(
    ("method", "method_args", "module", "module_args"),
    SUPPORTED,
    ids=[f"{case[0]}/{case[2]}" for case in SUPPORTED],
)
def test_supported(pyscf_soft, method, method_args, module, module_args):
    """Supported combinations translate with a molecule and a run type."""
    params = pyscf_soft.build_parameters(method, method_args, module, module_args)
    assert params["mol"] == {"charge": 0, "multiplicity": 1, "basis": "sto-3g"}
    assert params["run"]


@pytest.mark.parametrize(("method", "method_args"), UNSUPPORTED, ids=[case[0] for case in UNSUPPORTED])
def test_unsupported(pyscf_soft, method, method_args):
    """Semi-empirical methods are refused."""
    with pytest.raises(NotImplementedError, match="is not supported"):
        pyscf_soft.build_parameters(method, method_args, "sp", {})


def test_hf_settings(pyscf_soft):
    """HF arguments become molecule and SCF settings."""
    args = {
        "basis": "sto-3g",
        "charge": 1.0,
        "multiplicity": 2,
        "reference": "unrestricted",
        "scf-tol": 1e-9,
        "scf-max": 10,
        "level-shift": 0.1,
        "density-fitting": True,
        "aux-basis": "def2/j",
    }
    params = pyscf_soft.build_parameters("hf", args, "sp")
    assert params["mol"] == {"charge": 1.0, "multiplicity": 2, "basis": "sto-3g"}
    assert params["scf"] == {
        "reference": "U",
        "conv_tol": 1e-9,
        "max_cycle": 10,
        "level_shift": 0.1,
        "density_fit": True,
        "auxbasis": "def2/j",
    }


def test_dft_settings(pyscf_soft):
    """Functional, grid and dispersion; B3LYP is the VWN5 variant."""
    args = {"basis": "sto-3g", "functional": "pbe", "grid": "fine", "dispersion": "d3-bj"}
    assert pyscf_soft.build_parameters("dft", args, "sp")["dft"] == {
        "xc": "pbe",
        "grids_level": 8,
        "disp": "d3bj",
    }
    args = {"basis": "sto-3g", "functional": "b3lyp"}
    assert pyscf_soft.build_parameters("dft", args, "sp")["dft"] == {"xc": "b3lyp5"}


@pytest.mark.parametrize(
    ("method", "args", "post"),
    [
        ("mp2", {"frozen-core": True}, {"method": "mp2", "frozen_core": True}),
        ("ccsd", {"cc-tol": 1e-8, "cc-max": 20}, {"method": "ccsd", "conv_tol": 1e-8, "max_cycle": 20}),
        ("ccsd(t)", {}, {"method": "ccsd(t)"}),
        (
            "casscf",
            {"active-orbitals": 4, "active-electrons": 4, "roots": 2, "weights": [0.5, 0.5]},
            {"method": "casscf", "ncas": 4, "nelecas": 4, "nroots": 2, "weights": [0.5, 0.5]},
        ),
    ],
)
def test_post_hf(pyscf_soft, method, args, post):
    """Post-HF methods fill the "post" settings."""
    params = pyscf_soft.build_parameters(method, {"basis": "sto-3g", **args}, "sp")
    assert params["post"] == post


@pytest.mark.parametrize(
    ("module", "module_args", "expected"),
    [
        ("opt", {"max-step": 3}, {"run": "optimization", "opt": {"maxsteps": 3}}),
        ("ts", {}, {"run": "transition-state", "opt": {"transition": True}}),
        ("freq", {}, {"run": "frequencies"}),
        (
            "td",
            {"excitations": 3, "symmetry": "both", "tda": True},
            {"run": "excited-states", "td": {"nstates": 3, "symmetry": "both", "tda": True}},
        ),
        (
            "md",
            {"steps": 3, "time-step": 0.5, "temperature": 300.0},
            {"run": "md", "md": {"steps": 3, "dt": 0.5, "temperature": 300.0}},
        ),
    ],
)
def test_modules(pyscf_soft, module, module_args, expected):
    """Each module sets the run type and its settings."""
    params = pyscf_soft.build_parameters("hf", {"basis": "sto-3g"}, module, module_args)
    for key, value in expected.items():
        assert params[key] == value


def test_solvation(pyscf_soft):
    """Solvation writes a canonical "solvation" node."""
    options = {"solvation": {"model": "smd", "solvent": "water"}}
    params = pyscf_soft.build_parameters("hf", {"basis": "sto-3g"}, "sp", {}, options)
    assert params["solvation"] == {"model": "smd", "solvent": "water"}
