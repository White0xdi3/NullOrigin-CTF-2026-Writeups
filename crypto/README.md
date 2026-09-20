# Cryptography

Eight challenges, chained: each stage's flag unlocks the next stage's files, running from an entry-level linear-algebra recovery through core-dump forensics, format-preserving encryption, real quadratic forms, NAND forensics, and exact tensor decomposition over a finite field. The chain culminates in a meta challenge, **13-lantern**, which is not keyed by any of the seven flags — a team holding all seven flags still can't open it. Instead it's keyed by seven non-flag internal secrets, one reconstructed from each prior stage's own artifact, recombined via a Shamir-like secret-sharing scheme built deliberately over the ring **Z/2^64** rather than a prime field.

| Stage | Name | Difficulty | Hook | Writeup |
|---|---|---|---|---|
| 06 | bindery | Entry | Recover a 121-cell GF(3) linear recurrence's seed from known-plaintext stamps hidden in a padded, statistically flat binary index. | [06-bindery.md](06-bindery.md) |
| 07 | daybook | Entry | Reconstruct a 320-bit permutation from a live RWX memory mapping inside a 420 MB core dump, then recover 128 missing state bits from immediates buried in the emitted code and run the cipher backwards. | [07-daybook.md](07-daybook.md) |
| 08 | errata | Medium | Recover a linear checksum's generator matrix from 1.4 GB of raw logic-analyser capture, using byte-identical trailers across 1,467 heartbeat frames to prove the checksum can't depend on the key. | [08-errata.md](08-errata.md) |
| 09 | catalogue | Medium | Rebuild three unbalanced-Feistel round tables from 50 million index pairs alone, using a translation gauge and majority-vote repair against 9% deliberately poisoned records. | [09-catalogue.md](09-catalogue.md) |
| 10 | carillon | Hard | Tell a class group and a real quadratic cycle apart by the sign of one discriminant, then intersect a Pohlig-Hellman partial result with a fixed-point accumulator window to pin down a single 100-bit exponent. | [10-carillon.md](10-carillon.md) |
| 11 | cartouche | Hard | The key isn't stored on the NAND chip — it's a set of 40 deliberately-written bit flips buried among real bit rot, recovered by majority-voting 32 scrambled shadow copies of a recovery page and taking their combinatorial rank. | [11-cartouche.md](11-cartouche.md) |
| 12 | lastpage | Insane | Uniquely decompose a 512x512x512 rank-512 tensor over a finite field with Jennrich's algorithm and a Krylov-based characteristic polynomial, where every off-the-shelf numerical CP-decomposition tool is meaningless. | [12-lastpage.md](12-lastpage.md) |
| 13 | lantern (meta) | Insane | Reconstruct a degree-6 secret-sharing polynomial over Z/2^64 from seven non-flag secrets pulled out of every prior stage, solving 2-adically through non-invertible pairwise differences and brute-forcing the last 4096 candidates against a GCM tag. | [13-lantern.md](13-lantern.md) |

## Running the solvers

Every stage ships a working reference solver at `<stage>/solve/solve.py`. Each one is self-contained — it only reads the challenge files, reproduces the intended derivation from scratch, and prints the recovered flag. None of them import a private answer key.

```
pip install -r requirements.txt
python3 06-bindery/solve/solve.py /path/to/downloaded/06-bindery
```

The challenge files themselves aren't in this repo — download them from the [release repo](https://github.com/White0xdi3/NullOrigin-CTF-2026) first, then point each solver at the corresponding extracted stage directory.

**13-lantern is the exception**: it re-invokes stages 06 through 12's own `solve.py` as subprocesses (that's the whole point of the meta — it re-derives every prior stage's internal secret rather than trusting a stored value). To run it, keep the sibling layout this repo already uses — `crypto/<stage>/solve/solve.py` — and lay out your downloaded copies of 06-bindery through 13-lantern the same way, side by side in one parent directory, then run:

```
python3 13-lantern/solve/solve.py /path/to/downloaded/13-lantern
```

10-carillon additionally needs `cypari2`, which requires PARI/GP to be installed on your system (`apt install pari-gp` on Debian/Ubuntu, `brew install pari` on macOS) before `pip install` will succeed.
