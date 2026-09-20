# 13-lantern (meta finale)

**Category:** Cryptography (meta) · **Difficulty:** Insane

**Flag:**
```
Null0rigin{you_put_her_name_back_on_the_work}
```

Unlocked by completing **12-lastpage**, the last of the seven chained stages. This is the end of the chain.

## What ships

`lantern.sealed` (11.6 MB — the proof), `notebooks.txt` (seven spines, each with one 64-bit number written under it, in the author's hand), `shelf-slips.txt`, `verify`, and `taunt.wav`.

## What it's keyed by

This is the payoff of the entire chain. The finale is not keyed by the seven flags from stages 06 through 12 — a team holding all seven flags still cannot open it. It's keyed by seven **non-flag** internal secrets, one per prior stage, each one a specific canonical byte string produced only by fully solving that stage's own artifact:

| | Stage | Canonical bytes |
|---|---|---|
| I | 06-bindery | The 121-cell register seed, base-3 digits least-significant-first, 24 B |
| II | 07-daybook | The 320-bit permutation state *before* the rate lanes were staged over, 40 B |
| III | 08-errata | SHA-256 over a 512-column linear map's columns in walking-ones order, 32 B |
| IV | 09-catalogue | The held-back shelfmark, zero-padded to 14 decimal digits, ASCII |
| V | 10-carillon | `n` (13 B) followed by the reduced form of `P^n` in the negative-discriminant chain, 61 B |
| VI | 11-cartouche | The combinatorial rank of the forty payload flip positions, 56 B |
| VII | 12-lastpage | SHA-256 over the canonical tensor-factor byte string, 32 B |

Each share is derived as:

```
share_i = first 8 bytes of SHA-256(canonical bytes of secret i)
```

**Five of the seven secrets are ambiguous as naively recovered**, and each requires a stage-specific convention to pin down the one canonical form: 06-bindery's digit order, 07-daybook's pre-overwrite state versus the dumped sponge state, 08-errata's column and bit order, 09-catalogue's shelfmark field width, and 11-cartouche's flip set versus its scrambled complement. Every one of those canonical forms is fixed only by that stage's own artifact — never guessable, never searchable from the outside. The build asserts that no flag string is used as an input anywhere in this process.

## The reconstruction is over a ring, not a field

`notebooks.txt` publishes a 64-bit tweak `t_i` under each of the seven spines. `share_i + t_i` is the value at `x = i` of a degree-6 polynomial `f` over **Z/2^64**, and the target secret is `f(0)` — a Shamir-style secret-sharing scheme, but deliberately built over a ring with zero divisors rather than a prime field.

Standard Lagrange interpolation divides by the pairwise differences between the x-coordinates `1..7`, which include 2, 4, and 6 — none of which is invertible mod `2^64`. A generic Shamir library either throws on this or silently returns nonsense, and it would be right to: this isn't ordinary Shamir sharing.

The fix is 2-adic. `v_2(det Vandermonde(1..7)) = 12` exactly — the pairwise differences among `1..7` are five 2s, three 4s, and one 6, so `det = 24883200 = 2^12 * 6075`. Solving 2-adically pins `f(0)` only modulo `2^52`; the top 12 bits remain as `2^12 = 4096` candidates to check against the GCM tag. This is the only sanctioned brute force anywhere on the board — it's small, bounded, and stated openly here. Testing a candidate costs one AES block: since GCM is built on CTR mode, the first block of the known JSON prefix separates candidates immediately, and the full tag is verified once at the very end on the surviving candidate.

## The implementation risk, closed

A naive builder that picks the secret-sharing polynomial *after* generating the shares can produce a share vector that falls outside the image of the Vandermonde map, making the finale mathematically unopenable. This challenge avoids that by picking the polynomial `f` first, then publishing tweaks `t_i` specifically chosen to make `share_i + t_i` land on `f`'s actual values at `x = i`. That construction always succeeds by design, and the published tweaks read in-fiction as the author's own shelf annotations.

## Solve

The solve script re-runs all seven prior stages' solvers against their built artifacts and takes the canonical byte string each one produces — the shares themselves are not stored in any file. It then hashes each one, adds the published tweaks, performs the 2-adic solve for the top bits of `f(0)`, and walks the resulting 4,096 candidates against the GCM tag to find the one that opens `lantern.sealed`.
