# ORCA reference outputs

To write once ORCA is installed and its absolute `executable` is set in
`config-amac.json`. Each file is the ORCA output (`output-orca.out`) of a
calculation on `ase.build.molecule("H2O")`, run through AMAC:

| File                   | Calculation                                    |
|------------------------|------------------------------------------------|
| `sp.out`               | HF/STO-3G single point with forces (EnGrad)    |
| `opt.out`              | HF/STO-3G optimization                         |
| `freq.out`             | HF/STO-3G frequencies                          |
| `td.out`               | HF/STO-3G, 3 TD roots (singlets)               |
| `md-trajectory.xyz`    | HF/STO-3G, 5 MD steps of 0.5 fs                |

Note the ORCA version in `test/asset/orca/test_parser.py`, then replace the
`pytest.skip("TODO: ...")` of `test_parser.py`, `test_handler.py` and
`test_real.py`.
