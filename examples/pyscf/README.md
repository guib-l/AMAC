# PySCF examples

PySCF runs in-process: no executable and no `config-amac.json` section.

Python packages: `pyscf`; `geometric` for 05 and 08; `pyscf-dispersion`
for the D3(BJ) correction of 02.

| Script | Content |
|---|---|
| `01_single_point_hf.py` | HF/STO-3G energy |
| `02_single_point_dft.py` | B3LYP-D3(BJ)/def2-SVP energy |
| `03_correlated.py` | MP2, CCSD, CCSD(T), frozen core |
| `04_casscf.py` | CASSCF(4,4) |
| `05_optimization.py` | geometry optimization |
| `06_frequencies.py` | harmonic frequencies (no IR intensities) |
| `07_excited_states.py` | TD-DFT singlets and triplets |
| `08_transition_state.py` | NH3 inversion transition state |
| `09_molecular_dynamics.py` | BOMD, Berendsen thermostat |
| `10_solvation.py` | C-PCM solvation energy |

Not available: xTB, DFTB. Frequencies and excited states: HF and DFT only.
