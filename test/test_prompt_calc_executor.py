"""Tests of the prompt_calc executor (stage 5) on the DFTB+ asset.

Uses the stub-program pattern of test/conftest.py: a fake executable stands
in for dftb+, so nothing real is run. No network, no QC binary.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

import amac.config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "prompt_calc"))  # noqa: E402

import core  # noqa: E402
import execute  # noqa: E402
import prompt_calc as pc  # noqa: E402
import resolve  # noqa: E402

SCHEMA = core.load_schema()
DEFAULTS = core.load_defaults()


def dftb3_spec():
    """A dftb-3 water single-point spec (3ob hubbard derivs, d3-bj, charge 1)."""
    return {
        "software": "dftb+",
        "method": "dftb-3",
        "module": "single-point",
        "structure": {"name": "H2O"},
        "method_args": {"charge": 1, "dispersion": "d3-bj"},
        "handlers": ["lowest-energy"],
    }


def dftb2_spec():
    """A dftb-2 water single-point spec."""
    return {
        "software": "dftb+",
        "method": "dftb-2",
        "module": "single-point",
        "structure": {"name": "H2O"},
        "method_args": {},
        "handlers": ["lowest-energy"],
    }


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Offline AMAC configuration: stub dftb+ executable, 3ob-like basis."""
    basis = tmp_path / "sk" / "mio-1-1"
    basis.mkdir(parents=True)
    fake = tmp_path / "dftbplus-stub"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    cfg = {
        "software": {
            "dftb+": {"executable": str(fake), "basis": str(basis)},
            "deMonNano": {"executable": str(fake), "basis": str(basis)},
        }
    }
    monkeypatch.setattr(amac.config, "CONFIGURE", cfg)
    return cfg


def run_pipeline(spec, config, run_root, **kwargs):
    """resolve -> build image -> execute, the deterministic stages of the CLI."""
    resolved = resolve.resolve(spec, DEFAULTS, config, SCHEMA["aliases"])
    image = execute.build_image(resolved.spec["structure"], DEFAULTS["molecule-aliases"])
    return execute.execute(resolved, image, config, run_root=run_root, **kwargs)


def test_composed_inputs_expected_nodes(config, tmp_path):
    """The composed DFTB+ input holds the expected HSD nodes (dry run)."""
    execution = run_pipeline(dftb3_spec(), config, tmp_path / "run", dry_run=True)
    workdir = execution.workdir
    assert workdir.name == core.spec_hash(
        resolve.resolve(dftb3_spec(), DEFAULTS, config, SCHEMA["aliases"]).spec
    )
    hsd = (workdir / "dftb_in.hsd").read_text(encoding="utf-8")
    assert "ThirdOrderFull = Yes" in hsd
    assert "HubbardDerivs {" in hsd
    assert "H = -0.1857" in hsd
    assert "O = -0.1575" in hsd
    assert "HCorrection = Damping {" in hsd
    assert "Exponent = 4.0" in hsd
    assert "Dispersion = SimpleDftD3 {" in hsd
    assert "s8 = 0.49" in hsd
    assert "a1 = 0.5719" in hsd
    assert "a2 = 3.6017" in hsd
    assert "Charge = 1" in hsd
    assert "MaxSccIterations = 999" in hsd
    assert (workdir / "geo.gen").is_file()
    assert (workdir / "spec.json").is_file()
    assert execution.products == {}


def test_inputs_byte_identical_across_runs(config, tmp_path):
    """The same resolved spec gives the same hash and byte-identical inputs."""
    first = run_pipeline(dftb3_spec(), config, tmp_path / "a", dry_run=True)
    second = run_pipeline(dftb3_spec(), config, tmp_path / "b", dry_run=True)
    assert first.workdir.name == second.workdir.name
    for name in ("dftb_in.hsd", "geo.gen"):
        assert (first.workdir / name).read_bytes() == (second.workdir / name).read_bytes()


def test_fresh_appends_timestamp(config, tmp_path):
    """--fresh gives a new timestamped workdir; without it the hash dir is reused."""
    plain = run_pipeline(dftb2_spec(), config, tmp_path / "run", dry_run=True)
    again = run_pipeline(dftb2_spec(), config, tmp_path / "run", dry_run=True)
    assert plain.workdir == again.workdir
    fresh = run_pipeline(dftb2_spec(), config, tmp_path / "run", dry_run=True, fresh=True)
    assert fresh.workdir != plain.workdir
    assert fresh.workdir.is_dir()


def test_dry_run_launches_nothing(tmp_path, monkeypatch):
    """--dry-run composes the inputs but never launches the executable."""
    marker = tmp_path / "launched"
    fake = tmp_path / "stub"
    fake.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
    fake.chmod(0o755)
    basis = tmp_path / "sk"
    basis.mkdir()
    cfg = {"software": {"dftb+": {"executable": str(fake), "basis": str(basis)}}}
    monkeypatch.setattr(amac.config, "CONFIGURE", cfg)
    execution = run_pipeline(dftb2_spec(), cfg, tmp_path / "run", dry_run=True)
    assert (execution.workdir / "dftb_in.hsd").is_file()
    assert not marker.exists()


def test_stub_exit1_runtime_failure_keeps_workdir(tmp_path, monkeypatch):
    """A stub program exiting 1 is RUNTIME_FAILURE; the workdir is kept."""
    fake = tmp_path / "stub"
    fake.write_text("#!/bin/sh\necho 'SCC did not converge'\nexit 1\n")
    fake.chmod(0o755)
    basis = tmp_path / "sk"
    basis.mkdir()
    cfg = {"software": {"dftb+": {"executable": str(fake), "basis": str(basis)}}}
    monkeypatch.setattr(amac.config, "CONFIGURE", cfg)
    with pytest.raises(core.Failure) as exc:
        run_pipeline(dftb2_spec(), cfg, tmp_path / "run")
    failure = exc.value
    assert failure.code == "RUNTIME_FAILURE"
    assert "workdir" in failure.message
    workdir = failure.workdir
    assert workdir is not None
    assert (workdir / "dftb_in.hsd").is_file()
    assert (workdir / "geo.gen").is_file()
    assert (workdir / "dftb.out").is_file()


def test_fresh_collision_safe(config, tmp_path):
    """Two fresh runs in the same instant get distinct workdirs."""
    first = run_pipeline(dftb2_spec(), config, tmp_path / "run", dry_run=True, fresh=True)
    second = run_pipeline(dftb2_spec(), config, tmp_path / "run", dry_run=True, fresh=True)
    assert first.workdir != second.workdir
    assert (second.workdir / "spec.json").is_file()


def test_stub_empty_handler_product_runtime_failure(tmp_path, monkeypatch):
    """A finished run with an empty handler product is RUNTIME_FAILURE."""
    tag = tmp_path / "results.tag"
    tag.write_text("mermin_energy :real:0:\n -0.407771933677040E+001\n", encoding="utf-8")
    fake = tmp_path / "stub"
    fake.write_text(f"#!/bin/sh\ncp {tag} results.tag\nexit 0\n")
    fake.chmod(0o755)
    basis = tmp_path / "sk"
    basis.mkdir()
    cfg = {"software": {"dftb+": {"executable": str(fake), "basis": str(basis)}}}
    monkeypatch.setattr(amac.config, "CONFIGURE", cfg)
    spec = dftb2_spec()
    spec["handlers"] = ["lowest-energy", "forces"]
    with pytest.raises(core.Failure) as exc:
        run_pipeline(spec, cfg, tmp_path / "run")
    failure = exc.value
    assert failure.code == "RUNTIME_FAILURE"
    assert "no product for handler(s): forces" in failure.message
    assert failure.workdir is not None
    assert (failure.workdir / "results.tag").is_file()


# ----------------------------------------------------------------------
# _pipeline: report and provenance persistence (design doc, sections 3.3/8/9)
# ----------------------------------------------------------------------


def pipeline_run(tmp_path, monkeypatch, spec, config, extra=()):
    """_pipeline() on a spec file and a config file written into tmp_path."""
    monkeypatch.chdir(tmp_path)  # the workdir root is the relative .run/
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    args = pc._parse_args(["--spec", str(spec_path), "--config", str(config_path), *extra])
    return pc._pipeline(args)


def test_dry_run_writes_products_report(config, tmp_path, monkeypatch):
    """A successful dry-run writes products.json (status, code) in the workdir."""
    report = pipeline_run(tmp_path, monkeypatch, dftb2_spec(), config, ("--dry-run",))
    assert report["status"] == "succeeded"
    assert report["code"] is None
    products = Path(report["workdir"]) / "products.json"
    assert products.is_file()
    stored = json.loads(products.read_text(encoding="utf-8"))
    assert stored["status"] == "succeeded"
    assert stored["code"] is None
    assert stored["workdir"] == report["workdir"]


def test_stub_failure_writes_products_report(tmp_path, monkeypatch):
    """A stub-failure run writes products.json carrying the failure code."""
    fake = tmp_path / "stub"
    fake.write_text("#!/bin/sh\necho 'SCC did not converge'\nexit 1\n")
    fake.chmod(0o755)
    basis = tmp_path / "sk"
    basis.mkdir()
    cfg = {"software": {"dftb+": {"executable": str(fake), "basis": str(basis)}}}
    monkeypatch.setattr(amac.config, "CONFIGURE", cfg)
    report = pipeline_run(tmp_path, monkeypatch, dftb2_spec(), cfg)
    assert report["status"] == "RUNTIME_FAILURE"
    assert report["code"] == "RUNTIME_FAILURE"
    products = Path(report["workdir"]) / "products.json"
    assert products.is_file()
    stored = json.loads(products.read_text(encoding="utf-8"))
    assert stored["status"] == "RUNTIME_FAILURE"
    assert stored["code"] == "RUNTIME_FAILURE"


def test_pipeline_llm_samples_persisted(config, tmp_path, monkeypatch):
    """The raw LLM responses are written to llm_samples.json in the workdir."""
    import llm

    spec = {
        "method": "dftb-2",
        "module": "single-point",
        "structure": {"name": "H2O"},
        "handlers": ["lowest-energy"],
    }

    def fake_transcribe(prompt, schema, api_key, url, model=None, n=5, temperature=0.2):
        return [(copy.deepcopy(spec), {"attempt": i}) for i in range(5)]

    monkeypatch.setattr(llm, "transcribe", fake_transcribe)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    args = pc._parse_args(
        [
            "--prompt",
            "sp dftb2 water",
            "--llm-url",
            "http://fake/llm",
            "--api-key",
            "test-key",
            "--config",
            str(config_path),
            "--dry-run",
            "--yes",
        ]
    )
    report = pc._pipeline(args)
    assert report["status"] == "succeeded"
    samples_path = Path(report["workdir"]) / "llm_samples.json"
    assert samples_path.is_file()
    assert json.loads(samples_path.read_text(encoding="utf-8")) == [
        {"attempt": i} for i in range(5)
    ]


def test_pipeline_llm_samples_in_report_without_workdir(tmp_path, monkeypatch):
    """A vote that fails before any workdir exists keeps the raw samples
    in the report (the abort message)."""
    import llm

    def fake_transcribe(prompt, schema, api_key, url, model=None, n=5, temperature=0.2):
        base = {"method": "dftb-2", "module": "single-point", "structure": {"name": "H2O"}}
        specs = [
            {**base, "method_args": {"dispersion": "d3-bj"}},
            {**base, "method_args": {"dispersion": "d4"}},
            dict(base),
        ]
        round_ = "tie-break" if "candidate" in prompt else "first"
        return [(copy.deepcopy(s), {"round": round_}) for s in specs]

    monkeypatch.setattr(llm, "transcribe", fake_transcribe)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"software": {"dftb+": {"executable": "x", "basis": str(tmp_path / "sk")}}}),
        encoding="utf-8",
    )
    args = pc._parse_args(
        [
            "--prompt",
            "dftb2 water dispersion",
            "--llm-url",
            "http://fake/llm",
            "--api-key",
            "test-key",
            "--config",
            str(config_path),
            "--yes",
        ]
    )
    report = pc._pipeline(args)
    assert report["status"] == "AMBIGUOUS"
    assert report["workdir"] is None
    assert not (tmp_path / ".run").exists()
    assert [raw["round"] for raw in report["llm_samples"]] == ["first"] * 3 + ["tie-break"] * 3


def test_equiv_unsupported_module_suggestion(config, tmp_path):
    """An equiv supported: false module is UNSUPPORTED_SOFTWARE with a hint."""
    spec = dftb2_spec()
    spec["module"] = "frequencies"
    with pytest.raises(core.Failure) as exc:
        run_pipeline(spec, config, tmp_path / "run", dry_run=True)
    failure = exc.value
    assert failure.code == "UNSUPPORTED_SOFTWARE"
    assert "deMonNano" in failure.message
    assert "--software deMonNano" in failure.message


def test_demonnano_none_dispersion_unsupported(config, tmp_path):
    """'none' on deMonNano is UNSUPPORTED_SOFTWARE even at the execute stage."""
    spec = {
        "software": "deMonNano",
        "method": "dftb-2",
        "module": "single-point",
        "structure": {"name": "H2O"},
        "method_args": {"dispersion": "none"},
        "handlers": ["lowest-energy"],
    }
    # Deliberately bypass validate: the executor must not silently drop it.
    with pytest.raises(core.Failure) as exc:
        run_pipeline(spec, config, tmp_path / "run", dry_run=True)
    assert exc.value.code == "UNSUPPORTED_SOFTWARE"
    assert "deMonNano" in exc.value.message
    assert exc.value.workdir is not None
