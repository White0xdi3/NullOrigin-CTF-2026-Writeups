# 26-deadman

**Category:** Reverse Engineering · **Difficulty:** Hard

**Flag:** `Null0rigin{you_held_it_exactly_right}`

**Decoy:** the whole-stage decoy, reached whenever the observer-state gate
below resolves to its "wrong" reading, has its own five-layer system built
the same way as the real one — full rank, genuinely solvable, and reached
by a solver whose debugger relationship with the process doesn't match
what the stage actually wants.

## The mechanism

The tamper trace here doesn't derive a flag — **it seeds the matrix.**
Whichever of two 32-byte hashes is "live" (chosen by a SHA-256 opaque
predicate) seeds a system that the binary builds **one row at a time, on
the stack**, from counter-mode mixing over `hash ^ nonce ^ word_index`,
checked by popcount parity. A mismatch falls through to a *separate* system
seeded from a benign-page hash computed unconditionally, whose unique
solution is the decoy flag `Null0rigin{the_handler_never_lied}`.

The five layers are all variations on one theme: **the observer's own
relationship to the process, measured from inside it.**

| Layer | n | Rank | Mechanism | Real reading | Decoy reading |
|---|---|---|---|---|---|
| L1 | 320 | 320/320 | `TracerPid` transitions over a SIGALRM-sampled window | 3 | 0 |
| L2 | 256 | 256/256 | summed SIGSEGV fault latency against a `PROT_NONE` mapping | slow bucket | fast bucket |
| L3 | 344 | 344/344 | exact single-step (`stepi`) count through a gated region, folded with credential-gated material | mask `0xffffff` | `0x0` |
| L4 | 288 | 288/288 | a hot loop timed with an `int3` planted in its body | slow bucket | fast bucket |
| L5 | 296 | 296/296 | the *order* of attach/detach events over a second sampling window | `0xf0f0` | `0x0000` |

The full attach/step/detach choreography, run against a live process:

1. **L1** — 12 SIGALRM ticks, 80ms apart: detached (0–2), attached (3–5),
   detached (6–8), attached (9–11) → 3 transitions. Ends attached so L2
   finds a live tracer.
2. **L2** — stay attached and forward all 64 SIGSEGVs; the tracer's resume
   of each signal-delivery-stop *is* the kernel round trip being timed.
3. **L3** — single-step the gated region so all 24 `pushfq` checkpoints
   read `TF=1`, then a plain continue through the `sha512crypt` call.
4. **L4** — an `int3` planted at a hot loop's back edge, serviced 300
   times.
5. **L5** — 16 ticks, 60ms apart, attached on ticks 4–7 and 12–15 → `0xf0f0`.

**All five real/decoy rank pairs are full rank**, proved by running
elimination and checking the recovered vector against the intended bytes,
not by trusting the forward construction.

## The break

Reproduce the exact choreography above against the live process — attach,
break, single-step through the gated pages, detach, sleep, re-attach,
continue — while recording the five observer-state measurements as they
happen. The four-way gate that results was confirmed on real runs:

| Arm | Expected | Measured |
|---|---|---|
| choreography + real flag | accept | exit 0 |
| choreography + decoy flag | reject | exit 1 |
| no debugger + decoy flag | accept | exit 0 |
| no debugger + real flag | reject | exit 1 |

Layer 3 additionally folds in the credential standard: `sha512crypt`
output, never the plaintext.

- **Class:** contractor · **base token:** `oaklow` (audited clean against
  rockyou) · **seam:** 14 · **shot:** 203 → password `O4kl0w14203%`
- Seam known: 31,038,000 candidates (~10.4 min full sweep). Seam unknown:
  3.1 billion candidates (~17.3 hours).

## Anti-analysis tricks

- **There is no SIGTRAP handler anywhere in the binary** — proved, not
  asserted: the only installed handlers are for `SIGALRM` and `SIGSEGV`,
  and every occurrence of the string `SIGTRAP` in the source is inside a
  comment. This is deliberate: a real debugger intercepts `SIGTRAP` before
  the tracee ever sees it, so a design that required the *program* to
  catch its own `int3` would stall under the very tool the stage demands.
  Instead the stage polls `TracerPid` from `SIGALRM`, keys on genuine
  `SIGSEGV` fault latency, reads the trap flag via `pushfq` (the tracer
  sets `TF`; the tracee only ever reads its own `EFLAGS`), and reads
  `CLOCK_MONOTONIC` directly.
- **Measured, not guessed, timing thresholds — separated by orders of
  magnitude, not narrow margins.** L2's threshold (300,000 ns) sits 4.33×
  above the slowest native reading and 5.31× below the fastest traced one
  (23× population separation); L4's threshold (70,000 ns) sits 246× above
  native and 241× below perturbed (~59,000× separation). Both thresholds
  are set at the geometric midpoint of the gap, so the margin is balanced
  in orders of magnitude rather than raw nanoseconds.
- **Bidirectional gating, confirmed on real runs**, not just for the real
  flag: choreography plus the real flag accepts; choreography plus the
  decoy rejects; *no* debugger plus the decoy accepts; no debugger plus
  the real flag rejects. The stage genuinely wants a specific debugger
  relationship, not merely "any debugger" or "no debugger."

## Notes

- **A race condition in the transition counter, caught during
  development.** The window used to count `TracerPid` transitions
  initialized its baseline by reading the *live* tracer state at the
  moment the window opened — which depended on whether a debugger happened
  to be attached at that exact instant, a timing detail neither the tracer
  nor the tracee fully controls. Depending on a brief race between a
  detach and a grace-period sleep, the intended
  detached→attached→detached→attached choreography could read either 3 or
  4 transitions. Fixed by always baselining the window at the *untraced*
  state, removing the race entirely — a stage whose required answer
  depends on scheduling noise isn't a stage.
- **A single fault sample doesn't separate the populations — a real
  measurement bug, caught only by actually running it.** An earlier
  single-SIGSEGV design showed native timings (median ~2.3µs, occasional
  ~48µs outliers) *overlapping* with traced timings (30–73µs) — no
  threshold could separate them. This isn't a tuning problem, it's a
  sample-size problem: fixed by summing 64 fault latencies per
  measurement instead of one, so the real signal scales linearly while the
  outliers average out.
- **The augmented-bit collision bug, guarded against explicitly.** An
  earlier version of the GF(2) elimination step augmented each row with
  `b` at bit position `n_bits`, which could collide with unmasked high
  garbage left over from the row generator — a silent-wrong-answer class
  of bug. It's now prevented by masking at both the row-generation and
  augmentation steps, with an internal test asserting the row generator
  never sets a bit at or above `n`; it would also be caught regardless,
  because the elimination routine always re-solves every layer from
  scratch and checks the result against the intended vector rather than
  trusting the forward construction that produced `b`.
- **This stage's checker had the same "shipped unwinnable" defect as
  25-ouroboros, independently.** The board's shared strike-counter checker
  runs the stage binary via `fork`/`execv` and deliberately *never* under
  ptrace (correct for every sibling stage, whose tamper trace treats "not
  traced" as the right reading). 26-deadman inverts that assumption — its
  correct reading *requires* a specific debugger choreography — so the
  shared checker rejected the correct flag and password outright and would
  have locked the stage after three genuinely correct submissions. Fixed
  with a stage-local checker that never runs the choreography or the
  binary itself; it checks the candidate against a baked SHA-256
  commitment and the password against the shipped crypt line, in constant
  time, with one identical message regardless of which was wrong.
- **Flag absence, measured over both shipped binaries:** raw, reversed, all
  16/24-byte fragments, all 255 single-byte XOR keys, all 255 single-byte
  ADD keys, and all 7 bit rotations — clean. A real memory dump taken at
  the verdict `write()` on a run carrying a wrong candidate of the same
  length contains that wrong candidate (proving the dump caught the run)
  but not the real flag, raw or under any XOR key. `.text` SHA-256 is
  byte-identical before and after the runtime parameter patch. A plain
  `strings | grep` against the embedded vault returns 900 flag-*shaped*
  decoy strings and none of them are the real flag.
- **Verification rigor:** 49/49 acceptance checks and 61/61 differential
  checks passed; the four-way gate passed on 6 consecutive independent
  runs (12 choreographed runs total), with identical transition counts and
  step masks every time.
