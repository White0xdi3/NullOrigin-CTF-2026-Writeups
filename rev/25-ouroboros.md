# 25-ouroboros

**Category:** Reverse Engineering · **Difficulty:** Hard

**Flag:** `Null0rigin{you_found_where_it_eats_its_own_tail}`

**Decoys:**

| # | Route (the plausible wrong turn) | Lands on |
|---|---|---|
| D1 | A collision between neighboring headers instead of a true fixed point — check `decrypt(i)` against `decrypt(i-1)` rather than against `i` itself | `Null0rigin{you_matched_the_wrong_neighbor}` |
| D2 | Settle for a 12-bit near-miss instead of the real 20-bit match | `Null0rigin{almost_ate_its_own_tail}` |
| D3 | Key the decryption from the ciphertext instead of the plaintext guess — `SHA256(ciphertext)` instead of `SHA256(guess)`; needs no search at all, which is part of why it tempts | `Null0rigin{you_hashed_what_was_already_locked}` |
| D4 | CRC over the whole 68-byte record (trailer included) rather than the 64-byte covered range | `Null0rigin{you_checked_the_whole_thing}` |
| D5 | Hash the key-material window at its virtual address (treating an address as a file offset) instead of its real file offset | `Null0rigin{you_read_the_wrong_copy}` |

Every decoy is confirmed full rank and solves cleanly on isolated inspection
— proof that each wrong turn *looks* like a complete, valid answer, not a
claim that typing it into the binary prints "accepted" (it doesn't, any
more than a decoy does on 21-cinder or 22-dovetail).

## The mechanism

Ouroboros's original idea survives in full: `CIPHERTEXT = P xor
KS(SHA256(P[:16]))` — the key is a slice of the very plaintext it encrypts.
Five distinct layers apply that same idea five different ways, each posing
"find the value that makes this construction agree with itself" as a
search rather than a lookup, none reused from the earlier stages:

| Layer | n | Rank | Mechanism |
|---|---|---|---|
| L1 | 256 | 256/256 | a fixed ciphertext, decrypted under a searched 8-byte header whose decryption must reproduce the header's own low 20 bits |
| L2 | 288 | 288/288 | a hash-derived 8-byte string `x` such that `SHA256(x)`'s low 20 bits equal `x`'s own low 20 bits — a partial fixed point |
| L3 | 320 | 320/320 | a fixed 16-byte ciphertext, decrypted under a searched 16-byte plaintext guess whose own SHA-256 is the key — gated by `ouroboros_gate()` (see below) |
| L4 | 256 | 256/256 | a 64-byte record whose CRC-32 covers a 4-byte candidate embedded *inside* the range the CRC itself covers, searched until the CRC's low 20 bits equal the candidate's |
| L5 | 384 | 384/384 | this file's own `.text` window, hashed live and used as key material to decrypt a second, disjoint window elsewhere in the file — the loop closing on itself |

L1's header additionally folds in the credential standard's `sha512crypt`
output, recomputed live from the supplied password every run.

Every search here uses a 20-bit partial-match predicate (expected cost
~2^20 tries) — a deliberate, documented scale-down from a literal reading
of the original design spec (which would have made L2 a 32-bit search) so
the whole five-layer cascade stays something a solver actually finishes.
Measured, single process, cold:

| Layer | Tries | Time |
|---|---|---|
| L1 — searched header | 2,624,045 | 4.48s (Python; ~0.20s in C) |
| L2 — partial hash fixed point | 839,636 | 0.55s |
| L3 — self-keyed plaintext (forced build only) | 957,282 | 1.46s |
| L4 — self-covering CRC | 702,237 | 0.14s |
| L5 — text keys a second section | 149,722 | 0.98s |

All five landed within an order of magnitude of the 2^20 target. The
per-layer search cap is 2^24 rather than a tighter bound: a hand-solved
check found that L4's decoy path (never on the path a player actually runs)
reduces to a linear system over GF(2) with exactly 2^12 solutions in the
full 32-bit space, and one of those solutions happened to land just past a
tighter cap — raising the cap to 2^24 costs nothing on the real path (which
stays comfortably under 2^21 everywhere) and removes the problem
everywhere else.

### The CPUID gate

`ouroboros_gate()` returns true only when `CPUID` reports both Intel VT-x
(leaf `01H`, `ECX` bit 5) **and** AMD-V (leaf `80000001H`, `ECX` bit 2)
simultaneously. No physical CPU reports both — a CPU is one vendor's
silicon or the other's, never both — so `ouroboros_gate()` is false on
every real machine, on every real run. L3's measurement therefore *always*
computes the decoy value on real hardware, the same way 21-cinder's opcode
table branches on a password-derived digest match and its tamper trace
branches on `TracerPid`.

**The consequence, measured directly:** because every non-final layer's
live check hashes the candidate first, and a decoy's target is raw flag
bytes, the **shipped binary accepts nothing at all — not the real flag, not
any decoy, nothing** — under normal execution. The real flag is recovered
entirely offline: extract both baked (real and decoy) targets for every
layer from the file (always present, never hidden — only the runtime's own
branch decision is hidden), reimplement every measurement, and walk the
real branch for L3 in software. That recovers the flag in 7.09s of
elimination (25.6s end to end). What that recovered string *cannot* do is
make the shipped binary itself say "accepted" — proving that, rather than
merely asserting it, is the reason a second, never-shipped proof binary
exists (below).

## The break

Recover both the real and decoy target material for every layer directly
from the file (they're always present in the clear), reimplement each of
the five measurements, and walk the real branch of L3 in software rather
than relying on the gate ever passing at runtime.

Layer 1's key is derived from the `sha512crypt` *output*, recomputed from
the supplied password every run — never a stored plaintext or a stored hash
to compare against:

```
hashcat -a 6 -m 1800 ouroboros.shadow vocab.txt '13?d?d?d?1' \
        -1 '!@#$%&' -j 'c sa4 se3 si1 so0 ss5' -w 4 --hwmon-temp-abort 95
```

- **Class:** contractor · **base token:** `hollinrake` (audited absent
  from rockyou) · **seam:** 13 · **shot:** 071 → password
  `H0ll1nr4k313071%`
- Vocabulary: 3,668 harvested tokens, 694 (18.9%) already in rockyou. Seam
  known: 22,008,000 candidates (~7.4 min full sweep). Seam unknown: 2.2
  billion candidates (~12.3 hours).

## Anti-analysis tricks

- **An unsatisfiable hardware gate as the intended "trap door."** The
  CPUID check isn't a bug to route around quietly — it's the stage's own
  name and thesis made literal: the shipped binary is a closed door on
  purpose, and the real flag is proven correct against a *separate*,
  never-shipped build compiled with `-DOUROBOROS_FORCE_GATE=1`, from
  identical source and identical parameters, changing nothing else.
  Measured back to back on the same flag and password: the unforced binary
  rejects (exit 1), the forced one accepts (exit 0).
- **Self-referential constructions across all five layers** (fixed points,
  self-keyed ciphertexts, a CRC that covers its own candidate, a hash of
  the file used to decrypt another part of the same file) resist static
  analysis because there's no external secret to locate — only a
  self-consistency condition to satisfy by search.
- **Every non-final layer hashes the candidate before comparing**, so a
  decoy's target being raw flag bytes doesn't let a lucky guess short-
  circuit anything; it just produces a clean, wrong, fully-formed flag.

## Notes

- **The stage originally shipped unwinnable, found by running the checker,
  not by reading it.** The board's shared strike-counter checker decides
  accept/reject by running the stage binary itself and reading its exit
  code — correct for every other stage, wrong here, because this is the
  one stage whose own binary accepts nothing by design. Submitting the
  correct flag and password produced "rejected," charged a strike, and
  three correct submissions would have locked the stage forever. The fix
  was a **stage-local checker** that never runs `ouroboros` at all — it
  compares two SHA-256 digests supplied at build time (one of the flag,
  one of the crypt line that already ships in the clear in the shadow
  file) and accepts only if both match. No plaintext of the flag or
  password appears in it or anywhere else shipped. A test that had
  encoded the original defect as its own expected behavior ("the checker
  correctly rejects the real flag") was rewritten to check what actually
  matters: does the checker accept the right answer, at no strike cost.
- **A second, independent bug caught while building the proof binary.**
  The first attempt at the forced/unforced comparison had *both* binaries
  reject the real flag. Root cause: the forced compile flag
  (`-DOUROBOROS_FORCE_GATE=1`) changes compiled code, not just data — it
  shrinks `ouroboros_gate()`'s body by removing the two CPUID call sites,
  which shifts the linker's layout of everything after it. The forced and
  unforced binaries therefore do *not* share identical `.text` at the same
  file offsets (548,910 bytes differ outside the shared parameter window).
  Layer 5's target had been measured against the *unforced* binary's
  `.text` and then patched into both — so the forced binary could never
  match it either. Fixed by linking both binaries first, then measuring
  layer 5 specifically against the binary it needs to be true for. This is
  the same "solve it, don't assert it" discipline applied a second time,
  independently catching a second way a proof build could silently test
  nothing.
- **A credential-hashing design choice, explained.** The stage-local
  checker hashes the *crypt line* (the `$6$...` string), not the plaintext
  password, for the same reason every credential gate on this board is
  keyed off the crypt output: hashing the plaintext directly would have
  reduced the password-cracking cost by roughly 5,000× and deleted the
  intended GPU-bound wall, even though that string is only used for a
  final accept/reject decision here.
- **Every run of the shipped binary is slow, by construction, regardless
  of input.** The verification loop never branches early on how far a
  candidate got — it always runs every layer to completion, so layer 5's
  search always runs to its full 2^24 iterations on the unforced binary
  (whose target it can never actually match). Measured: 5.25s per run,
  every time, hot or cold — not a cache effect. The stage-local checker is
  exempt: since it never launches `ouroboros`, submitting an answer costs
  milliseconds even though inspecting one costs over 5s.
- **A filesystem-bridge performance trap, recorded for anyone re-running
  this.** Running the checker binary from a network- or cross-filesystem
  mount multiplies per-syscall latency across the up-to-2^24 `pread()`
  calls layer 5's search performs on the unforced binary — turning a ~5s
  run into several minutes. Confirmed as an environment artifact, not a
  stage property, by re-timing an identical byte-for-byte copy on a native
  filesystem (back down to 5.25s). A related trap existed in the reference
  solver itself: an early version reopened the target file on every single
  search candidate, which is cheap on a native filesystem but turned a
  ~10s solve into over two and a half minutes on a bridged one — fixed by
  opening the file once and reading the whole candidate span into memory
  up front.
- **Flag absence, re-measured after the checker fix, over all four shipped
  files:** not present as plaintext, reversed, or any 16/24-byte fragment;
  not under any of 255 XOR keys, 255 ADD keys, or 7 bit rotations; the flag
  body without its braces is absent too, as is the password plaintext and
  all five decoys. A real memory dump was taken for both shipped binaries
  on a run carrying a wrong candidate — the wrong candidate is present
  (proving the dump caught the run), the real flag is not. The checker
  does carry, checked for positively: the two SHA-256 digests as hex, and
  the salt (which ships in the shadow file anyway) — it does not carry
  `SHA256(password)`.
