# Design plan: `prompt_calc` — prompt-driven calculations on AMAC

Status: design draft — 2026-11-19
Location of the tool: `project/AMAC/tools/prompt_calc/`

## 1. Purpose

Run a quantum-chemistry calculation of any AMAC-supported type from a single
free-text prompt, e.g. *"calcul de DFTB 3 sur une molécule d'eau avec
dispersion b3-bj"*.

Two hard constraints:

1. **Determinism.** The LLM is used *only* to translate the prompt into a
   machine-checkable spec. Every step after the spec is a pure, testable
   Python function. Same resolved spec → byte-identical inputs, same workdir,
   same run.
2. **Minimal dependencies.** Python ≥ 3.12 stdlib + `amac` + `ase` + NumPy
   (all already in `project/.env`). No LangChain, no LLM SDK, no pydantic.

AMAC is the single execution path (catalog validation, input composition,
execution, handlers, provenance). The tool is a thin client, ~500 lines
across four files plus two JSON data tables.

## 2. Architecture

```
prompt ──► [1] TRANSCRIBE (LLM, N samples) ──► spec.json  (voted)
                                                        │
                          [2] VALIDATE  ◄── catalog-derived schema
                                                        │
                          [3] RESOLVE   ◄── defaults.json (explicit table)
                                                        │
                          [4] BUILD IMAGE (ase)
                                                        │
                          [5] EXECUTE (AMAC) ──► workdir/<hash>/ + products
                                                        │
                          [6] REPORT (JSON, typed status)
```

Stages 2–6 are deterministic. Stage 1 is the only non-deterministic step;
it is *sampled N times and voted* (§3.3), and every raw output is persisted.

## 3. Stage 1 — TRANSCRIBE (prompt → spec)

### 3.1 Spec format

The LLM emits one JSON object (schema-constrained decoding, no free text,
no code):

```json
{
  "software": "dftb+",
  "method": "dftb-3",
  "module": "single-point",
  "structure": {"name": "H2O"},
  "method_args": {"dispersion": "d3-bj"},
  "handlers": ["lowest-energy"],
  "ambiguities": ["'b3-bj' is not a valid choice, interpreted as 'd3-bj'"]
}
```

Field rules (part of the system prompt):

- Only fill keys the user mentioned. Everything else is **absent**, not
  default-valued — defaults are the executor's job (§5), never the LLM's.
- Values must come from the catalog `choices`/`aliases`; an unrecognizable
  token goes into `ambiguities` with the interpretation proposed, never
  silently rewritten.
- `software` only if the user named it.
- `structure` is exactly one of `{"name": …}`, `{"xyz": …}`, `{"file": …}`.

### 3.2 Schema and system prompt

`spec_schema.json` is **generated once** from the AMAC catalog
(`gen_schema.py`, output checked in): methods + aliases, modules + aliases,
per-method `mandatory-attribute`/`allowed-attribute` with `choices` →
`enum`, `range` → `minimum/maximum`, `type` → JSON-schema type, nested
`children` → nested objects; plus the handler name list per software.
Single source of truth: the catalog. Nothing re-typed by hand.

System prompt = fixed preamble + schema + alias table + the field rules
above + a worked example pair (prompt → spec). Temperature 0 is **not**
used: the step is sampled instead (§3.3).

### 3.3 Multi-sample interpretation and voting

Instead of one draw, transcribe is **N independent draws at low
temperature** (default `N = 5`, `T = 0.2`, schema-constrained each).

Algorithm:

1. Draw `s_1 … s_N` (sequential; the call is cheap — one short prompt).
2. **Canonicalize** each spec: sort keys, drop empty lists/`null`s,
   normalize case of known tokens (`d3-bj`, `H2O`). Canonical JSON → hash.
3. **Vote on the hash:**
   - **Unanimous (N/N):** accept, confidence `high`.
   - **Majority (strict > N/2):** accept the majority spec, confidence
     `majority`. The minority specs are kept as *variants* and the fields
     on which they disagree are appended to `ambiguities` (e.g.
     `"2/5 samples mapped dispersion to 'd4' instead of 'd3-bj'"`).
   - **No majority (tie):** run **one tie-break round**: re-prompt with the
     prompt + the distinct candidate specs + "pick the one that matches the
     request best, or report which fields are ambiguous". If a majority
     emerges, accept with confidence `tied-break`; otherwise **stop and
     present the distinct candidates to the user** and let the user choose
     or rephrase (CLI interaction; `--yes` turns this into a hard failure
     with code `AMBIGUOUS` — never a silent guess).
4. `ambiguities` across all accepted samples: **union**, so any doubt any
   sample voiced is visible to the user.
5. **Provenance:** store all N raw responses (`llm_samples.json` in the
   workdir) + the vote outcome (`vote: {count: "3/5", fields: [...]}`).

Rationale: at low T, N samples cluster; a stable translation is unanimous,
a genuinely ambiguous prompt splits the vote, and the split is *data* — it
is what flags "the user's request is unclear" instead of a single lucky
(or unlucky) draw deciding. Cost: N × a few hundred tokens.

### 3.4 The LLM client (Variant A only)

`llm.py`, stdlib only: one function

```python
def transcribe(prompt, schema, api_key, url, n=5, temperature=0.2)
    -> list[tuple[dict, dict]]   # (spec, raw_response) × N
```

`urllib.request` POST to any OpenAI-compatible `/chat/completions` with
`response_format` JSON schema. JSON-parse failures are discarded with a
warning and do not count toward N (redraw, up to N total attempts).

**Variant B** (OpenCode session is the interpreter): the same spec format,
schema, voting and storage apply — the agent performs the N draws — and
`llm.py` simply does not exist. The tool then also accepts
`--spec PATH`, which skips stage 1 entirely and is the fully
deterministic entry point for reruns and sharing.

## 4. Stage 2 — VALIDATE

`validate(spec, schema) -> list[SpecError]`, pure function. Checks:

1. Every field present in the spec exists in the schema; enum/alias
   membership for `software`, `method`, `module`, `handlers` (handlers per
   software).
2. Recursive type/range check on `method_args` following `children`
   (e.g. `dispersion.a2` must be a float if `d3-bj`/`d4` selected).
3. `mandatory-attribute` presence **at the right method** — but a missing
   mandatory attribute is *not* an error yet: it is resolvable from
   `defaults.json` (§5). Only *unresolvable* mandates fail here.
4. Cross-field rules: `kpoints` requires a periodic structure;
   `multiplicity` range; `solvation` option shape.

Each `SpecError` carries `field`, `code`, `message`, and — whenever the
schema knows it — the **valid choices**, so the error text is actionable:
`method_args.dispersion: 'b3-bj' not in ['lj-uff','d3-bj','d3-zero','d4',
'model-1','model-2']`.

Retry policy (LLM path only): on failure, send **only the error list**
back ("fix field X; allowed values: …") for at most **2 rounds**. After
that, exit with code `INVALID_SPEC`. No unbounded loops.

## 5. Stage 3 — RESOLVE (defaults, explicit table)

`resolve(spec, defaults, config) -> resolved`, a pure merge, priority:
**user spec > defaults table > hard error**. The LLM never fills defaults;
the table does, and every value it injects is listed in the report.

`defaults.json` contents (small, human-editable, values already validated
by existing AMAC examples):

- `software`: `"dftb+"`.
- `scc`: `{"scc-max": 999, "filling": 50}`.
- `hubbard-derivs` per SK set (e.g. `3ob: {H: -0.1857, O: -0.1575, …}`) —
  DFTB-3 mandatory attribute.
- `dftb-3-conventions`: `h-correction: {value: damping, exponent: 4.0}`.
- `dispersion-damping` per SK set: `d3-bj`/`d4` parameters (DFTB+ has no
  built-in defaults; the manual examples validate these).
- `molecule-aliases`: `{"eau": "H2O", "water": "H2O", "méthane": "CH4", …}`.

Resolution rules:

- Basis directory defaults to the configured software's `basis` from
  `config-amac.json`.
- DFTB-3 without `hubbard-derivs`: inject the table entry **for the
  resolved basis**; if the basis is not in the table → error
  `MISSING_DATA` (never guess U-derivatives).
- Dispersion without damping parameters: inject the table entry; unknown
  (method, dispersion, basis) combination → error `MISSING_DATA`.
- Anything else absent stays absent (software default behavior) — the
  resolved spec records which keys were injected (`resolved.by` list).

## 6. Stage 4 — BUILD IMAGE

```python
def build_image(spec) -> ase.Atoms:
    name → molecule-aliases → ase.build.molecule(name)
    xyz  → ase.io.read(StringIO(xyz), "xyz")
    file → ase.io.read(file)      (paths relative to cwd, must exist)
```

Same spec → same coordinates, every time. (Periodic images: `{"cell": …,
"pbc": …, "positions": …}` branch, same determinism; cell/pbc come from the
spec, never invented.)

## 7. Stage 5 — EXECUTE

```python
spec_hash = sha256(canonical_json(resolved))[:10]
workdir = .run/<software>/<method>/<spec_hash>        # --fresh to bypass
amac.configure_from_file(config)
calc = AMAC(software=resolved["software"], workdir=workdir, label=…)
calc.handler_register(*resolved["handlers"])
calc.parameters_register(method=…, method_args=…, module=…)
calc.run(image)
products = {h: calc.instance.res.product[h] for h in resolved["handlers"]}
```

Properties:

- Identical resolved spec → identical workdir and byte-identical input
  files; reruns are cheap and reproducible.
- `--dry-run`: compose the inputs (AMAC instance composition), write them
  to the workdir, print them, **launch nothing**.
- On failure the workdir is kept as-is (inputs + program logs + stdout) —
  it is the forensic artifact.
- AMAC's own per-software validation (equivalence tables, guards) runs
  inside `parameters_register`/`run` and is the **second, independent**
  safety net behind stage 2 (e.g. DFTB+ frequencies `supported: false`,
  TD-DFTB non-gamma rejection).

## 8. Failure taxonomy

A calculation request can die in six distinct places. Each maps to a typed
code, a detection stage, an exit code, and the artifacts kept. The report
(§9) always carries one of these — a failure is never an unhandled
traceback.

| Code | Meaning | Detected at | Detection | User-facing message (shape) | Exit |
|---|---|---|---|---|---|
| `INVALID_SPEC` | LLM output violates the catalog schema, still after 2 retries | 2 | `validate` | `field: value not in [choices]` | 2 |
| `AMBIGUOUS` | No stable vote (§3.3) and `--yes` given | 1 | vote/tie-break | the distinct candidate specs, pick one | 2 |
| `UNSUPPORTED_CATALOG` | Request is not expressible in the AMAC catalog at all (e.g. "DFT/PBE on dftb+", "CPMD") | 2 | `validate` | "AMAC cannot express <X>; closest supported: …" | 3 |
| `UNSUPPORTED_SOFTWARE` | Catalog-expressible, but the chosen software rejects it (equiv `supported: false`, guard, e.g. frequencies on dftb+, CI-DFTB on dftb+) | 2/5 | `validate` cross-rules / AMAC validation | "supported only by <other software> — rerun with --software <s>?" | 3 |
| `MISSING_DATA` | A mandatory value has no defaults-table entry (hubbard-derivs for unknown SK set, damping for unknown (dispersion, basis)) | 3 | `resolve` | "<field> required for <combo>; not in defaults.json" | 3 |
| `MISSING_BINARY` / `RUNTIME_FAILURE` | AMAC accepted the spec but the run itself failed: binary lacks the feature (no tblite/dftd3 in this build), missing SK file, SCC non-convergence, program crash | 5 | exit status / AMAC exception / handler empty | stage tag: binary vs inputs vs convergence; last relevant log lines; workdir path | 1 |
| `USER_ABORT` | Confirmation refused (ambiguities without `--yes`) | glue | `input()` | — | 4 |

Design rules:

- **No partial side effects:** the workdir is created only after
  `resolve` succeeds; validate failures leave nothing on disk.
- **Convergence policy (deterministic):** no silent retry on SCC
  non-convergence. Report `RUNTIME_FAILURE` with the SCC tail; a retry with
  a different mixer (`broyden`, already cataloged) is a *user* decision via
  an explicit spec field, not a hidden second attempt.
- **Failed runs are recorded too:** the report (and optionally the AMAC
  store) is written for every terminal status, so "what the catalog
  doesn't know yet" is data, not noise.
- `UNSUPPORTED_*` codes feed back into the catalog: they mark where AMAC's
  catalog/equiv is incomplete.

## 9. Report

`products.json` in the workdir + stdout table:

```json
{
  "status": "succeeded",            // or the failure code of §8
  "code": null,                     // failure code, or null
  "vote": {"count": "5/5", "fields": []},
  "ambiguities": ["…"],
  "injected": ["method_args.hubbard-derivs", "method_args.dispersion.damping"],
  "spec_hash": "9f2c…",
  "workdir": ".run/dftb+/dftb-3/9f2c…",
  "products": {"lowest-energy": -76.412345}
}
```

Stdout adds human-friendly values (Hartree + kcal/mol) and the ambiguities
block; a failure prints `code` + message + workdir path.

## 10. Files and layout

```
tools/prompt_calc/
├── prompt_calc.py     # CLI: --prompt / --spec / --dry-run / --yes /
│                      #      --config / --software / --fresh
│                      #   main() = transcribe→validate→resolve→build→execute→report
├── gen_schema.py      # one-shot: catalog/*.json → spec_schema.json
├── spec_schema.json   # checked-in output of gen_schema.py
├── defaults.json      # defaults table (§5)
├── llm.py             # Variant A only: stdlib urllib, N-draw client
└── test/
    ├── test_executor.py    # spec → validate/resolve/build/execute (stub program)
    └── test_prompts.py     # prompt battery → expected spec (LLM path)
```

No new package, no pyproject changes; runs from the AMAC root with the
shared venv.

## 11. Tests

- **Executor (always, no QC binary — AMAC stub-program pattern from
  `test/conftest.py`):**
  - `validate`: each taxonomy trigger (bad enum, bad range, unknown
    software for the handler, kpoints on a molecule) → exact code +
    message.
  - `resolve`: dftb-3 + 3ob basis injects `hubbard-derivs` and
    `h-correction`; unknown basis → `MISSING_DATA`.
  - `execute`: composed inputs contain the expected nodes
    (`HubbardDerivs/N`, D3 damping block, `Charge = 1`); **byte-identical
    inputs across two runs of the same resolved spec**; `--dry-run`
    launches nothing.
  - Failure injection: stub program exit 1 → `RUNTIME_FAILURE` with
    workdir kept; equiv-`supported: false` option →
    `UNSUPPORTED_SOFTWARE` with the correct suggestion.
- **Prompt battery (LLM path):** ~15 FR/EN prompts with realistic typos and
  partials (*"dftb 3 eau b3-bj"*, *"sp DFTB2 water d4"*, *"optimisation
  SCC NH3 multiplicité 4"*), each pinned to an expected spec and expected
  vote behavior; a regression on the translation layer (catches model
  upgrades that change mappings).

## 12. Determinism guarantees (summary)

| Input | Guarantee |
|---|---|
| Same resolved spec | Byte-identical inputs, same workdir hash, same AMAC call sequence |
| Same prompt | N-sample vote makes the spec stable in practice; every draw persisted; a later rerun uses `--spec <workdir>/spec.json` and the LLM is out of the loop |
| Defaults | Only `defaults.json` fills gaps; every injected value listed in the report |
| Failure | Typed code, no silent retry, workdir kept as artifact |

Remaining irreducible non-determinism: inside the QC code itself (e.g. MD
seeds) — a `seed` field will be added to the spec schema for
`molecular-dynamics` before that module is exposed.

## 13. Open decisions

1. ~~Variant B only, or B + A (`llm.py`) from the start?~~
   **Resolved (2026-11-19): ship both.** `--spec PATH` is the deterministic
   entry point (no LLM); `--prompt TEXT` uses `llm.py` (stdlib-urllib client
   to an OpenAI-compatible endpoint, N=5 draws at T=0.2 with the §3.3
   voting/tie-break algorithm).
2. ~~DFTB-3 default dispersion (D3H5 default vs explicit)?~~
   **Resolved (2026-11-19): a bare "dftb 3" with no dispersion is a hard
   error.** Implementation: a validation cross-rule — when the method is
   dftb-3 (and the software is dftb+), `method_args.dispersion` must be
   present, with a value in the catalog choices **plus the explicit string
   "none"** (used only when the user explicitly asked for no dispersion; the
   LLM field rules say so). The executor maps "none" to omitting the
   dispersion attribute. For deMonNano the dispersion key stays optional
   (model-1/model-2); the string "none" on deMonNano is
   `UNSUPPORTED_SOFTWARE` (DISP=1 is a program default, it cannot be
   disabled).
3. ~~Which SK sets enter `defaults.json` initially?~~
   **Resolved (2026-11-19): 3ob / mio-1-1 only** (the user's configured
   DFTB+ basis): hubbard-derivs H -0.1857, O -0.1575; d3-bj
   {s6: 1.0, s8: 0.49, a1: 0.5719, a2: 3.6017}; d4
   {s6: 1.0, s8: 1.1948145, s9: 0.0, a1: 0.6074567, a2: 4.9336133}.
4. Interactive candidate choice on `AMBIGUOUS`: plain CLI `input()` now,
   menu later? (Kept as designed: `input()` index choice now; `--yes` turns a
   tie into a hard `AMBIGUOUS` failure.)
