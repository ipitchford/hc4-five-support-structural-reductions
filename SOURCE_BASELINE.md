# Source baseline and reconstruction boundary

The external source is pinned to Roy van Rijn's repository commit
`3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9`.

A detached local checkout is stored at
`source/royvanrijn-jacobian-research`; `git rev-parse HEAD` is audited by the
consolidated replay script.

Relevant frozen SHA-256 values:

```text
2203c36bcb787a3d9620fa7110f6f3a48bd5e7769cc156100837aef6914d4ce1  HC4_DOUBLE_CONIC_NORMAL_LAYERS.md
519cecddf95ff1d8106d2680f88f687d5db1a39306a361dfcc728200711e9928  HC4_DOUBLE_CONIC_INVARIANT_SATURATION_GATE.md
48b78faeb4bd2a2700084d3314be7f3745dbd953368c4777f02b4d92cbcc0a07  scripts/verify_hc4_double_conic_normal_layers.py
03a9e5b6b0e867b54cbf3daac872d768e730f7b9290ce09ec108011f9e0e94f3  scripts/verify_hc4_double_conic_invariant_saturation_gate.py
0e6cac3d8ae4f4bf8e049c7d43686297ff44c6017eb0aa6ba13ed2475d0fb26d  HC4_DOUBLE_CONIC_BALANCED_FOUR_ROOT_CLOSURE.md
822b56fd73e75631ea5d337499315c977f5bae938bae638596e64ee9bd16ed7e  scripts/verify_hc4_double_conic_balanced_four_root_closure.py
```

The source proves an explicit four-layer covariant frontend and identifies
the clean saturation `I_nor:m2^infinity`. It reports the support-at-least-five
row as open. Its ledger labels the relevant results exact-symbolic or hybrid,
without independent replay or formal verification.

This campaign's `reconstruct_normal_layers.py` is a second derivation, not a
copy of the coefficient table. It uses a closed harmonic-projection
recurrence and automatic transvectant-basis interpolation. The production
receipt uses three exact training samples and two disjoint symbolic holdouts.

Source links:

- [Normal layers](https://github.com/royvanrijn/jacobian-research/blob/3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9/HC4_DOUBLE_CONIC_NORMAL_LAYERS.md)
- [Invariant saturation](https://github.com/royvanrijn/jacobian-research/blob/3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9/HC4_DOUBLE_CONIC_INVARIANT_SATURATION_GATE.md)
- [Status ledger](https://github.com/royvanrijn/jacobian-research/blob/3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9/MATH_STATUS.json)
