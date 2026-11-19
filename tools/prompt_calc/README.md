# prompt_calc

Turn a free-text prompt or a JSON spec into an AMAC quantum-chemistry
calculation. The LLM (used only in `--prompt` mode) does exactly one thing:
transcribe the prompt into a **schema-constrained spec** (N independent draws
at low temperature, then a vote). Everything after the spec is deterministic
and pure: **validate → resolve → build image → execute via AMAC → report**.
Same resolved spec → byte-identical inputs, same workdir, same run.

Full design: [`docs/prompt_calc_design.md`](../../docs/prompt_calc_design.md).

## Requirements / installation

- **Python ≥ 3.12** (`pyproject.toml`: `requires-python = ">=3.12"`).
- **No new dependencies.** The tool is stdlib-only on top of what AMAC
  already needs: `amac` itself (editable in the workspace venv), `ase`,
  `numpy`. No LLM SDK, no pip install of this tool.
- **No installation step required.** `prompt_calc.py` is a script in the
  checkout; you only need `amac` to be importable (it is, editable, in the
  workspace venv).

Run everything from the AMAC project root (`/AMAC`) with the workspace venv:

```sh
# either activate it ...
source .env/bin/activate
# ... or just call its python directly
python3 tools/prompt_calc/prompt_calc.py --help
```

`--config` defaults to `config-amac.json` in the AMAC root, which must
configure the target software (executable + basis directory).

## Quick start

### Spec-driven (no LLM, fully deterministic)

Write `spec.json` in the AMAC root:

```json
{
  "software": "dftb+",
  "method": "dftb-2",
  "module": "single-point",
  "structure": {"name": "H2O"},
  "handlers": ["lowest-energy"]
}
```

Compose the inputs and launch nothing:

```sh
python3 tools/prompt_calc/prompt_calc.py --spec spec.json --dry-run
```

This prints the report JSON and the composed input files, and writes them to
`.run/dftb+/dftb-2/<hash>/`. Drop `--dry-run` to actually launch the
configured dftb+ executable:

```sh
python3 tools/prompt_calc/prompt_calc.py --spec spec.json
```

### Prompt-driven (LLM transcribes, then the same pipeline)

```sh
python3 tools/prompt_calc/prompt_calc.py \
  --prompt "calcul de DFTB 3 sur une molécule d'eau avec dispersion d3-bj" \
  --llm-url <OPENAI_COMPATIBLE_URL> \
  --api-key-env <VAR> \
  --llm-model <model>
```

`--llm-url` is any OpenAI-compatible `/chat/completions` endpoint;
`--api-key-env VAR` reads the key from environment variable `VAR`
(`--api-key <key>` works too); `--llm-model` is optional. Note the dftb-3
rule: the prompt must state an explicit dispersion model (or "sans
dispersion" → `"none"`); a bare "dftb 3" with no dispersion is a hard error.

## The spec format

| Field | Meaning |
|---|---|
| `software` | `dftb+` or `deMonNano` (name or alias); if absent, the `defaults.json` default (`dftb+`) is injected and listed in `injected` |
| `method` | Catalog method, e.g. `dftb-2`, `dftb-3`, `ci-dftb` (aliases accepted: `scc-dftb`, `dftb3`, …) |
| `module` | Catalog module, e.g. `single-point`, `optimization-geometry` (aliases: `sp`, `opt`, …) |
| `structure` | Exactly one of `{"name": "<formula>"}`, `{"xyz": "<xyz text>"}`, `{"file": "<path>"}` (or a periodic `cell`/`positions`/`pbc`/`symbols` block) |
| `method_args` | Method attributes (`dispersion`, `charge`, `multiplicity`, `basis`, …); values from the catalog choices/aliases |
| `module_args` | Module attributes (same rules) |
| `options` | Cross-cutting options, e.g. `{"solvation": {...}}` |
| `handlers` | Per-software handler names, e.g. `["lowest-energy"]` |
| `ambiguities` | LLM only: short notes about every interpretation doubt |

Rules:

- **Only keys the user mentioned** are filled in by the LLM; everything else
  is absent, not default-valued.
- **Defaults come from `defaults.json`** at the resolve stage (basis
  directory, `scc`/`filling`, dftb-3 `hubbard-derivs` + `h-correction` for
  known SK sets, D3/D4 damping). Every injected key is listed in the report
  `injected` field.
- **dftb-3 on dftb+ requires an explicit `method_args.dispersion`**: a
  catalog choice (`d3-bj`, `d3-zero`, `d4`, …) or the explicit string
  `"none"` when no dispersion was asked. `"none"` on deMonNano is
  `UNSUPPORTED_SOFTWARE` (its dispersion is a program default).

## CLI flags

| Flag | Description |
|---|---|
| `--prompt TEXT` | Free-text request, translated by an LLM (N=5 draws + vote). One of `--prompt`/`--spec` is required |
| `--spec PATH` | JSON spec file (deterministic entry point, no LLM) |
| `--dry-run` | Compose the inputs, write them to the workdir, print them, launch nothing |
| `--yes` | Never ask; an ambiguous vote (tie) becomes a hard `AMBIGUOUS` failure |
| `--config PATH` | AMAC configuration file (default `config-amac.json`) |
| `--software NAME` | Software override (`dftb+`, `deMonNano`) |
| `--fresh` | New timestamped workdir even if the spec hash already exists |
| `--llm-url URL` | OpenAI-compatible `/chat/completions` endpoint (for `--prompt`) |
| `--api-key KEY` | API key of the LLM endpoint |
| `--api-key-env VARNAME` | Read the API key from this environment variable |
| `--llm-model MODEL` | Model name sent to the endpoint (optional) |

## Determinism & reproducibility

- The workdir is `.run/<software>/<method>/<spec_hash>`, where `spec_hash`
  is the first 10 hex chars of the sha256 of the **canonical resolved spec**.
- Same resolved spec → same workdir name and **byte-identical input files**;
  reruns are cheap and reproducible.
- `--fresh` creates a new timestamped (microsecond-resolution) workdir
  instead of reusing the hash directory.
- To rerun a previous calculation without the LLM:
  `--spec <workdir>/spec.json` — the voted, resolved spec is on disk, so the
  LLM is entirely out of the loop.

## Reports & outputs

Everything lands in the workdir:

- `spec.json` — the resolved spec (what was actually composed).
- the composed inputs (e.g. `dftb_in.hsd`, `geo.gen`) and, after a real run,
  the program logs — **kept on failure as the forensic artifact**.
- `products.json` — the report, written for **every** terminal status.
- `llm_samples.json` — the N raw LLM responses (prompt path only); when a
  vote fails before any workdir exists, the raw samples stay in the report
  itself.

Report shape (`products.json` / stdout):

```json
{
  "status": "succeeded",
  "code": null,
  "message": null,
  "vote": {"count": "5/5", "confidence": "high", "fields": []},
  "ambiguities": [],
  "injected": ["method_args.basis.directory", "method_args.scc-max"],
  "spec_hash": "e1344255c4",
  "workdir": ".run/dftb+/dftb-2/e1344255c4",
  "products": {"lowest-energy": -76.412345}
}
```

On failure, `status` and `code` carry the failure code, `message` the
actionable text (with a `--software` suggestion when one is known), and
`workdir` the forensic path.

## Exit codes / failure codes

| Code | Meaning | Exit |
|---|---|---|
| `succeeded` | calculation (or dry run) ok | 0 |
| `RUNTIME_FAILURE` | AMAC accepted the spec but the run failed (binary, crash, SCC non-convergence, empty handler product) | 1 |
| `INVALID_SPEC` | spec/LLM output violates the catalog schema | 2 |
| `AMBIGUOUS` | no stable LLM vote and `--yes` was given | 2 |
| `UNSUPPORTED_CATALOG` | request not expressible in the AMAC catalog at all | 3 |
| `UNSUPPORTED_SOFTWARE` | catalog-expressible, but the chosen software rejects it | 3 |
| `MISSING_DATA` | a mandatory value has no `defaults.json` entry (hubbard-derivs, damping) | 3 |
| `USER_ABORT` | the user refused to proceed (ambiguities without `--yes`) | 4 |

A failure is never an unhandled traceback.

## Testing

`pytest -q -m "not real"` (from the AMAC root) runs the offline suite —
no network, no QC binaries (stub programs stand in for dftb+). The 15-prompt
LLM battery is `real`-marked and runs only with `PROMPT_CALC_LLM_URL` set
(`PROMPT_CALC_API_KEY` optional, default `"no-key"`): `pytest -m real`.
