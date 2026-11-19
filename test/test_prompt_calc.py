"""Tests of prompt_calc stages 2-3 (validate, resolve): pure, no binary, no network.

The LLM prompt battery (test_prompt_battery) is marked ``real`` and skips
when no LLM endpoint is configured (PROMPT_CALC_LLM_URL).
"""

import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "prompt_calc"))  # noqa: E402

import core  # noqa: E402
import execute  # noqa: E402
import resolve  # noqa: E402
import validate  # noqa: E402
from vote import vote_samples  # noqa: E402

SCHEMA = core.load_schema()
DEFAULTS = core.load_defaults()

# Config whose bases match the "3ob" entry of defaults.json (the deMonNano
# one in its real dotted form, "mio-1.1.0").
CONFIG = {
    "software": {
        "dftb+": {"basis": "/opt/sk/mio-1-1/skfiles"},
        "deMonNano": {"basis": "/opt/sk/mio-1.1.0/skfiles"},
    }
}
# Config whose dftb+ basis matches no sk-set of defaults.json.
CONFIG_UNKNOWN_BASIS = {
    "software": {
        "dftb+": {"basis": "/opt/sk/unknown-set"},
        "deMonNano": {"basis": "/opt/sk/demon"},
    }
}


def make_spec(**overrides):
    """A minimal valid dftb-2 water single-point spec, overridable per test."""
    base = {
        "software": "dftb+",
        "method": "dftb-2",
        "module": "single-point",
        "structure": {"name": "H2O"},
        "method_args": {},
        "handlers": ["lowest-energy"],
    }
    base.update(overrides)
    return base


def validate_spec(config=CONFIG, **overrides):
    """validate() of make_spec(**overrides); returns (spec, errors)."""
    spec = make_spec(**overrides)
    errors = validate.validate(spec, SCHEMA, spec.get("software", "dftb+"), DEFAULTS, config)
    return spec, errors


def codes(errors):
    return [error.code for error in errors]


# ----------------------------------------------------------------------
# validate: clean specs
# ----------------------------------------------------------------------


def test_validate_valid_dftb2_water():
    """A plain dftb-2 water single-point spec has no error."""
    _, errors = validate_spec()
    assert errors == []


def test_validate_valid_dftb3_none_dispersion():
    """dftb-3 with the explicit 'none' dispersion passes (hubbard is resolvable)."""
    _, errors = validate_spec(method="dftb-3", method_args={"dispersion": "none"})
    assert errors == []


def test_validate_canonicalizes_aliases():
    """Aliases are turned into canonical names in place."""
    spec, errors = validate_spec(method="scc-dftb", module="optimization")
    assert errors == []
    assert spec["method"] == "dftb-2"
    assert spec["module"] == "optimization-geometry"


# ----------------------------------------------------------------------
# validate: each taxonomy trigger yields the exact code + message
# ----------------------------------------------------------------------


def test_validate_bad_enum_dispersion():
    """A value outside the catalog choices is INVALID_SPEC, choices listed."""
    _, errors = validate_spec(method_args={"dispersion": "b3-bj"})
    assert codes(errors) == ["INVALID_SPEC"]
    assert errors[0].field == "method_args.dispersion"
    assert "'b3-bj' not in" in errors[0].message
    assert "'d3-bj'" in errors[0].message


def test_validate_bad_range_filling():
    """A value outside its range is INVALID_SPEC."""
    _, errors = validate_spec(method_args={"filling": -1})
    assert codes(errors) == ["INVALID_SPEC"]
    assert "out of range" in errors[0].message


def test_validate_wrong_type_multiplicity():
    """A value of the wrong type is INVALID_SPEC."""
    _, errors = validate_spec(method_args={"multiplicity": "four"})
    assert codes(errors) == ["INVALID_SPEC"]
    assert "is not of type int" in errors[0].message


def test_validate_unknown_attribute():
    """A method attribute unknown to the catalog is INVALID_SPEC."""
    _, errors = validate_spec(method_args={"bogus": 1})
    assert codes(errors) == ["INVALID_SPEC"]
    assert "unknown attribute" in errors[0].message


def test_validate_unknown_method():
    """A method outside the catalog is UNSUPPORTED_CATALOG."""
    _, errors = validate_spec(method="cpmd")
    assert codes(errors) == ["UNSUPPORTED_CATALOG"]
    assert "AMAC cannot express method 'cpmd'" in errors[0].message


def test_validate_unknown_software():
    """A software outside AMAC is UNSUPPORTED_CATALOG."""
    _, errors = validate_spec(software="CPMD")
    assert codes(errors) == ["UNSUPPORTED_CATALOG"]
    assert "supported" in errors[0].message


def test_validate_handler_of_other_software():
    """A handler of deMonNano on dftb+ is UNSUPPORTED_SOFTWARE with a hint."""
    _, errors = validate_spec(handlers=["frequencies"])
    assert codes(errors) == ["UNSUPPORTED_SOFTWARE"]
    assert "deMonNano" in errors[0].message
    assert "--software deMonNano" in errors[0].message


def test_validate_handler_nowhere():
    """A handler of no software is INVALID_SPEC."""
    _, errors = validate_spec(handlers=["not-a-handler"])
    assert codes(errors) == ["INVALID_SPEC"]
    assert "not a handler of dftb+" in errors[0].message


def test_validate_kpoints_on_molecule():
    """kpoints on a molecular structure is INVALID_SPEC."""
    _, errors = validate_spec(method_args={"kpoints": [1, 1, 1]})
    assert codes(errors) == ["INVALID_SPEC"]
    assert "periodic structure" in errors[0].message


def test_validate_dftb3_without_dispersion_hard_error():
    """Bare dftb-3 on dftb+ (no dispersion) is a hard error (decision 13.2)."""
    _, errors = validate_spec(method="dftb-3")
    assert codes(errors) == ["INVALID_SPEC"]
    assert errors[0].field == "method_args.dispersion"
    assert "required for dftb-3 with dftb+" in errors[0].message
    assert "'none'" in errors[0].message


def test_validate_demonnano_dispersion_none_unsupported():
    """'none' on deMonNano is UNSUPPORTED_SOFTWARE (DISP is a program default)."""
    _, errors = validate_spec(software="deMonNano", method_args={"dispersion": "none"})
    assert codes(errors) == ["UNSUPPORTED_SOFTWARE"]
    assert "deMonNano" in errors[0].message


def test_validate_demonnano_d3bj_unsupported():
    """d3-bj on deMonNano is UNSUPPORTED_SOFTWARE, suggesting dftb+."""
    _, errors = validate_spec(software="deMonNano", method_args={"dispersion": "d3-bj"})
    assert codes(errors) == ["UNSUPPORTED_SOFTWARE"]
    assert "dftb+" in errors[0].message


def test_validate_demonnano_dftb3_dispersion_optional():
    """dftb-3 on deMonNano without dispersion is valid (no dftb+ cross-rule)."""
    _, errors = validate_spec(software="deMonNano", method="dftb-3")
    assert codes(errors) == []


def test_validate_ci_dftb_on_dftbplus():
    """CI-DFTB (equiv supported: false) on dftb+ is UNSUPPORTED_SOFTWARE."""
    _, errors = validate_spec(method="ci-dftb", method_args={"size-ci": 2, "fragments": [3, 3]})
    assert codes(errors) == ["UNSUPPORTED_SOFTWARE"]
    assert "deMonNano" in errors[0].message


def test_validate_frequencies_on_dftbplus():
    """frequencies (equiv supported: false) on dftb+ is UNSUPPORTED_SOFTWARE."""
    _, errors = validate_spec(module="frequencies")
    assert codes(errors) == ["UNSUPPORTED_SOFTWARE"]
    assert "deMonNano" in errors[0].message


def test_validate_missing_mandatory_unresolvable():
    """dftb-3 with a basis absent from defaults.json is MISSING_DATA."""
    _, errors = validate_spec(
        config=CONFIG_UNKNOWN_BASIS, method="dftb-3", method_args={"dispersion": "none"}
    )
    assert codes(errors) == ["MISSING_DATA"]
    assert "hubbard-derivs" in errors[0].message


def test_validate_bad_structure():
    """A structure with neither a name, an xyz nor a file is INVALID_SPEC."""
    _, errors = validate_spec(structure={})
    assert codes(errors) == ["INVALID_SPEC"]


def test_validate_unknown_spec_field():
    """A top-level key outside the spec format is INVALID_SPEC."""
    _, errors = validate_spec(seed=42)
    assert codes(errors) == ["INVALID_SPEC"]
    assert "unknown spec field" in errors[0].message


# ----------------------------------------------------------------------
# resolve
# ----------------------------------------------------------------------


def resolve_spec(config=CONFIG, **overrides):
    """resolve() of make_spec(**overrides); returns the Resolved object."""
    return resolve.resolve(make_spec(**overrides), DEFAULTS, config, SCHEMA["aliases"])


def test_resolve_injects_basis_and_scc():
    """The basis directory and the scc defaults are injected and listed."""
    resolved = resolve_spec()
    args = resolved.spec["method_args"]
    assert args["basis"] == {"directory": CONFIG["software"]["dftb+"]["basis"]}
    assert args["scc-max"] == 999
    assert args["filling"] == 50
    assert "method_args.basis.directory" in resolved.injected
    assert "method_args.scc-max" in resolved.injected
    assert "method_args.filling" in resolved.injected


def test_resolve_dftb3_injects_hubbard_h_correction_damping():
    """dftb-3 + 3ob basis injects hubbard-derivs, h-correction and d3-bj damping."""
    resolved = resolve_spec(method="dftb-3", method_args={"dispersion": "d3-bj"})
    args = resolved.spec["method_args"]
    assert args["hubbard-derivs"] == {"H": -0.1857, "O": -0.1575}
    assert args["h-correction"] == {"value": "damping", "exponent": 4.0}
    assert args["dispersion"] == {
        "value": "d3-bj",
        "s6": 1.0,
        "s8": 0.49,
        "a1": 0.5719,
        "a2": 3.6017,
    }
    for key in (
        "method_args.hubbard-derivs",
        "method_args.h-correction",
        "method_args.dispersion.damping",
    ):
        assert key in resolved.injected


def test_resolve_user_values_win():
    """Values already in the user spec are never overridden by the table."""
    args = {"hubbard-derivs": {"N": -0.2}, "h-correction": {"value": "h5"}}
    resolved = resolve_spec(method="dftb-3", method_args=args)
    assert resolved.spec["method_args"]["hubbard-derivs"] == {"N": -0.2}
    assert resolved.spec["method_args"]["h-correction"] == {"value": "h5"}
    assert "method_args.hubbard-derivs" not in resolved.injected
    assert "method_args.h-correction" not in resolved.injected


def test_resolve_dftb3_unknown_basis_missing_data():
    """dftb-3 with a basis absent from defaults.json is MISSING_DATA."""
    with pytest.raises(core.Failure) as exc:
        resolve_spec(
            config=CONFIG_UNKNOWN_BASIS, method="dftb-3", method_args={"dispersion": "none"}
        )
    assert exc.value.code == "MISSING_DATA"
    assert "hubbard-derivs" in exc.value.message


def test_resolve_dispersion_none_kept():
    """'none' is kept as-is on dftb+ (the executor omits the attribute)."""
    resolved = resolve_spec(method="dftb-3", method_args={"dispersion": "none"})
    assert resolved.spec["method_args"]["dispersion"] == "none"
    assert "method_args.dispersion.damping" not in resolved.injected


def test_resolve_dispersion_missing_damping_missing_data():
    """d3-zero has no 3ob damping entry in defaults.json: MISSING_DATA."""
    with pytest.raises(core.Failure) as exc:
        resolve_spec(method="dftb-3", method_args={"dispersion": "d3-zero"})
    assert exc.value.code == "MISSING_DATA"
    assert "damping" in exc.value.message


def test_resolve_structure_alias():
    """A molecule word is mapped to its formula and listed as injected."""
    resolved = resolve_spec(structure={"name": "eau"})
    assert resolved.spec["structure"] == {"name": "H2O"}
    assert "structure.name" in resolved.injected


def test_resolve_canonicalizes_module_alias():
    """The module alias 'optimization' becomes 'optimization-geometry'."""
    resolved = resolve_spec(module="optimization")
    assert resolved.spec["module"] == "optimization-geometry"


def test_sk_set_matches_mio110_dotted_path():
    """The real basis directory "mio-1.1.0" (dots) matches the 3ob entry."""
    sk = core._sk_set({"directory": "/opt/parameters_dftb/mio-1.1.0/skfiles"}, DEFAULTS)
    assert sk is not None
    assert sk["hubbard-derivs"] == {"H": -0.1857, "O": -0.1575}


def test_sk_set_bare_mio1_no_match():
    """The tightened token 'mio-1-1' no longer matches a bare 'mio-1' path."""
    assert core._sk_set({"directory": "/opt/sk/mio-1"}, DEFAULTS) is None


# ----------------------------------------------------------------------
# build_image
# ----------------------------------------------------------------------


def test_build_image_name():
    """A molecule name builds the same atoms every time."""
    a = execute.build_image({"name": "H2O"}, DEFAULTS["molecule-aliases"])
    b = execute.build_image({"name": "eau"}, DEFAULTS["molecule-aliases"])
    assert (a.get_chemical_symbols(), b.get_chemical_symbols()) == (
        ["O", "H", "H"],
        ["O", "H", "H"],
    )


def test_build_image_unknown_name():
    """An unknown molecule is a typed INVALID_SPEC failure."""
    with pytest.raises(core.Failure) as exc:
        execute.build_image({"name": "notamolecule"}, DEFAULTS["molecule-aliases"])
    assert exc.value.code == "INVALID_SPEC"


def test_build_image_missing_file():
    """A missing file is a typed INVALID_SPEC failure."""
    with pytest.raises(core.Failure) as exc:
        execute.build_image({"file": "nope.xyz"})
    assert exc.value.code == "INVALID_SPEC"


def test_build_image_deterministic_hash():
    """The same resolved spec hashes to the same 10-hex workdir name."""
    spec = {"software": "dftb+", "method": "dftb-2", "x": {"b": 1, "a": 2}}
    assert core.spec_hash(spec) == core.spec_hash(copy.deepcopy(spec))
    assert len(core.spec_hash(spec)) == 10


# ----------------------------------------------------------------------
# LLM prompt battery (real: needs an endpoint, PROMPT_CALC_LLM_URL)
# ----------------------------------------------------------------------

LLM_URL = os.environ.get("PROMPT_CALC_LLM_URL")
LLM_API_KEY = os.environ.get("PROMPT_CALC_API_KEY", "no-key")


@pytest.mark.real
@pytest.mark.skipif(LLM_URL is None, reason="PROMPT_CALC_LLM_URL is not set")
class TestPromptBattery:
    """FR/EN prompts pinned to expected specs and vote behavior."""

    def _transcribe(self, prompt):
        from llm import transcribe

        samples = transcribe(prompt, SCHEMA, LLM_API_KEY, LLM_URL)
        assert samples, "no parseable spec from the LLM"
        return samples

    def _voted(self, prompt):
        vote = vote_samples(self._transcribe(prompt))
        assert vote.spec is not None, f"no stable vote for {prompt!r}: {vote.variants}"
        return vote

    def _check(self, prompt, expected):
        """Assert the voted spec carries the expected canonical fields."""
        vote = self._voted(prompt)
        spec = vote.spec
        assert vote.confidence in ("high", "majority", "tie-break")
        # Canonicalize aliases in place (as the pipeline would).
        validate.validate(spec, SCHEMA, spec.get("software") or "dftb+", DEFAULTS, CONFIG)
        for key, value in expected.items():
            if key == "method_args.dispersion":
                got = core._dispersion_value(spec.get("method_args", {}).get("dispersion"))
                assert got == value, f"dispersion: {got!r} != {value!r}"
                continue
            if key.startswith("method_args."):
                got = spec.get("method_args", {}).get(key.removeprefix("method_args."))
                assert got == value, f"{key}: {got!r} != {value!r}"
                continue
            if key == "structure":
                got = str(spec.get("structure", {}).get("name", "")).upper()
                assert got == value["name"].upper(), f"structure.name: {got!r}"
                continue
            assert spec.get(key) == value, f"{key}: {spec.get(key)!r} != {value!r}"
        return vote

    def test_dftb3_eau_d3bj(self):
        vote = self._check(
            "calcul de DFTB 3 sur une molécule d'eau avec dispersion d3-bj",
            {
                "method": "dftb-3",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d3-bj",
            },
        )
        # A stable vote: strict majority of the N draws.
        assert int(vote.count.split("/")[0]) > 2

    def test_sp_dftb2_water_d4(self):
        self._check(
            "sp DFTB2 water d4",
            {
                "method": "dftb-2",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d4",
            },
        )

    def test_dftb3_eau_b3bj_typo(self):
        """A typo in the model is interpreted, and the doubt is voiced."""
        vote = self._check(
            "dftb 3 eau b3-bj",
            {
                "method": "dftb-3",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d3-bj",
            },
        )
        assert vote.ambiguities, "the typo should be reported as an ambiguity"

    def test_optimization_scc_nh3_multiplicity(self):
        self._check(
            "optimisation SCC NH3 multiplicité 4",
            {
                "method": "dftb-2",
                "module": "optimization-geometry",
                "structure": {"name": "NH3"},
                "method_args.multiplicity": 4,
            },
        )

    def test_single_point_dftb2_methanol_d3bj(self):
        self._check(
            "single point DFTB-2 methanol avec d3-bj",
            {
                "method": "dftb-2",
                "module": "single-point",
                "structure": {"name": "CH3OH"},
                "method_args.dispersion": "d3-bj",
            },
        )

    def test_dftb3_eau_sans_dispersion(self):
        """An explicit 'no dispersion' maps to the 'none' value on dftb-3."""
        self._check(
            "DFTB 3 sur une molécule d'eau sans dispersion",
            {
                "method": "dftb-3",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "none",
            },
        )

    def test_sp_dftb3_eau_d4(self):
        self._check(
            "SP DFTB3 eau d4",
            {
                "method": "dftb-3",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d4",
            },
        )

    def test_dftb2_methane_no_dispersion(self):
        """A partial prompt (no dispersion) stays partial: dispersion absent."""
        vote = self._check(
            "calcul DFTB 2 du méthane",
            {
                "method": "dftb-2",
                "module": "single-point",
                "structure": {"name": "CH4"},
            },
        )
        assert core._dispersion_value(vote.spec.get("method_args", {}).get("dispersion")) is None

    def test_opt_dftb3_nh3_d3bj_multiplicity(self):
        self._check(
            "geometric optimization of ammonia with DFTB-3 d3-bj multiplicity 4",
            {
                "method": "dftb-3",
                "module": "optimization-geometry",
                "structure": {"name": "NH3"},
                "method_args.dispersion": "d3-bj",
                "method_args.multiplicity": 4,
            },
        )

    def test_demonnano_dftb2_water(self):
        """A named software is kept in the spec (deMonNano naming)."""
        self._check(
            "run a DFTB 2 single point on water with deMonNano",
            {
                "software": "deMonNano",
                "method": "dftb-2",
                "module": "single-point",
                "structure": {"name": "H2O"},
            },
        )

    def test_sp_dftb2_eau_d3zero(self):
        self._check(
            "single point dftb2 eau d3-zero",
            {
                "method": "dftb-2",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d3-zero",
            },
        )

    def test_sp_dftb2_h2o_charge(self):
        """A stated charge is carried as an int in method_args."""
        self._check(
            "SP DFTB2 H2O charge +1",
            {
                "method": "dftb-2",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.charge": 1,
            },
        )

    def test_opt_dftb2_eau_d4(self):
        self._check(
            "optimisation de la géométrie de l'eau, DFTB-2, dispersion d4",
            {
                "method": "dftb-2",
                "module": "optimization-geometry",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d4",
            },
        )

    def test_td_dftb_h2o_d3bj(self):
        self._check(
            "excited states du H2O en TD-DFTB avec d3-bj",
            {
                "method": "dftb-2",
                "module": "excited-states",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d3-bj",
            },
        )

    def test_alias_scc_dftb_eau_d4(self):
        """The catalog alias 'scc-dftb' is canonicalized to dftb-2."""
        vote = self._check(
            "calcul scc-dftb de l'eau avec dispersion d4",
            {
                "method": "dftb-2",
                "module": "single-point",
                "structure": {"name": "H2O"},
                "method_args.dispersion": "d4",
            },
        )
        assert vote.confidence in ("high", "majority", "tie-break")


# ----------------------------------------------------------------------
# llm.transcribe request shape (no network: urllib is stubbed)
# ----------------------------------------------------------------------


class _FakeResponse:
    """A closed-over context manager standing in for the HTTP response."""

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_transcribe_embeds_spec_schema_in_response_format(monkeypatch):
    """The request sends the spec schema as a json_schema response_format."""
    import llm

    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data)
        content = json.dumps({"method": "dftb-2", "module": "single-point"})
        return _FakeResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    schema = {"methods": {"dftb-2": {}}, "software": {"dftb+": {"alias": [], "handlers": []}}}
    samples = llm.transcribe("sp DFTB2 water", schema, "key", "http://fake/llm", n=1)
    assert len(samples) == 1
    assert captured["body"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "spec", "schema": schema},
    }


def test_transcribe_warns_on_failed_attempt(monkeypatch):
    """A failed draw is discarded with a warning, then redrawn."""
    import llm

    attempts = {"n": 0}

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OSError("connection refused")
        content = json.dumps({"method": "dftb-2", "module": "single-point"})
        return _FakeResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    with pytest.warns(UserWarning, match="draw failed"):
        samples = llm.transcribe("sp DFTB2 water", {}, "key", "http://fake/llm", n=2)
    assert len(samples) == 1
    assert attempts["n"] == 2


# ----------------------------------------------------------------------
# Voting mechanics (no network: synthetic samples)
# ----------------------------------------------------------------------


def _samples(*specs):
    return [(copy.deepcopy(s), {}) for s in specs]


def test_vote_unanimous():
    """N/N identical specs: high confidence, no ambiguity note."""
    spec = make_spec(method="dftb-3", method_args={"dispersion": "d3-bj"})
    vote = vote_samples(_samples(spec, spec, spec, spec, spec))
    assert vote.confidence == "high"
    assert vote.count == "5/5"
    assert vote.spec == spec


def test_vote_majority():
    """3/2 split: the majority spec wins, the minority is voiced with values."""
    spec_a = make_spec(method_args={"dispersion": "d3-bj"})
    spec_b = make_spec(method_args={"dispersion": "d4"})
    vote = vote_samples(_samples(spec_a, spec_a, spec_a, spec_b, spec_b))
    assert vote.confidence == "majority"
    assert vote.count == "3/5"
    assert vote.spec == spec_a
    assert "method_args.dispersion" in vote.fields
    assert (
        "2/5 samples mapped method_args.dispersion to 'd4' instead of 'd3-bj'" in vote.ambiguities
    )


def test_vote_tie():
    """2/2/1 split: no stable vote, the distinct candidates are kept."""
    a = make_spec(method_args={"dispersion": "d3-bj"})
    b = make_spec(method_args={"dispersion": "d4"})
    c = make_spec()
    vote = vote_samples(_samples(a, b, c))
    assert vote.spec is None
    assert vote.confidence == "tie"
    assert len(vote.variants) == 3


def test_vote_ambiguities_union():
    """ambiguities across all samples are unioned."""
    a = make_spec(ambiguities=["note-A"])
    b = make_spec(ambiguities=["note-B"])
    vote = vote_samples(_samples(a, b))
    assert set(vote.ambiguities) == {"note-A", "note-B"}


def test_vote_case_insensitive_tokens():
    """Differently-cased known tokens vote as the same spec."""
    a = make_spec(method="DFTB-2")
    b = make_spec(method="dftb-2")
    vote = vote_samples(_samples(a, b))
    assert vote.confidence == "high"


def test_vote_structure_name_case_insensitive():
    """'H2O' and 'h2o' vote as the same spec (design doc, section 3.3)."""
    a = make_spec(structure={"name": "H2O"})
    b = make_spec(structure={"name": "h2o"})
    vote = vote_samples(_samples(a, b))
    assert vote.confidence == "high"
