# prompt_calc — how it works

Internal walkthrough of the tool. Usage and installation: see `README.md`.

## 1. Big picture

The LLM is a **translation function**: it reads a free-text request and emits a machine-checkable JSON
spec, nothing more. It is the *only* non-deterministic step — and even it is sampled (N draws) and
voted on. Everything after the spec is a pure, deterministic pipeline: the same resolved spec always
gives the same inputs, workdir, and AMAC call sequence. `--spec` skips stage 1 entirely, so a rerun
is fully reproducible offline.

```
prompt ──► [1] TRANSCRIBE (LLM, N=5 draws, T=0.2, vote) ──► spec
                        (skipped with --spec; then: spec file)
                                                            │
        [2] VALIDATE ◄── spec_schema.json (generated from the catalog)
                                                            │
        [3] RESOLVE  ◄── defaults.json + config-amac.json
                                                            │
        [4] BUILD IMAGE (ase)
                                                            │
        [5] EXECUTE (AMAC: compose inputs → run → handlers)
                                                            │
        [6] REPORT (products.json + stdout)
```

`_pipeline(args)` runs the six stages in order and always ends in a typed report — a failure is never a traceback.

## 2. Stage 1 — TRANSCRIBE (`_llm_stage`, `llm.transcribe`, `vote_samples`)

`llm.transcribe` posts the prompt to an OpenAI-compatible endpoint **N=5 times** (T=0.2). Each draw
is schema-constrained: the actual `spec_schema.json` is embedded in the request's `response_format`
(`json_schema`), not hinted at. The system prompt (`build_system_prompt`) is a fixed preamble +
schema + alias table + two worked examples, with the field rules: fill **only keys the user
mentioned**; unknown tokens go into `ambiguities`, never silently rewritten; `software` only if the
user named it. A failed draw (network, HTTP, JSON parse, non-object) is discarded with a
`warnings.warn` and redrawn; zero parseable draws → `INVALID_SPEC`.

Each accepted draw is canonicalized by `_normalize_spec` (lower-cased software/method/module/handler
tokens, upper-cased `structure.name`, lower-cased string `dispersion`, empties dropped) and grouped
by the sha256 of its canonical JSON. `vote_samples` then decides:

```
N draws ──► canonicalize + group by hash
                │
                ├─ one group has all N ───────────► accept, confidence "high"
                ├─ strict majority (len(best) > N/2)► accept the majority spec,
                │   confidence "majority"; one note per disagreed field:
                │   "k/N samples mapped <field> to <minority> instead of <majority>"
                └─ tie ──► ONE tie-break round (_tie_break: re-prompt with the
                        │  distinct candidates, N=1)
                        ├─ a known candidate wins ──► accept, "tie-break"
                        └─ still tied
                                ├─ --yes ───────────► fail AMBIGUOUS (exit 2)
                                └─ interactive ─────► _ask_candidate: user picks an
                                                      index (confidence "user") or
                                                      aborts (USER_ABORT, exit 4)
```

`ambiguities` from every sample (including the minority notes) are **unioned**; without `--yes` the
user confirms them via `_confirm` (a refusal — or any non-TTY — is `USER_ABORT`). Provenance: all N
raw responses are kept and written to `llm_samples.json` in the workdir, or into the report itself
when the vote dies before any workdir exists.

Concrete before/after (the README's example prompt):

```
prompt: "calcul de DFTB 3 sur une molécule d'eau avec dispersion d3-bj"

voted spec (one of the N draws, after the vote):
{
  "method": "dftb-3",
  "module": "single-point",
  "structure": {"name": "H2O"},
  "method_args": {"dispersion": "d3-bj"},
  "ambiguities": []
}
```

(`software` is absent — the user did not name it; `_pipeline` fills the `defaults.json` default and lists it in `injected`.)

## 3. Stage 2 — VALIDATE (`validate` and its `_check_*` helpers)

`validate(spec, schema, software, defaults, config)` is a pure function that canonicalizes names in
place and returns a list of `SpecError`s. It checks:

- unknown top-level spec field → `INVALID_SPEC`;
- `software`/`method`/`module` against the schema, alias-tolerant, any case; unknown →
  `UNSUPPORTED_CATALOG`, canonical name written back;
- **per-software support** via the assets' equivalence tables (`supporting_software_for`,
  `_equiv_tables`): equiv `supported: false` for the chosen software → `UNSUPPORTED_SOFTWARE`, with
  a `--software` hint when another software supports it;
- `handlers` must belong to the software (per-software lists);
- `structure` is exactly one of `{name}`, `{xyz}`, `{file}` (or a periodic
  `cell`/`positions`/`pbc`/`symbols` block);
- every `method_args`/`module_args`/`options` attribute: known, right type, in range, in choices
  (aliases accepted for data lists), children checked (e.g. `dispersion.damping` keys);
- a missing **mandatory** attribute is an error only if no source can fill it: `MISSING_DATA`
  (resolvable from defaults/config) or `INVALID_SPEC`;
- dispersion cross-rules (`_check_dispersion`): the model must exist for the software's DFTB family;
  `"none"` is dftb+-only;
- cross-field rules (`_check_cross_rules`): `kpoints` needs a periodic structure; **dftb-3 on dftb+
  requires an explicit `method_args.dispersion`** (catalog choice or `"none"`).

The schema it checks against, `spec_schema.json`, is **generated once from the AMAC catalog** by
`gen_schema.py` (methods, modules, options, aliases, attribute rules, per-software handlers) — the
catalog is the single source of truth; re-run the generator after a catalog change. Validation runs
before anything touches the filesystem: a failed stage 2 writes **nothing** to disk.

## 4. Stage 3 — RESOLVE (`resolve` and its `_resolve_*` helpers)

Priority rule: **user spec > defaults.json > hard error** (a `Failure` with `MISSING_DATA`; the
table never guesses). A bare dftb-3 spec with a config whose dftb+ basis is `.../mio-1.1.0/skfiles`
gets completed like this:

```
before (validated spec):                     after (resolved.spec):
  method_args: {dispersion: "d3-bj"}    →    method_args:
                                              dispersion: {value: "d3-bj", s6: 1.0,
                                                s8: 0.49, a1: 0.5719, a2: 3.6017}
                                              basis: {directory: ".../mio-1.1.0/skfiles"}
                                              hubbard-derivs: {H: -0.1857, O: -0.1575}
                                              h-correction: {value: damping, exponent: 4.0}
                                              scc-max: 999, filling: 50
```

`_resolve_basis` takes the configured basis directory (missing → `MISSING_DATA`); `_sk_set`
matches it (dots normalized to dashes, so `mio-1.1.0` matches the token `mio-1-1`) against the
`sk-sets` table; `_resolve_dftb3` injects `hubbard-derivs` **from that SK entry** (unknown SK set →
`MISSING_DATA` — never guess U-derivatives) and `h-correction` from `dftb-3-conventions`;
`_resolve_scc` injects `scc-max`/`filling` for the SCC methods (`dftb-2`, `dftb-3`, `ci-dftb`);
`_resolve_dispersion` expands a D3/D4 model string with the SK set's damping (dftb+ has no
built-in defaults); `_resolve_structure` maps molecule words (`eau` → `H2O`). **Every injected key
is listed** in `Resolved.injected` and appears in the report's `injected`.

## 5. Stage 4 — BUILD IMAGE (`build_image`)

```
{"name": ...}  → molecule-aliases → ase.build.molecule(name)
{"xyz": ...}   → ase.io.read(StringIO(xyz), "xyz")
{"file": ...}  → ase.io.read(path)          (file must exist)
{cell, positions, pbc, symbols} → ase.Atoms(...)
```

Any failure is a typed `INVALID_SPEC`. Same spec → same coordinates, every time.

## 6. Stage 5 — EXECUTE (`execute`, `compose`, `make_workdir`)

`compose` drives AMAC with a fixed call sequence:

```
compose(resolved, image, config, run_root, fresh)
  ├─ make_workdir(spec, run_root, fresh)     .run/<software>/<method>/<hash>/
  │                                          + writes the resolved spec.json
  ├─ amac.configure(config)                  process-wide configuration
  ├─ _new_calc(spec, workdir)                 AMAC(software, workdir, label)
  ├─ calc.handler_register(*handlers)         one call, all handlers
  ├─ calc.parameters_register(method, method_args, module, module_args, options)
  ├─ calc.instance.props(image=image)
  ├─ calc._soft.collect(instance)             catalog validation, equiv tables,
  │                                          asset guards (may raise)
  └─ calc._soft.prepare(instance)             writes the input files
                                              (e.g. geo.gen + dftb_in.hsd)

execute()  ── if not dry_run:
  └─ calc.run(image)                          launch, parse the output,
                                              apply the handlers
```

The workdir is `.run/<software>/<method>/<spec_hash>` where
`spec_hash = sha256(canonical_json(resolved_spec))[:10]`. The hash depends only on the resolved
spec and the whole sequence is a pure function of it — hence **byte-identical inputs and the same
workdir on every rerun**. `--fresh` appends a microsecond stamp (plus a numeric suffix on
collision). `--dry-run` stops after `prepare`: inputs are composed through the *same* `collect`/
`prepare` path a real run uses, but nothing launches and `products` stays empty.

Rejections inside `compose` are typed: `NotImplementedError` (equiv `supported: false`) →
`UNSUPPORTED_SOFTWARE` with a `--software` suggestion (`_unsupported_message`); `CatalogError`/
`KeyError` → `INVALID_SPEC`; `ValueError` (asset guard, e.g. missing D3 damping, `"none"`
dispersion on deMonNano) → `UNSUPPORTED_SOFTWARE`. After a real run, an AMAC error (`AmacError`:
non-zero exit, timeout, unparseable output) is `RUNTIME_FAILURE`, and so is a run that finished but
left a **registered handler's product empty or None** (`_is_empty_product`) — a "success" with
`products: {handler: null}` never happens.

## 7. Stage 6 — REPORT (`make_report`, `write_report`, `_print_report`)

`make_report` assembles the report; `write_report` writes it to `products.json` **for every
terminal status**; `_print_report` prints the report JSON, the composed inputs on `--dry-run`, and
product values (`lowest-energy` in Hartree + kcal/mol).

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

Workdir contents — **success**: `spec.json`, composed inputs, program logs, `products.json` (plus `llm_samples.json` on the prompt path).
**Failure**: the same, kept as-is — inputs + logs + partial outputs are the forensic artifact; `products.json` carries
`status`/`code` = the failure code and `message` = the actionable text.

## 8. Where it can fail

The stage functions above raise these typed `Failure`s:

```
[1] TRANSCRIBE    INVALID_SPEC  no parseable spec / --llm-url / api key missing
                    AMBIGUOUS   tie survived the tie-break and --yes was given
                    USER_ABORT  user declined ambiguities / chose no candidate
[2] VALIDATE      INVALID_SPEC  schema violation (type, range, choice, shape)
                    UNSUPPORTED_CATALOG   not expressible in the catalog at all
                    UNSUPPORTED_SOFTWARE  expressible, software refuses it (equiv
                                          supported: false) — with a --software hint
                    MISSING_DATA          mandatory attribute no source can fill
[3] RESOLVE       MISSING_DATA  basis / hubbard-derivs / damping absent from
                                          defaults.json or the configuration
[5] EXECUTE       UNSUPPORTED_SOFTWARE / INVALID_SPEC   (AMAC validation, above)
                    RUNTIME_FAILURE  program exit != 0, crash, unparseable output,
                                          empty handler product, AMAC unconfigurable
```

Exit codes: `0` ok · `1` RUNTIME_FAILURE · `2` INVALID_SPEC / AMBIGUOUS ·
`3` UNSUPPORTED_CATALOG / UNSUPPORTED_SOFTWARE / MISSING_DATA · `4` USER_ABORT.

Three rules: **no partial side effects** (the workdir is created only after `resolve` succeeds —
stages 1–3 leave nothing on disk); **no silent retry** (SCC non-convergence is reported; a retry
with a different mixer is a user decision made through the spec); **failed runs are recorded too**
(the report is written for every terminal status).

## 9. Determinism guarantees

| Input | Guarantee |
|---|---|
| Same resolved spec | Same `spec_hash` → same workdir, byte-identical inputs, same AMAC call sequence |
| Same prompt | The N-vote makes the spec stable in practice; all raw draws persisted (`llm_samples.json`); a rerun is `--spec <workdir>/spec.json`, LLM out of the loop |
| Defaults | Only `defaults.json` fills gaps; every injected key listed in `injected` |
| Failure | Typed code, no silent retry, workdir kept as the artifact |
| Inside the QC code | The one irreducible non-determinism (e.g. MD seeds); a `seed` field is planned for the spec |

## 10. See also

`README.md` for usage; `docs/prompt_calc_design.md` for the full design rationale.
