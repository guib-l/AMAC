"""ORCA equiv.json: canonical methods and modules -> ORCA keywords and blocks."""

import pytest

STO3G = {"basis": "sto-3g"}

SUPPORTED = [
    ("hf", STO3G, "sp", {}),
    ("dft", {"basis": "def2-svp", "functional": "b3lyp"}, "sp", {}),
    ("mp2", STO3G, "sp", {}),
    ("ccsd", STO3G, "sp", {}),
    ("ccsd(t)", STO3G, "sp", {}),
    ("casscf", {**STO3G, "active-orbitals": 4, "active-electrons": 4}, "sp", {}),
    ("xtb", {}, "sp", {}),
    ("hf", STO3G, "optimization-geometry", {}),
    ("hf", STO3G, "frequencies", {}),
    ("hf", STO3G, "excited-states", {"excitations": 3}),
    ("hf", STO3G, "md", {"steps": 5, "time-step": 0.5}),
    ("hf", STO3G, "transition-state", {}),
]


@pytest.mark.parametrize(
    ("method", "method_args", "module", "module_args"),
    SUPPORTED,
    ids=[f"{case[0]}/{case[2]}" for case in SUPPORTED],
)
def test_supported(orca, method, method_args, module, module_args):
    """Supported combinations give a "!" line and the charge/multiplicity."""
    params = orca.build_parameters(method, method_args, module, module_args)
    assert params["*"] == {"charge": 0, "mult": 1}
    assert params["!"]["method"]
    assert params["!"]["run"]


@pytest.mark.parametrize("method", ["dftb-1", "dftb-2"])
def test_dftb_unsupported(orca, method):
    """DFTB is not available with ORCA."""
    with pytest.raises(NotImplementedError, match="DFTB is not supported"):
        orca.build_parameters(method, {"basis": {"directory": "/sk"}}, "sp", {})


@pytest.mark.parametrize(
    ("method", "args", "keyword"),
    [
        ("hf", STO3G, "HF"),
        ("dft", {"basis": "def2-svp", "functional": "b3lyp"}, "B3LYP"),
        ("dft", {"basis": "def2-svp", "functional": "pbe"}, "PBE"),
        ("mp2", STO3G, "MP2"),
        ("ccsd(t)", STO3G, "CCSD(T)"),
        ("xtb", {}, "XTB2"),
    ],
)
def test_method_keyword(orca, method, args, keyword):
    """The method keyword of the "!" line."""
    assert orca.build_parameters(method, args, "sp")["!"]["method"] == keyword


@pytest.mark.parametrize(
    ("module", "module_args", "run"),
    [
        ("sp", {}, "SP"),
        ("opt", {}, "Opt"),
        ("freq", {}, "Freq"),
        ("ts", {}, "OptTS"),
        ("md", {"steps": 5, "time-step": 0.5}, "MD"),
        ("td", {"excitations": 3}, "SP"),
    ],
)
def test_run_keyword(orca, module, module_args, run):
    """The run type of the "!" line."""
    assert orca.build_parameters("hf", STO3G, module, module_args)["!"]["run"] == run


def test_hf_settings(orca):
    """Charge, multiplicity and the %scf block."""
    args = {
        **STO3G,
        "charge": 1.0,
        "multiplicity": 2,
        "reference": "unrestricted",
        "scf-tol": 1e-8,
        "scf-max": 50,
    }
    params = orca.build_parameters("hf", args, "sp")
    assert params["*"] == {"charge": 1.0, "mult": 2}
    assert params["%scf"] == {"HFTyp": "UHF", "TolE": 1e-8, "MaxIter": 50}


def test_dft_settings(orca):
    """Dispersion, grid and RI keywords."""
    args = {
        "basis": "def2-svp",
        "functional": "pbe",
        "dispersion": "d3-bj",
        "grid": "fine",
        "density-fitting": True,
    }
    keywords = orca.build_parameters("dft", args, "sp")["!"]
    assert keywords["dispersion"] == "D3BJ"
    assert keywords["grid"] == "DefGrid3"
    assert keywords["ri"] == "RIJCOSX"


def test_correlated_settings(orca):
    """Frozen core keyword and the %mdci block."""
    params = orca.build_parameters("ccsd(t)", {**STO3G, "frozen-core": False, "cc-tol": 1e-8}, "sp")
    assert params["!"]["frozen-core"] == "NoFrozenCore"
    assert params["%mdci"] == {"STol": 1e-8}


def test_casscf_block(orca):
    """The %casscf block: active space and roots."""
    args = {**STO3G, "active-orbitals": 4, "active-electrons": 4, "roots": 2}
    assert orca.build_parameters("casscf", args, "sp")["%casscf"] == {"norb": 4, "nel": 4, "nroots": 2}


def test_tddft_block(orca):
    """The %tddft block."""
    module_args = {"excitations": 3, "tda": True, "symmetry": "both"}
    params = orca.build_parameters("hf", STO3G, "td", module_args)
    assert params["%tddft"] == {"TDA": True, "NRoots": 3, "Triplets": True}


def test_optimization_block(orca):
    """Maximum number of optimization steps."""
    assert orca.build_parameters("hf", STO3G, "opt", {"max-step": 3})["%geom"] == {"MaxIter": 3}


def test_md_node(orca):
    """MD writes a canonical "md" node, turned into %md by collect()."""
    params = orca.build_parameters("hf", STO3G, "md", {"steps": 5, "time-step": 0.5})
    assert params["md"] == {"steps": 5, "dt": 0.5}
