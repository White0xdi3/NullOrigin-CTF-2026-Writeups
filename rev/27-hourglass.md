# 27-hourglass

**Category:** Reverse Engineering · **Difficulty:** Insane — Meta finale

**Flag:** `Null0rigin{you_were_the_input_all_along}`

**Decoy:** `Null0rigin{you_beat_the_clock}` — the thesis of the whole board,
inverted. It's the answer a player most wants to be true (a clean boot
"beats" the anti-tamper system), it's reachable from a completely clean
boot with no debugger and no password, and it's wrong.

## The mechanism

A from-scratch, freestanding kernel (NASM + `gcc -m32 -ffreestanding`),
booted via Multiboot1 under `qemu-system-x86_64 -kernel`. Its round-robin
scheduler **is the VM**: four tasks run across 2000 PIT timer ticks, and
which task ran on which tick folds into a running 32-bit signature, updated
every timer interrupt.

That signature seeds a 512×512 GF(2) matrix at runtime, expanded via
`gen_word`/`triple32` and never stored. The candidate arrives on the
Multiboot kernel command line as a zero-padded 512-bit vector. Accept iff
`A.x == b`. **There is no `if (sig == ...)` branch anywhere** — one single
code path, and which of two different full-rank systems you land in depends
entirely on which signature you produced getting there.

At four fixed tick-count checkpoints (ticks 211, 419, 631, and 839), the
kernel reads a `ctrl` byte out of its own `.data` and, if nonzero, commits
the next 24 ticks to task `(rr + ctrl) & 3` — overriding the scheduler's own
decision. **Nothing in the kernel ever writes that byte.** The kernel has no
idea a correct value even exists. The only thing that can ever set it is a
debugger, attached via QEMU's `gdbstub`, poking a one-shot word into `.ctrl`
at each breakpoint. The four values a correct password implies are derived
from the `sha512crypt` **output**, never the plaintext.

So the anti-tamper counters don't gate the flag — **they feed it.** A clean
run cannot produce it, because the missing input the scheduler needs was
never going to appear on its own. You were supposed to be debugged.

| Layer | n | Rank | Measurement | Decoy |
|---|---|---|---|---|
| L1 | 224 | 224/224 | PIT tick signature prefix, snapshotted at tick 211 | a pure fencepost — snapshot one tick off |
| L2 | 256 | 256/256 | final signature under the four checkpoint overrides | the clean (un-overridden) signature |
| L3 | 192 | 192/192 | interrupt-nesting pattern (which checkpoints actually fired) | the flat-nesting assumption |
| L4 | 208 | 208/208 | TSC delta across the halted vCPU, bucketed to a single bit | the wall-clock-duration assumption |
| L5 | 320 | 320/320 | the order the four tasks completed | strict round-robin |

L1 is *deliberately* boot-invariant: its snapshot is taken at tick 211,
before any override could possibly have taken effect, so clean and
choreographed boots produce the identical value. Its "decoy" exists purely
as a fencepost so the cascade engine has a distinguishable sibling system
at every layer — L1 is simply correct on every boot, clean or not.

**Why L4 keys on attachment, not duration.** Under TCG virtualization
(without hardware `/dev/kvm` acceleration), QEMU's emulated TSC does not
track host wall-clock time while the guest vCPU is halted at a breakpoint —
a scripted two-second real pause measures identically to an instant
continue. So L4 keys on *being attached and hitting a breakpoint at all*,
never on how long the pause lasted, bucketed at a 600,000-cycle threshold.

**The decoy resolves at layer 2.** A completely clean boot — no debugger,
no password, nothing — reproduces L1 (correct by construction) and then
falls straight into L2's decoy: `Null0rigin{you_beat_the_clock}` falls out
for almost no work. Layers 3–5 are never even reached. It's still gated
behind all six prior flags (the meta hash is folded into every layer seed,
decoys included), so it's not reachable by a passerby — only by someone
who cleared the whole chain and then stopped one step short of the idea.

### The meta gate

Every layer's seed is built from a domain string that folds in all six
prior flags:

```
"27-hourglass|meta|" + SHA256(the six prior flags, joined by "|", IN ORDER)
```

A wrong flag, a missing flag, or the right six flags in the wrong order all
produce a different domain — different seeds, different matrices, and a
walk with no unique solution. Exercised directly against the shipped
binary, with the correct candidate flag and password and only the six
prior flags varied:

| Case | Result |
|---|---|
| canonical six, in order | accepted (exit 0) |
| reversed stage order | rejected (exit 1) |
| five-of-six, sixth replaced with a wrong string | rejected (exit 1) |
| five-of-six, sixth simply dropped | rejected (exit 1) |
| an earlier, superseded flag string for 24-palimpsest | rejected (exit 1) |

Six flags are necessary, not sufficient — a further test matrix also
confirms the decoy flag, a wrong password, and a one-character near-miss
flag all reject given the canonical six.

## The break

Recover the parameter blob from the shipped binary (it ships with no
separate parameter file, by design — finding it is part of the job), work
out the four-value choreography implied by the cracked password, run a
real boot under a real gdb session poking `.ctrl` at each checkpoint, then
run five eliminations strictly in order using the resulting signatures. The
reference solve does this end to end in about 8.4–8.6 seconds of actual
work (11.81s including a fresh qemu boot).

Measured signatures, 15 boots of each kind, all bit-identical within their
kind:

| | prefix | final signature | nesting | completion |
|---|---|---|---|---|
| clean boot | `9a938e86` | `411656fd` | `00` | `e4` |
| choreographed boot | `9a938e86` | `a71487fd` | `0f` | `c6` |

`prefix` is identical across both — L1's boot-invariance holding exactly as
designed. The other three all differ, which is what L2, L3, and L5
respectively measure.

## Anti-analysis tricks

- **The anti-tamper mechanism has no legitimate way to succeed on its
  own.** The scheduler override byte is written by nothing in the kernel —
  there's no "solve this and defeat the anti-debug" path, because the
  correct behavior requires the very thing the anti-debug logic looks like
  it should be defending against.
- **A hardware-timing constraint turned into a design choice rather than
  patched over.** QEMU's TCG mode doesn't track wall-clock time while a
  vCPU is halted at a breakpoint, so a naive "how long did they pause"
  design would have been unmeasurable. Rather than fighting the emulator,
  the stage keys on the one signal that reliably does hold: being attached
  and hitting a breakpoint at all costs on the order of 300K–1.7M cycles
  against a clean run's few hundred.
- **The meta gate feeds every layer's seed**, so there's no separate "check
  the six flags, then solve the puzzle" step to isolate and skip — the
  wrong prior flags don't produce a rejection message, they produce a
  system with no solution at all.
- **32-bit protected mode via Multiboot rather than long mode with a custom
  bootloader** — a deliberate reliability trade-off for a from-scratch
  kernel, documented as a scope choice rather than left unexplained.

## Notes

- **A Python reference checker was retired after it was broken during
  development, and the compiled replacement is the direct consequence.**
  An earlier build shipped the checker as a standalone Python script,
  which meant shipping a full Python port of the kernel's own scheduler
  logic alongside it so it could run without booting a VM. Having that
  port in hand made every one of the five measurements computable purely
  offline: an attack script recovered the correct flag in 0.038 seconds
  with zero boots of the kernel, reproducing every measured value exactly.
  That's not a narrow bug to patch — once a faithful scheduler port exists
  outside the kernel, "you were the input all along" becomes a simulation
  you can run without ever being the input. The checker is compiled and
  stripped now, and the Python port is kept only as an internal reference,
  never shipped.
- **Keeping the shared verification engine unmodified required a small,
  careful trick.** The shared cascade engine expects its per-stage domain
  string as a compile-time string literal, but this stage's domain isn't
  known until runtime — it contains the hash of six flags supplied on the
  command line. Rather than forking a second copy of the domain-derivation
  logic into a stage-local header (which is exactly how an earlier board
  iteration once shipped a stage whose real mechanism was never actually
  engaged), the domain is instead built into a fixed-size buffer sized to
  the exact length that string always has, so the shared engine hashes
  precisely the bytes it would have hashed for a literal.
- **The parameter file that used to ship was itself a shortcut, and was
  dropped for it.** It's not shipped for the same reason no sibling stage
  ships one (finding the blob in the binary is part of the job) — and,
  specifically for this stage, because that file also contained the raw
  SHA-256 digest of the six prior flags. Shipping it would have handed
  every player a free, instant, offline oracle for guessing the six-flag
  set with no boot and no strike cost; the compiled binary itself is not
  such an oracle; it costs a real ~5-second boot-and-attach per attempt.
- **The reused 3 GB machine image from an earlier build had a real gap,
  which the final build closed.** The original machine image had the decoy
  string sitting in it as greppable plaintext (inherited bulk that predated
  a later rework, and out of scope to regenerate at the time). The current
  12 MB image is purpose-built instead: filler bytes are engineered so no
  accidental five-plus-letter run of lowercase text can appear, the
  intended vocabulary (3,273 tokens) and ~1,400 flag-shaped decoy strings
  are planted deliberately, and neither the real flag nor the decoy is
  ever written into it, forward or reversed — checked automatically at
  build time. The real flag has no such gap in the current build, in any
  shipped file or a real memory dump.
- **Known, accepted property: the four-value choreography is only an
  81-way space** (`ctrl_sequence_from_shadow` produces four values from a
  3-symbol alphabet). A solver who has understood the mechanism can, in
  principle, brute-force all 81 sequences directly against the boot loop
  instead of cracking the password — at roughly 5 seconds a boot, about 7
  minutes expected. This is recorded rather than closed because it isn't
  actually a shortcut: the credential itself is calibrated to about 3.3
  minutes expected on the board's reference GPU (`hashcat -m 1800`, ~19.6M
  keyspace, ~49.7 kH/s), so the intended password path is cheaper than the
  brute force, and both require finding the mechanism first.
- **Verification rigor:** every layer's rank was confirmed by rebuilding
  the matrix from its seed, solving it against the `b` vector read directly
  out of the shipped binary, and comparing the recovered vector to the
  intended bytes. All five decoys were solved independently and confirmed
  to land only on the decoy flag, never the real one. The compiled checker
  was proven equivalent to the Python reference it replaced by the only
  test that can prove it: the compiled binary accepts the real flag against
  parameters the Python engine built, which can't happen unless every
  shared derivation function agrees bit-for-bit, five layers deep.
