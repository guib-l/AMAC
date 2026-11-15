# deMonNano examples

`config-amac.json`:

```json
"deMonNano": {
  "executable": "/absolute/path/to/deMon.x",
  "basis": "/absolute/path/to/basis",
  "launcher": ["/usr/bin/mpirun", "-np", "{process_unit}"],
  "timeout": 600
}
```

`basis` is the Slater-Koster directory (BIO parameters); `launcher` is only
used by `10_parallel.py`; `timeout` is in seconds.

| Script | Content |
|---|---|
| `01_single_point.py` | DFTB-2 energy terms |
| `02_dftb_levels.py` | DFTB-1, DFTB-2, DFTB-3 |
| `03_properties.py` | electrons, HOMO-LUMO gap, dipole, forces, ... |
| `04_dispersion.py` | water dimer binding: model-1, model-2 |
| `05_optimization.py` | geometry optimization |
| `06_frequencies.py` | frequencies and IR intensities |
| `07_td_dftb.py` | TD-DFTB singlets and triplets |
| `08_periodic.py` | graphene with k-points |
| `09_ci_dftb.py` | CI-DFTB on the water dimer cation, fragment charges |
| `10_parallel.py` | serial vs MPI run |

Not available: HF, xTB, molecular dynamics, transition state, solvation.
Mulliken charges are only read for CI-DFTB.
