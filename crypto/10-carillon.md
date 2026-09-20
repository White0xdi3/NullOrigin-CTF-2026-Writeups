# 10-carillon

**Category:** Cryptography · **Difficulty:** Hard

**Flag:**
```
Null0rigin{you_told_two_worlds_apart_by_a_single_sign}
```

Unlocked by **09-catalogue**; solving it unlocks **11-cartouche**.

## What ships

`Ledgerd.dll` (.NET 6, mangled names, one flattened dispatch loop, string pool folded, a stack machine whose program is an embedded resource), two ledger files of ten million records each, and the sealed archive. The daemon verifies *internal consistency only* — one discriminant per file and a strictly increasing accumulator. It never takes, tests, or reports a candidate secret, so there is no oracle anywhere in the stage.

## The mechanism

Records are integer triples `(a, b, c)` plus three 64-bit fields. Nothing in any artifact uses the words "quadratic form," "class group," "discriminant," or "infrastructure" — the reader has to recognize the structure unaided.

`b^2 - 4ac` is constant across each file. That's the cheap first observation. The real one is that the constant is **negative** in `ledger-I.dat` and **positive** in `ledger-R.dat` — two different kinds of mathematical object living on the same code path:

- `D_I = -(10^30+7)`. This is a finite abelian group of order `h = 752026136216220`, structure `[376013068108110, 2]`. `quadclassunit` returns it in under half a second. The genesis record has full order `M = 376013068108110`, the seal record is its `n`-th power, and Pohlig–Hellman (`M = 2 * 3^4 * 5 * 23 * 59 * 61 * 5608003`, largest prime factor 5608003, widest baby-step table 2,369 entries) recovers `n mod M` — about 48.4 of the 100 bits of `n`.
- `D_R` is 282 bits and positive — not a group, but a cycle carrying a real-valued distance. The genesis record is one step along the principal cycle from the reduced principal form, and its accumulator field is that step's true distance in fixed point, scale `2^49`.

### The accumulator

The three trailing fields form one 192-bit fixed-point value, XOR-folded with a keystream the machine derives from the record's own `a || b || c` bytes. Raw field ratios are noise until the bytecode is read: the program is 207 bytes — a fold over the coefficient words with one 64-bit multiplier and a shift, then three finalizers.

Once unfolded, `ledger-R.dat`'s field is exactly additive under composition, so `seq(seal) / seq(genesis) = n`. It's written with **56 significant bits** — the width of the genesis field, which is the tell — so it pins `n` only to a window of `2^45`. That's deliberately wider than nothing and deliberately narrower than `2^48.4`: neither chain alone decides `n`, but together exactly one value survives. The build asserts both conditions (`window >= 2^40`, `candidates == 1`).

`ledger-I.dat` carries the same field computed by the same routine, but the weight routine's logarithm step early-outs on a negative discriminant and hands back an unreduced ratio around `2^124`. Ten million records stay inside the 192-bit field and stay monotone, but the seal record — at `n` times that value — overflows it. Dividing the two gives a number near `4.5e19` with no usable magnitude. Chain I has to be solved with the class group, not with arithmetic on the accumulator.

## The break

Combine both chains: Pohlig–Hellman on the negative-discriminant class group gives `n mod M` (48.4 bits), and the positive-discriminant cycle's accumulator window gives a `2^45`-wide band around the true `n`. Intersecting the two leaves exactly one candidate for `n`.

## Why it's hard / why there's no shortcut

- No distance value ever ships in the clear.
- Ten million records per chain make brute-force walking either structure hopeless.
- The archive key is `H(n || h_I || genesis form of chain I || D_R)`, so a numeric fluke that happened to produce the right `n` still couldn't self-verify without doing the actual class-group work.
- The sealed archive is one GCM tag at the very end — one bit of failure, no gradient — and `verify` locks after three wrong answers.

### Deviations from the design sheet, stated

- Composition and reduction live in the managed (obfuscated) layer, not in the bytecode; the bytecode only carries the accumulator mask, which is the routine a solver actually has to reproduce. A full bignum VM wasn't worth the build risk.
- Ledger totals are 2.08 GB rather than the originally planned 2.6 GB, because record strides of 80 and 128 bytes are the natural fit for 16- and 32-byte coefficients.

## Solve

[`solve.py`](10-carillon/solve/solve.py) runs in 0.9 s wall-clock against the built artifact (0.6 s of that internal computation). It parses the container, reproduces the bytecode's keystream, reads both signs, runs Pohlig–Hellman, intersects the two constraints, and opens the archive.

**Feeds the finale:** the internal secret this stage contributes to 13-lantern is `n` as a 100-bit big-endian integer (13 bytes), concatenated with the canonical reduced form of `P^n` in the negative-discriminant chain — `a`, `b`, `c` each as 16-byte signed big-endian integers, in that order (61 bytes total). The convention is fixed by the ledger's own record layout: the seal record of `ledger-I.dat` *is* that form.
