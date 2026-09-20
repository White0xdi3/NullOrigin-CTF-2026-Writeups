# 09-catalogue

**Category:** Cryptography · **Difficulty:** Medium

**Flag:**
```
Null0rigin{you_rebuilt_three_tables_from_nothing_but_pairs}
```

Unlocked by **08-errata**; solving it unlocks **10-carillon**.

## What ships

`shelfmark.dll` (Windows PE x86-64, built with mingw, stripped of debug info, but with its export table intact: `binding_copy`, `load_key`, `point_of`, `shelfmark_of`, `slip`) and `shelf.idx` — 50,331,648 forty-byte records, 2.01 GB. The master key lived in `shelfmark.key`, which is not part of the released files, so the DLL neither issues nor validates anything on its own. There is no oracle. Also shipped: `catalogue.sealed`, `verify`, `description.txt`.

## The mechanism

Shelfmarks are a format-preserving encryption of the accession number over the decimal domain `[0, 10^12)`:

```
point_of(acc) = ((acc*0x0F4243 + 0x0A95B7) mod 10^12)*0x03D091 + 0x02C1A3
                mod 10^12

halves 19 and 21 bits, three rounds, addition modulo the half:
    R1 = L0 + F1[R0]   (mod 2^19)
    L3 = R0 + F2[R1]   (mod 2^21)
    R3 = R1 + F3[L3]   (mod 2^19)
packed out as R3*2^21 + L3, cycle-walked while the result is >= 10^12
```

`F1` and `F3` are 2^21-entry tables; `F2` is 2^19 entries. All three are expanded from the absent key, so there's no small secret to brute-force and no algebraic structure to attack directly — the tables themselves are the target.

## The break

The unbalanced Feistel halves are the point. Eliminating `R1` between rounds one and three gives:

```
R3 - L0 = F1[R0] + F3[L3]   (mod 2^19)
```

`F2` drops out of that equation entirely. Every record in the index is one edge of a bipartite graph on `(R0, L3)` with average degree 24, and the graph is connected — so `F1` and `F3` come out by propagation from a single free choice. That choice is the translation gauge `F1 → F1 + t`, `F2(r) → F2(r − t)`, `F3 → F3 − t`, which leaves the cipher itself unchanged, so any representative in the gauge orbit encrypts correctly and there's no need to collapse the class by hand.

### The poisoning is the actual work

`10^12 / 2^40 = 0.9095`, so **9.05%** of the records went around the cycle-walk a second time and aren't genuine Feistel pairs at all. A naive first-write-wins fill lands with a 64% residual error — most of both tables wrong, not just 9%.

The repair is the real trick, and it isn't a fixed threshold. If `F1[r]` is wrong by `delta`, then *every honest record touching `r`* has residual exactly `delta` — the error behaves as a constant, not noise. So the per-entry **mode of the residual is the correction**. Two rounds of that take the residual from 64% → 12.9% → 9.05%, which is the poisoning floor — and at the floor, both tables are exact. `F2` then falls out from one more vote across six entries of 524,288, needing an exact tally rather than a sampled one.

A fixed majority threshold does not work here, because the poisoning rate per entry is not the global rate and isn't stated anywhere in the artifacts.

## Why it's hard / why there's no shortcut

The stage key is the shelfmark of accession number `0x3ADE68B1`, named only inside the DLL and appearing nowhere in the index. Producing it requires walking all three tables (twice, if the first pass lands out of range) — so 99.99% of the tables tells you nothing directly. The sealed archive ends in a 16-byte GCM tag: pass or fail, no partial credit.

### Deviations from the design sheet, stated

- The build uses 19/21-bit halves and 50.3M pairs rather than the originally planned 22/24 bits and 268M pairs, because the peel is memory-bound and the build machine has 7 GB of RAM. The structure, the poisoning rate (9.05% measured against a ~8% target), and the "at least a handful of records per table entry" property (measured minimum 22 for `F1`, minimum 5 for `F3`, mean 24) are all preserved.
- The translation gauge needs no collapsing — it's a genuine symmetry of the cipher, so the reserved shelfmark is well-defined on any representative. The reserved-shelfmark check still does the job it was designed for: forcing the tables to be complete.

## Solve

`solve.py` runs in 49 s and uses about 1.9 GB of resident memory against the built 2 GB artifact.
