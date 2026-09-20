# 06-bindery

**Category:** Cryptography · **Difficulty:** Entry

**Flag:**
```
Null0rigin{you_counted_in_a_base_she_never_named}
```

This is the entry point of the crypto chain — it ships in the clear and unlocks **07-daybook**.

## What ships

- `bindery.o` — 3,368 bytes, an ELF relocatable with no entry point and four unresolved externs (`idx_alloc`, `idx_emit`, `idx_fault`, `idx_slack`). Linking it requires supplying those four symbols yourself; stub them and it links and runs, which gives you a local oracle. Nothing shipped does that for you — there is no encryptor, no reference implementation, and no oracle out of the box.
- `index.sealed` — 345,454 records of exactly 110 bytes each, 38.0 MB.
- Supporting files: `slips.txt`, `bindery.sealed`, `verify`, `description.txt` (story and flag format, no hints).

## The mechanism

The core is a 121-cell linear recurrence over GF(3). The register is two 128-bit bit-planes (four 64-bit words), and a cell is one bit from each — `(0,0)`, `(1,0)`, `(0,1)` — so `cadd` is the carry-free identity on those planes. There is no literal 3, no `0xAAAAAAAB`, no multiply, and no divide anywhere in the object; the build asserts that against the disassembly. The reciprocal-multiply idiom and the 1/3/9/27/81 ladder that any disassembly pass would instantly flag as "base-3 arithmetic" simply isn't present.

The 121 multipliers sit in `.rodata` as one bit-plane pair; the 28 fixed leading cells of every entry sit beside them as another. `.rodata` is 64 bytes total and nothing in it is named.

### The encoding is the hardening

An entry is 512 cells written as one integer, with cell 0 most significant, so `x` lies in `[0, 3^512)` — 812 bits. `pack` writes it into 110 bytes, and then `idx_slack` tops it up:

```
y = x + u * 3^512,   u uniform in [0, floor(256^110 / 3^512))
```

`256^110` is 880 bits, so `u` has a 68-bit range and the statistical distance from uniform is below `2^-67`. Measured on the built artifact: the leading byte takes **all 256 values**, whole-file byte entropy is **8.00000**, and the per-offset chi-squared at offsets 0–3 is 265 / 233 / 240 / 305 against 255 degrees of freedom — flat.

| Metric | Value |
|---|---|
| Leading byte value coverage | all 256 values |
| Whole-file byte entropy | 8.00000 |
| Chi-squared, offset 0 | 265 (df 255) |
| Chi-squared, offset 1 | 233 (df 255) |
| Chi-squared, offset 2 | 240 (df 255) |
| Chi-squared, offset 3 | 305 (df 255) |

This matters because the naive encoding is fatal. Writing `x` straight to `ceil(512*log2(3)/8)` bytes leaves the leading byte **constant** across every record — its value is 4 or 8 depending on stamp-plane order, not zero, and it's constant because the 28-cell stamp is fixed. A per-offset byte histogram is the first thing any carving, entropy, or format-identification tool prints, so that naive layout would collapse instantly. Decoding the actual padded format costs one modulo.

## The break

The 28 stamp cells of every entry are known plaintext at known positions, so each entry hands over 28 cells of the register. Six entries give 168 linear equations on the 121-cell seed over GF(3); rank 121 arrives well inside that. Gaussian elimination mod 3 in plain `int64` numpy runs in milliseconds — notably **not** via `galois`, whose GF(2^k) matrix routines hang at this size.

There is one genuine ambiguity: which of the two 32-bit words in `.rodata` is the stamp's first plane. Both choices give rank 121, but only one correctly predicts the stamp of an entry the system never saw — the solve script demonstrates taking the wrong one first before correcting.

## Why it's hard / why there's no shortcut

`index.sealed` is uniform; a wrong seed yields uniform cells and no way to rank candidate solutions. Fewer than 121 independent equations leaves an affine space with nothing to score against. Nothing runnable ships, so there is no chosen-key probe available either — the only path in is the linear-algebra recovery above.

## Solve

[`solve.py`](06-bindery/solve/solve.py) runs in 23.2 seconds end to end (warm cache; slower under load) against the built artifact. It reads the constants directly out of `.rodata`, so it survives a rebuild with a new seed.

**Feeds the finale:** the internal secret this stage contributes to 13-lantern is the 121-cell register seed, expressed as the base-3 digits of one integer (least significant digit first, cell 0 is digit 0), written as 24 bytes big-endian. The framing fixes the register at entry zero, which is what fixes the digit-order convention.
