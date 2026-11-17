# DFTB+ examples

`config-amac.json`:

```json
"dftb+": {
  "executable": "/absolute/path/to/dftb+",
  "basis": "/absolute/path/to/mio-1-1"
}
```

`basis` is the Slater-Koster directory; the scripts read it from the file.
`05_xtb.py` needs a DFTB+ build with tblite.

| Script | Content |
|---|---|
| `01_single_point.py` | DFTB-2 energy terms |
| `02_dftb_levels.py` | DFTB-1, DFTB-2, DFTB-3 |
| `03_properties.py` | charges, dipole, eigenvalues, Fermi level, forces, ... |
| `04_dispersion.py` | water dimer binding: none, LJ-UFF, D3-BJ, D3-zero, D4 |
| `05_xtb.py` | GFN1-xTB, GFN2-xTB |
| `06_optimization.py` | geometry optimization |
| `07_td_dftb.py` | TD-DFTB (Casida) excitations |
| `08_molecular_dynamics.py` | MD, Berendsen thermostat |
| `09_solvation.py` | C-PCM (ddCOSMO) solvation energy |
| `10_periodic.py` | graphene with k-points |
| `11_shell_dep.py` | DFTB-2 shell-resolved SCC, off vs on |

Not available: CI-DFTB, HF, frequencies, transition state. Solvation:
`cpcm` model only.
