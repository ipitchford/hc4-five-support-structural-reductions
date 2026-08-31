# HC4 research closeout — 31 August 2026

**Research cutoff:** 22:30 BST  
**Scope:** secant `j2` successive-colon route after the exact `h3` identity

## Strongest positive results

1. The exact source-level identity
   `M*h3=sum(q_i*F_i)+q_18*h+q_19*h2` over `QQ` remains independently
   certified.  Hence `h3` lies in the preceding localized colon.  This is not
   colon equality, saturation, secant closure, nullcone containment, or HC4.
2. The next `M*h4` system was constructed exactly with 85,688 rows, 36,587
   selected coordinates, 1,487,624 nonzeros, and 2,239 free coordinates.
3. Its fixed-gauge characteristic-173 solution lifted through `173^96` with
   zero row swaps.  The 42 new digits from `p54` to `p96` took 4,932.96
   seconds external wall and 459,046,912 bytes maximum RSS.
4. A separately frozen audit replayed all 42 corrections and the terminal
   integer congruence in 6.58 seconds.

The last two items certify a finite modular lift, not a rational fourth-colon
identity.

## Exact-recovery result

The prospectively frozen `p96` hierarchy exhausted without an exact rational
vector:

- equal-height reconstruction: 28,008 resolved, 8,579 unresolved;
- progress from `p54`: only 382 fewer unresolved coordinates after 42 digits;
- `p84 -> p96` stable nonzeros: 601 coordinates, 289-bit denominator LCM;
- stable-denominator exact replay: 42,870 mismatched rows;
- unscaled simultaneous LLL: dimensions 8, 16, 24, and 32, with all sampled
  candidates failing and candidate denominators roughly 897--969 bits.

This is negative evidence about one fixed gauge and one frozen reconstruction
hierarchy.  It does not disprove rational membership.

## Next bounded experiment

The 2,239 free coordinates are now reduced to a prospectively selected
16-column character-two kernel batch.  An exact descriptor census found free
source supports from 13 to 248; 43 columns attain support 13.  The first 16
are all from generator `g00`:

```text
46, 47, 57, 66, 68, 102, 155, 547,
763, 965, 966, 1261, 1269, 1499, 1699, 1711.
```

Construct `T=-B^(-1)C16`, normalize the free block to `I16`, and replay all
85,688 rows.  If that passes, lift the unchanged batch through `173^2`; only a
passing two-digit falsifier may promote to `173^4` and exact rational replay.
The existing audited 114-RHS driver supplies the normalization pattern.  The
measured solver bracket is 2--8 solve equivalents, about 4--16 minutes, with
a fail-closed stop above eight equivalents or 1.5 GB RSS.  Implementation and
independent audit are separate costs.

## Artifact hashes

```text
72973069b837145ffaf8bf15569f2d9dd2c9e1ba2253b4b3635005ffe99f4f2d  artifacts/fourth-colon-p173-target-96digit-extension-v1/extension.json
4a2234d1b905d2039badccc946e81e40c42a37aadd9dbb73d4d093ea803ea25e  receipts/hsop-j2-secant-r10-fourth-colon-p173-96digit-extension-independent-audit.json
5454be5227dca5ca7c19bbe893f2224f2b5ccb64a5404db8f0b8143f23a9bc13  artifacts/fourth-colon-p173-target-p96-exact-rational-recovery-v1/replay.json
0cff239471b300190d2212ace37fa40e27434f90ab5881b2ec8d9a394c34dc15  receipts/hsop-j2-secant-r10-fourth-colon-character2-free-support-census.json
138fdc39fe60a37ad3e09890b1409e4cbac752eb03ef2266173c89a8c4318989  scripts/scout_p173_fourth_colon_character2_free_supports.py
403f11cb96f4a00ae8c34e01e873b686f158d297910208103c5bfa3411c333a9  research/FOURTH_COLON_CHARACTER2_KERNEL_BATCH_SCOUT_DESIGN.md
91508ee0fc2d0a235ad2332e3f9fc644a9b126037d2eeacde01163d9a817c5d7  README.md
6e4a9a79f3e4830ff105f96c59e522aa06f034aaefcc7c18466dbdc286a3aa2e  NEXT_GOAL_HSOP_NULLCONE.md
6fdca1d0299554d1d50f7f82e5edd249c870ea04b537a8a477f37ea4c049453d  RESEARCH_METRICS.md
46c51f1c03d64994efc8a919c8f97e46fa55bc5d4728255546525cef5ec5000c  CLAIM_LEDGER.json
```

## Theorem boundary

The campaign now has an exact third successive localized-colon element, a
certified 96-digit modular lift for the fourth target, and a sharply bounded
next kernel-batch experiment.  It does not yet have a rational fourth target,
colon equality, saturation, closure of either exact secant `V2` branch,
secant nullcone containment, polynomial-level orbit closure, or HC4.
