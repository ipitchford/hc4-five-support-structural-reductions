# Methodology-specialist report

**Target:** commit `2779d701b2e115c141df4eab22b3843af19c593c`  
**Assurance class:** internal producer-coordinated role review  
**Decision:** revise verification coverage

## Assessment

The C16 path is unusually well bound: prospective support ordering, complete
row-interface comparison, four canonical multi-RHS solves, uniqueness-bounded
rational reconstruction, exact row replay, and a direct-polynomial audit. The
resource metrics are sufficiently specific to calibrate reruns.

## Required repairs

1. `verify_package.py` validates C16 deeply but only checks the existence of the
   C1–C3 claim entries. It should also require the terminal PASS statuses for
   the five-support theorem, all-31-generator tangent theorem, and all three
   rational colon identities.
2. The C2 evidence map currently names the target-ideal profile receipt, which
   does not itself prove tangent containment. Replace it with the aggregate
   all-31-generators receipt.
3. Add a recorded clean-copy replay after the repaired manifest is created.

## Scope note

The status token in one historical audit contains `INDEPENDENT`; the surrounding
assurance text correctly prevents reading that as unaffiliated reproduction.

