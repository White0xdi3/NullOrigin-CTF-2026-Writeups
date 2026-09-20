# Reverse Engineering — NullOrigin CTF 2026

Seven stages, chained end to end. Each stage's flag unlocks the next stage's
embedded corpus; the seventh is a meta finale keyed off all six prior flags.

## Design philosophy

Every stage on this board is a **keygen-me**. No binary computes the expected
flag and compares it to your input. Instead, verification is a property
check performed on your candidate:

```
accept  iff  A . x == b     (over GF(2))
```

`x` is your candidate's bit vector, `A` is a matrix generated at runtime and
never stored anywhere, and `b` is the only thing actually baked into the
binary. `A` is constructed to be full rank, so the system has exactly one
solution: recover `A` and `b`, run Gaussian elimination over GF(2), and the
flag falls out. **The flag does not exist inside any binary, at any point,
in any buffer.** A memory dump taken at the moment of comparison yields a
matrix, not a string. Static analysis yields a matrix. The only route to the
answer is to reconstruct a solution.

Layered on top of that, every stage also ships a **second, complete,
full-rank system** — reachable via the route a static analyst finds first,
or the mathematically "correct" way of computing some measured value. Its
unique solution is that stage's **decoy**: valid ASCII, correct flag shape,
nothing marking it as wrong. Solving it feels exactly like solving the real
thing. It is a tax on success at the wrong task, not a punishment for
failure.

Finally, every stage gates at least one control-flow decision on a SHA-256
comparison over a runtime-computed value. A symbolic execution engine cannot
invert SHA-256, so a solver that tries to reason about the binary
symbolically stalls rather than explores — forcing real, concrete execution
that a file-only, non-interactive solver cannot perform.

### Why the board looks like this

This was not the original design, and the reason is worth stating plainly.
Earlier iterations of this challenge board had shortcuts that let automated,
non-interactive analysis skip the intended mechanism entirely and land on
the flag directly:

- One earlier build simply **printed the real flag** on a plain run for
  several stages — every "solve" was really just running the program and
  reading its own stdout.
- Another earlier build derived the flag from the shipped bytes via a
  **single cheap transform** (a one-byte XOR), so a hex dump and one XOR
  pass recovered it without the intended mechanism ever being engaged.

Both failures were structural, not the result of a single weak trick: a
binary that computes the expected flag and compares it against your input
always leaves that answer sitting somewhere in its own execution, and making
the derivation longer only ever slowed down someone reading it off directly.
The board was redesigned around the rule above — there is no extractable
secret at any point, because there is no secret. Only a property that a
correct vector happens to satisfy.

That doesn't mean these stages are unbeatable by tooling in general, nor is
that the goal. It means arriving at the answer without doing the reversing
is no longer on the table.

## The story, in order

| Stage | Beat |
|---|---|
| 21 | the drive was still warm when they pulled it. they wrote 'inert'. |
| 22 | you are holding one joint of something longer. you are not the first. |
| 23 | it has been measuring you since you typed the first command. |
| 24 | the version you spent an hour understanding does not exist. |
| 25 | you have been reading its handwriting for three boards. |
| 26 | it wanted to be debugged. the lock was never the lock. |
| 27 | there was no intruder. null origin. nothing came before it. |

Stage 25's beat retroactively reframes the two boards before it. Stage 27's
beat is the ending of all six stages that came before it.

## Stages

| # | Name | Tier | Hook | Writeup |
|---|---|---|---|---|
| 21 | Cinder | Easy | A 50,000-round pointer chase through a 230 MB dump seeds a matrix that exists only on the stack. | [21-cinder.md](21-cinder.md) |
| 22 | Dovetail | Easy | A lying ELF section header sends static tools to a fully-formed, fully-wrong decoy system. | [22-dovetail.md](22-dovetail.md) |
| 23 | Quicklime | Medium | Five different ways the FPU disagrees with "correct" IEEE math — and doing the math right is the trap. | [23-quicklime.md](23-quicklime.md) |
| 24 | Palimpsest | Medium | A bytecode VM whose opcode table is rewritten at runtime; the plaintext table in `.data` is bait. | [24-palimpsest.md](24-palimpsest.md) |
| 25 | Ouroboros | Hard | Five self-referential fixed points, gated behind a CPUID check no physical CPU can satisfy. | [25-ouroboros.md](25-ouroboros.md) |
| 26 | Deadman | Hard | The debugger relationship itself — TracerPid transitions, fault latency, single-step counts — is the input. | [26-deadman.md](26-deadman.md) |
| 27 | Hourglass | Insane (Meta) | A from-scratch kernel's scheduler is the VM; the anti-tamper counters don't gate the flag, they feed it. | [27-hourglass.md](27-hourglass.md) |

## A note on how these stages evolved

Stages 21–26 (and the framework 27 sits on) went through a significant
rebuild during development: an original single-system-per-stage design was
replaced with a **five-layer cascade** per stage — five chained GF(2)
systems, each seeded by a transcript that folds in every prior solution and
measurement, so later layers cannot even be constructed until earlier ones
are solved. Each of the five layers carries its own decoy. The writeups
below describe the final, shipped cascade design for each stage, since that
is what the released binaries actually implement.
