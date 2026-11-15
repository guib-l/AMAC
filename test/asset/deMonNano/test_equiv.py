"""deMonNano equiv.json: canonical methods and modules -> deMonNanoPy arguments."""

import pytest

BASIS = {"directory": "/sk", "ptype": "BIO"}
HUBBARD = {"H": -0.1857, "O": -0.1575}

SUPPORTED = [
    ("dftb-1", {"basis": BASIS}, "sp", {}),
    ("dftb-2", {"basis": BASIS}, "sp", {}),
    ("dftb-3", {"basis": BASIS, "hubbard-derivs": HUBBARD}, "sp", {}),
    ("ci-dftb", {"basis": BASIS, "size-ci": 2, "fragments": [3, 3]}, "sp", {}),
    ("dftb-2", {"basis": BASIS}, "optimization-geometry", {}),
    ("dftb-2", {"basis": BASIS}, "td-dftb", {"excitations": 4}),
    ("dftb-2", {"basis": BASIS}, "frequencies", {}),
]

UNSUPPORTED = [
    ("hf", {"basis": "sto-3g"}, "sp", {}),
    ("xtb", {}, "sp", {}),
    ("dftb-2", {"basis": BASIS}, "md", {"steps": 2, "time-step": 0.5}),
    ("dftb-2", {"basis": BASIS}, "ts", {}),
]


@pytest.mark.parametrize(
    ("method", "method_args", "module", "module_args"),
    SUPPORTED,
    ids=[f"{case[0]}/{case[2]}" for case in SUPPORTED],
)
def test_supported(demonnano, method, method_args, module, module_args):
    """Supported combinations translate into DFTB parameters and a basis."""
    params = demonnano.build_parameters(method, method_args, module, module_args)
    assert "DFTB" in params["DEMON_PARAMETERS"]["ACTIVE"]
    assert params["BASIS"] == {"SKFILE": "/sk", "PTYPE": "BIO"}


@pytest.mark.parametrize(
    ("method", "method_args", "module", "module_args"),
    UNSUPPORTED,
    ids=[f"{case[0]}/{case[2]}" for case in UNSUPPORTED],
)
def test_unsupported(demonnano, method, method_args, module, module_args):
    """Unsupported methods and modules are refused."""
    with pytest.raises(NotImplementedError, match="is not supported"):
        demonnano.build_parameters(method, method_args, module, module_args)


def test_solvation_unsupported(demonnano):
    """deMonNano has no solvation option."""
    options = {"solvation": {"model": "cpcm", "solvent": "water"}}
    with pytest.raises(NotImplementedError, match="option SOLVATION"):
        demonnano.build_parameters("dftb-2", {"basis": BASIS}, "sp", {}, options)


def test_dftb1_no_scc(demonnano):
    """DFTB-1: no SCC."""
    params = demonnano.build_parameters("dftb-1", {"basis": BASIS}, "sp")
    assert params["DEMON_PARAMETERS"]["ACTIVE"]["DFTB"] == {}


def test_dftb2_arguments(demonnano):
    """SCC tolerance, maximum of cycles and charge."""
    args = {"basis": BASIS, "scc-tol": 1e-6, "scc-max": 50, "charge": 1.0}
    active = demonnano.build_parameters("dftb-2", args, "sp")["DEMON_PARAMETERS"]["ACTIVE"]
    assert active["DFTB"] == {"SCC": True, "TOL": 1e-6, "MAX": 50}
    assert active["CHARGE"] == 1.0


def test_dftb3(demonnano):
    """DFTB-3: third order; Hubbard derivatives kept apart (ORB_PARAMS)."""
    params = demonnano.build_parameters("dftb-3", {"basis": BASIS, "hubbard-derivs": HUBBARD}, "sp")
    assert params["DEMON_PARAMETERS"]["ACTIVE"]["DFTB"]["THIRD"] is True
    assert params["ORB_PARAMS"] == HUBBARD


def test_ci_dftb(demonnano):
    """CI-DFTB: CI size and fragments."""
    args = {"basis": BASIS, "size-ci": 2, "fragments": [3, 3]}
    active = demonnano.build_parameters("ci-dftb", args, "sp")["DEMON_PARAMETERS"]["ACTIVE"]
    assert active["CI"] == {"SIZECI": 2}
    assert active["CUTSYS"] == {"FRAGMENT": [3, 3]}


def test_modules(demonnano):
    """Optimization, TD-DFTB and frequencies keywords."""
    opt = demonnano.build_parameters("dftb-2", {"basis": BASIS}, "opt")
    assert opt["DEMON_MODULE"]["ACTIVE"]["OPT"] == {}
    td = demonnano.build_parameters("dftb-2", {"basis": BASIS}, "td-dftb", {"excitations": 4})
    assert td["DEMON_PARAMETERS"]["ACTIVE"]["TD-DFTB"] == {"LRESP": 4}
    freq = demonnano.build_parameters("dftb-2", {"basis": BASIS}, "freq")
    assert freq["DEMON_PARAMETERS"]["ACTIVE"]["FREQ"] is True
