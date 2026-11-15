# ORCA examples

`config-amac.json`:

```json
"orca": {
  "executable": "/absolute/path/to/orca"
}
```

| Script | Content |
|---|---|
| `01_single_point_hf.py` | HF/def2-SVP energy |
| `02_single_point_dft.py` | B3LYP-D3(BJ)/def2-SVP energy, RI |
| `03_correlated.py` | MP2, CCSD, CCSD(T), frozen core |
| `04_casscf.py` | CASSCF(4,4) |
| `05_xtb.py` | GFN1-xTB, GFN2-xTB |
| `06_properties.py` | charges, dipole, forces |
| `07_optimization.py` | geometry optimization |
| `08_frequencies.py` | frequencies and IR intensities |
| `09_excited_states.py` | TD-DFT singlets and triplets |
| `10_transition_state.py` | NH3 inversion transition state |
| `11_molecular_dynamics.py` | GFN2-xTB MD, Berendsen thermostat |
| `12_solvation.py` | C-PCM and SMD solvation energies |

Not available: DFTB. Solvation model `gbsa` (ALPB): xTB only.
