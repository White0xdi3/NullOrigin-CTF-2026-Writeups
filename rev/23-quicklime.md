# 23-quicklime

**Category:** Reverse Engineering · **Difficulty:** Medium

**Flag:** `Null0rigin{you_kept_the_last_eleven_bits}`

**Decoys:**

| # | Route (the mathematically "correct" wrong turn) | Lands on |
|---|---|---|
| D1 | Compute the correctly-reduced sine (e.g. via libm) instead of running the raw `FSIN` instruction | `Null0rigin{the_library_pi_was_too_exact}` |
| D2 | Force the same computation to 53-bit x87 precision-control throughout | `Null0rigin{fifty_three_bits_of_almost}` |
| D3 | Compute `a*b+c` as two separately-rounded operations instead of a fused multiply-add | `Null0rigin{one_rounding_short_of_fma}` |
| D4 | Compute the product directly in double precision (single rounding) instead of via the x87 80-bit path | `Null0rigin{the_second_rounding_was_real}` |
| D5 | Repeat the multiply with FTZ/DAZ set in MXCSR (flush-to-zero) instead of gradual underflow | `Null0rigin{gradual_underflow_never_happened}` |

Every decoy above is the answer you get by doing the arithmetic **correctly**
by IEEE-754's own rules — which is precisely why it's the trap.

## The mechanism

Five chained GF(2) systems, the same cascade shape as 21-cinder and
22-dovetail:

```
A1.x1 = b1  ->  seed(A2)  ->  ...  ->  A5.x5 = b5,   x5 = flag
```

What's unique to this stage is *what gets measured*. All five layers share
one theme — the machine's actual floating-point arithmetic disagreeing with
"the mathematics" — and each is a different flavor of that disagreement:

| Layer | Divergence: hardware vs. "correct" math |
|---|---|
| L1 | `FSIN` of a huge argument vs. correctly-reduced sine |
| L2 | x87 precision control at 64-bit vs. the same loop forced to 53-bit |
| L3 | `fma(a,b,c)` vs. `a*b+c` rounded separately (credential-gated) |
| L4 | 80-bit extended precision, narrowed, vs. computed directly in double |
| L5 | gradual underflow vs. FTZ/DAZ set in MXCSR |

Every layer narrows its result to an IEEE double and keeps **the last
eleven bits of the mantissa** (0–2047) as an index into
`reduction_tables.bin` — 2048 slots of 140 KiB each (280 MB shipped). The
slot at that index is SHA-256'd into the layer's 32-byte seed material. The
arithmetic result itself never has to be secret: turning "index 364" into
the right 32 bytes requires the actual shipped table, and the only way to
land on the *right* index is to run the *right* computation on real
hardware. The table is opened read-only and streamed 8 KiB at a time —
never mapped or loaded whole.

| Layer | n | Rank | Real value → slot | "Correct" value → slot |
|---|---|---|---|---|
| L1 | 352 | 352/352 | `FSIN` mantissa → slot 604 (or 364, per measurement run) | libm `sin` → decoy slot |
| L2 | 320 | 320/320 | PC=64 (CW `0x037F`) | PC=53 (CW `0x027F`) |
| L3 | 296 | 296/296 | `fma(a,b,c)`, credential-gated | `a*b+c`, rounded twice |
| L4 | 264 | 264/264 | x87 `fmulp` then narrow | SSE2 `mulsd`, one rounding |
| L5 | 328 | 328/328 | gradual underflow | FTZ+DAZ flush |

Every rank above was obtained by *running* Gaussian elimination and checking
the recovered vector against the intended one — `search_nonce()` has no
path that skips this check. All five real/decoy pairs are also confirmed to
land on genuinely *different* table slots; two doubles that happened to
share their low eleven mantissa bits would otherwise select the same slot,
hash to the same seed material, and silently kill a layer while it still
looked fine.

The `-ffp-contract=off` compiler flag is load-bearing specifically here:
without it, the compiler is free to contract `a*b+c` back into a single
`fma`, which would silently turn the L3 decoy into the same system as the
real layer.

## The break

Both arms of all five divergences have to be run **on real hardware** —
there is no portable IEEE library that reproduces `FSIN`'s behavior on a
huge argument, x87's 80-bit precision-control field, or MXCSR's flush
behavior. The reference implementation reaches these through mmap'd
machine-code stubs called via `ctypes` (CPython has no 80-bit float type and
no way to touch the FPU control word directly), cross-checked against
equivalent inline-asm in C.

Layer 3's `fma` operands are derived from the *output* of `sha512crypt`,
never the plaintext, so a candidate password costs one full 5,000-round
`sha512crypt` to test:

```
hashcat -a 6 -m 1800 quicklime.shadow vocab.txt 14?d?d?d?1 -1 !@#$%& -j ^-^k^l -w 4 --hwmon-temp-abort 95
```

- **Class:** bundle (a `district-basetoken+seam+shot+marker` shape, distinct
  from staff/contractor) · **base token:** `entwhaite` (audited absent from
  rockyou) · **district:** lk · **seam:** 14 · **shot:** 602 → password
  `lk-entwhaite14602%`
- Vocabulary: 5,274 harvested tokens, 924 (17.5%) already in rockyou. Seam
  known: 31,644,000 candidates (~10.6 min full sweep). Seam unknown: 3.16
  billion candidates (~17.7 hours).
- As with the other stages, the seam number comes from a planted "lamp
  account" card (7 copies in the table) that narrows the mask, not the
  wordlist.

Recovering the flag from the shipped artifact took 0.083s of elimination,
0.216s end to end.

## Anti-analysis tricks

- **Correctness is the trap.** Every decoy is the mathematically *right*
  answer under standard IEEE-754 semantics — a solver who "fixes" what
  looks like a bug (e.g. `FSIN` on a huge argument, or a supposedly-buggy
  double rounding) has already lost.
- **A dependency on real silicon.** L1 keys on the x87 `FSIN` result for a
  large argument (specified by a 66-bit pi constant both Intel and AMD
  implement), and L2/L4 key on the x87 80-bit datapath — an architectural
  assumption, not a portability bug, recorded rather than hidden.
- **No anti-debug on this stage, deliberately.** Unlike its neighbors,
  none of quicklime's five sources observe the debugger at all — this
  stage is the one place on the board where running under gdb to confirm
  your own answer gets you the *right* answer.
- **Credential gate off the crypt output.** As with every credentialed
  layer on this board, keying off `SHA256(plaintext)` instead of the full
  `sha512crypt` output would have made a candidate roughly 5,000× cheaper
  to test, deleting the intended GPU-bound wall.

## Notes

- **A near-miss build bug on L5, caught only by differential testing.**
  FTZ/DAZ flush behavior cannot be set from pure Python, so the Python
  mirror models the flush from the IEEE bit fields directly, and the model
  was cross-checked against a compiled probe that actually sets MXCSR. The
  two initially *disagreed*: the model predicted a flushed-to-zero product,
  but the compiled probe returned the *unflushed* value even with FTZ/DAZ
  demonstrably set (confirmed by reading MXCSR back immediately after). The
  root cause: GCC doesn't implement `#pragma STDC FENV_ACCESS`, so it
  doesn't treat the MXCSR control word as an input to a floating-point
  instruction, and had hoisted the multiply out of the window between the
  two `ldmxcsr` calls that were supposed to bracket it. Pinning the
  multiply in inline asm with a memory clobber fixed it. The exact same
  shape existed in the shipped C source (`volatile` orders loads, but does
  not pin the multiply itself) — on the build machine it happened to
  produce the right answer anyway, because the ambient FPU mode a fresh
  Linux process starts in already matches what the stage expects, so
  nothing visible would have caught it by simply running the stage. A
  player whose process started with FTZ set for any other reason would
  have found the stage silently unsolvable. This was found and fixed only
  because the differential test exercises both arms independently rather
  than trusting the forward construction.
- **`reduction_tables.bin` is load-bearing, measured, not assumed.** Delete
  it and the stage refuses to run; flip one bit inside the single slot
  layer 1 actually reads and the real flag stops being accepted; restore
  that byte and acceptance returns.
- **Cold-cache timing:** ~18ms on first run — five 140 KiB slot reads out of
  a 280 MB file, a much smaller page-in cost than 21-cinder's 50,000
  dependent reads.
- **Verification rigor:** 78 differential checks (both arms of all five
  divergences, not just the real ones, run against a probe binary built
  from the shipped C source) and 60 end-to-end checks against the shipped
  artifact.
- **Flag absence, measured:** not present as plaintext, reversed, or any
  16/24-byte fragment in either the binary or `reduction_tables.bin`
  (280 MB of harvestable text being the likeliest accidental leak surface
  on this stage); not under any of 255 XOR keys, 255 ADD keys, or 7 bit
  rotations; absent from a memory dump taken at the verdict `write()` on a
  run carrying a wrong candidate.
