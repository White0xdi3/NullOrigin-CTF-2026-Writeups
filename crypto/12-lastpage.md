# 12-lastpage

**Category:** Cryptography · **Difficulty:** Insane

**Flag:**
```
Null0rigin{you_took_her_last_paper_apart_into_the_pieces_she_built_it_from}
```

Unlocked by **11-cartouche**; solving it unlocks the finale, **13-lantern**.

## What ships

- `Lastpage.jar` — name-mangled, string-pooled JVM bytecode that evaluates a trilinear form against `records.bin`. Its embedded resource `META-INF/o/notes.txt` carries an honest security note and — load-bearing — the canonical ordering needed for a factorization.
- `records.bin` (539 MB) — the 512³ = 134,217,728 entries of the tensor as little-endian `uint32`, in 32,768 slots of 4,096 entries each, followed by a 64-byte trailer (`crc32 | start_index | pad`). Slots are written **shuffled**; the trailing index is not optional.
- `lastpage.sealed` — AES-256-GCM under `SHA-256(SHA-256(canonical factor bytes))` — the seal helper hashes the secret twice to derive the key.

## The mechanism

The challenge evaluates `seal(x,y,z) = Σ_{ijk} T[i,j,k] x_i y_j z_k mod p`, with `p = 1048573`, and `T = Σ_{r=1..512} a_r ⊗ b_r ⊗ c_r`, where `A, B, C ∈ F_p^{512×512}` are uniform and all invertible (rejection-sampled), and `n = R = 512`.

The security note bundled in the jar is correct and useless: rank decomposition of a 3-tensor is NP-hard **in the worst case**. This instance is deliberately not a worst case:

- `R = n` and the factors are invertible, so Kruskal's uniqueness condition `3n ≥ 2n+2` holds — the decomposition is **unique**.
- Jennrich's simultaneous-diagonalization algorithm recovers it in polynomial time.

### Why `R = n` and not `R < n`

At a lower rank like `R = 450 < n = 600`, the first reflex any solver reaches for — the rank of the mode-1 unfolding — would return 450 and immediately announce "low rank." At `R = n`, that probe instead returns full rank:

```
mode-1 unfolding rank = 512 of 512 -- FULL, no low-rank tell
```

The only surviving tell is that the matrix pencil `M(w1)M(w2)^-1` has a **completely split** characteristic polynomial over `F_p` — probability ≈ `1/n!` for a random matrix, and no standard forensics battery computes the characteristic polynomial of a 512×512 matrix over a finite field.

The modulus choice matters too: `p ≈ 2^20` rather than something like 65537. With 512 columns and `p = 65537`, an eigenvalue collision is roughly 86% likely per draw and produces a degenerate eigenspace. At `p = 1048573`, collisions are rare, so the solver simply loops over fresh `(w1, w2)` pairs until `factor` returns 512 distinct linear factors, each with multiplicity 1.

## The break

1. Parse the container and assemble `T` (1.07 GB as `int64`).
2. Build `M(w) = Σ_k w_k T[:,:,k] = A · diag(Cᵀw) · Bᵀ` for a random weight vector `w`.
3. Form the pencil `G = M(w1) · M(w2)^-1 = A · diag(d1/d2) · A^-1`.
4. Compute the characteristic polynomial of `G` via a **Krylov minimal polynomial** (n matrix-vector products plus one nullspace computation) — this avoids ever shipping a 512×512 matrix into PARI.
5. Factor that polynomial mod `p` — it splits into 512 distinct roots.
6. Recover `A`'s columns as `a_r = ker(G - λ_r I)`.
7. `A^-1 T[:,:,k] = diag(c_k) · Bᵀ` recovers `B` and `C` via two linear solves.
8. Canonicalize the triple, hash it with `SHA-256` twice, and open the archive.

All the `F_p` linear algebra runs as float64 BLAS with a modular reduction afterward: `p² · n = 2^49 < 2^53`, so every product is bit-exact in double precision. No `galois`-style finite-field library is used anywhere — its GF(2^k) characteristic-polynomial routine hangs on this machine at `n ≥ 12`.

## Measured

```
container: p=1048573 n=512 per_record=4096 records=32768
mode-1 unfolding rank = 512 of 512 -- FULL, no low-rank tell (0.8s)
pencil G = M(w1) M(w2)^-1 built (2.7s)
charpoly via Krylov, degree 512 (0.3s)
factors over F_1048573: 512 of them, max degree 1, max multiplicity 1
512 eigenvectors -> A (130.9s)
B and C by two linear solves (6.9s)
reconstruction verified on 4 slices
canonical factor digest = d988d824...4c05
total 142.1s
```

## Why it's hard / why there's no shortcut

No oracle ships for testing a partial or candidate factorization (only the generic flag-checker `verify`, as on every stage). The payload is GCM under a hash of the full factorization — one bit of failure at the very end. The one predicate that exists in principle — remove a rank-1 term and see whether the tensor's rank drops — has zero measure and no usable gradient over a finite field. Every numerical CP-decomposition tool (tensorly, CP-ALS, ALS at scale) is built for floating point and is meaningless over `F_p`, so the applied literature doesn't apply, and the one algorithm that *does* apply (Jennrich's) is the one the numerical community largely abandoned for a floating-point instability that simply doesn't exist in exact finite-field arithmetic.

## Solve

The attack pipeline above runs automatically end-to-end in [`solve.py`](12-lastpage/solve/solve.py) against the built artifact in a total of 142.1 seconds, dominated by the 512-eigenvector recovery step (130.9s).

**Feeds the finale:** the internal secret this stage contributes to 13-lantern is `SHA-256` over the canonical factor byte string: `A`, then `B`, then `C`, columns in canonical order, each entry 4 bytes little-endian (32 bytes total). Canonical order is fixed by `META-INF/o/notes.txt` inside the jar: scale each triple so the first nonzero entry of `a_r` is 1 and the first nonzero entry of `b_r` is 1 (letting `c_r` absorb both scalings), then sort lexicographically by `(a_r || b_r || c_r)`. This resolves the scaling gauge ambiguity inherent to the decomposition.
