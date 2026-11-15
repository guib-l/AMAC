# OpenMolcas examples

`config-amac.json`:

```json
"openmolcas": {
  "executable": "/absolute/path/to/pymolcas",
  "env": {"MOLCAS": "/absolute/path/to/OpenMolcas/build"}
}
```

| Script | Content |
|---|---|
| `01_single_point_hf.py` | HF/cc-pVDZ energy |
| `02_single_point_dft.py` | B3LYP/cc-pVDZ energy, grid, RICD |
| `03_mp2.py` | MP2, with and without frozen core |
| `04_casscf.py` | CASSCF(4,4), single state and state average |
| `05_open_shell.py` | OH radical: UHF and CASSCF(3,3) |
| `06_properties.py` | charges, dipole, forces |
| `07_optimization.py` | geometry optimization (SLAPAF loop) |
| `08_solvation.py` | C-PCM by solvent name and by dielectric constant |
| `09_coupled_cluster.py` | CCSD, CCSD(T) (Cholesky), frozen core |
| `10_caspt2.py` | CASPT2: single state, MS, XMS, imaginary and IPEA shifts |
| `11_nevpt2.py` | SC- and PC-NEVPT2 |
| `12_frequencies.py` | frequencies and IR intensities: analytic (HF) and numerical (B3LYP, MP2) Hessian |

Not available yet: transition state, excited states, molecular dynamics. Not available: xTB, DFTB, `restricted-open` reference,
open-shell MP2/CCSD, QD-NEVPT2, dispersion, solvation models `smd` and
`gbsa`, MPI runs.
