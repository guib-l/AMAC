# Examples

One folder per software, one concept per script. Run every script from the
AMAC root directory, so that `config-amac.json` and `.run/` are found:

```bash
python examples/pyscf/01_single_point_hf.py
bash examples/pyscf/run_all.sh    # every script of the folder, then the failures
```

Executables, Slater-Koster directories, launcher and timeout come from
`config-amac.json` (see each folder's README). Outputs go to
`.run/<software>/<concept>`.

| Folder | Software | Needs in `config-amac.json` |
|---|---|---|
| [`pyscf/`](pyscf/) | PySCF (in-process) | nothing |
| [`dftbplus/`](dftbplus/) | DFTB+ | `executable`, `basis` |
| [`deMonNano/`](deMonNano/) | deMonNano | `executable`, `basis` (+ `launcher` for MPI) |
| [`orca/`](orca/) | ORCA | `executable` |
| [`openmolcas/`](openmolcas/) | OpenMolcas | `executable`, `env.MOLCAS` |
| [`general/`](general/) | several | multi-software comparisons, benchmarks, `Store` |

Shared structures live in [`data/`](data/).

## Coverage

| | PySCF | DFTB+ | deMonNano | ORCA | OpenMolcas |
|---|:-:|:-:|:-:|:-:|:-:|
| HF | 01 | – | – | 01 | 01 |
| DFT | 02 | – | – | 02 | 02 |
| MP2, CCSD, CCSD(T) | 03 | – | – | 03 | 03, 09 |
| CASSCF | 04 | – | – | 04 | 04, 05 |
| CASPT2, NEVPT2 | – | – | – | – | 10, 11 |
| DFTB-1/2/3 | – | 01, 02 | 01, 02 | – | – |
| CI-DFTB | – | – | 09 | – | – |
| xTB | – | 05 | – | 05 | – |
| Properties | – | 03 | 03 | 06 | 06 |
| Dispersion | 02 | 04 | 04 | 02 | – |
| Optimization | 05 | 06 | 05 | 07 | 07 |
| Frequencies | 06 | – | 06 | 08 | 12 |
| Excited states | 07 | 07 | 07 | 09 | – |
| Transition state | 08 | – | – | 10 | – |
| Molecular dynamics | 09 | 08 | – | 11 | – |
| Solvation | 10 | 09 | – | 12 | 08 |
| Periodic (k-points) | – | 10 | 08 | – | – |
| Parallel run | – | – | 10 | – | – |
| DFTB shell-resolved SCC | – | 11 | 11 | – | – |

Numbers are the script prefixes; `–` means not supported by the asset
(`"supported": false` or absent from its `equiv.json`).
