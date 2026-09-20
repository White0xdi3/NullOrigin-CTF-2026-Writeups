# 21-cinder

**Category:** Reverse Engineering · **Difficulty:** Easy

**Flag:** `Null0rigin{you_stepped_where_it_would_not_read}`

**Decoys:**

| # | Route (the plausible wrong turn) | Lands on |
|---|---|---|
| D1 | Walk the embedded dump with `span = len` instead of `len - 8` | `Null0rigin{ash_is_all_you_get}` |
| D2 | Compute the mathematically correct sine instead of running the x87 `FSIN` instruction | `Null0rigin{the_sine_was_never_the_point}` |
| D3 | Read the VM bytecode through the plaintext `.data` opcode table | `Null0rigin{you_read_the_table_you_were_shown}` |
| D4 | Assume the task scheduler is strict round-robin | `Null0rigin{round_and_round_and_wrong}` |
| D5 | Measure the tamper trace with a debugger attached | `Null0rigin{the_debugger_saw_a_different_file}` |

D1 is also reachable as a standalone, statically-baked 240×240 system sitting
behind the same dead `call decoy_entry` bait that the real entry redirect
walks past — plus roughly 4,200 flag-shaped decoy strings salted through the
corpus for anyone grepping.

## The mechanism

The binary verifies candidates by checking `A·x == b` over GF(2), where `A`
is generated at runtime and never stored, and the unique solution `x` to
that system *is* the flag. There is no comparison against a precomputed
answer anywhere in the program.

That system isn't solved in one step — it's the last of a **chain of five**:

```
A1.x1 = b1  ->  seed(A2)  ->  A2.x2 = b2  ->  ...  ->  A5.x5 = b5,   x5 = flag
```

Each layer's seed is `SHA256(DOMAIN | stage | k | t_{k-1} | source_k)`, where
`t` is a running transcript that folds in every previous solution *and*
every measurement taken along the way. Layer `k` literally cannot be
constructed until layer `k-1` has been solved — the five layers must be
walked in order; there's no shortcut from having partial information about
several of them at once. The inner vectors `x1..x4` aren't independent
secrets either — they're counter-mode SHA-256 expansions of the whole
candidate. That's precisely what lets the binary *verify* without ever
*solving*: it hashes forward, builds each matrix a row at a time on the
stack, and checks parity.

| Layer | n | Rank | Mechanism |
|---|---|---|---|
| L1 | 376 | 376/376 (full) | pointer chase over the embedded corpus |
| L2 | 320 | 320/320 (full) | x87 `FSIN` divergence |
| L3 | 288 | 288/288 (full) | VM under the credential-gated live opcode table |
| L4 | 256 | 256/256 (full) | scheduler signature |
| L5 | 376 | 376/376 (full) | tamper trace |

Every rank above was obtained by *running* Gaussian elimination and checking
that the recovered vector matches the intended one — not by trusting the
forward construction that produced `b`.

**L1 — the pointer chase.** `A` is a 376×376 matrix built at runtime from a
50,000-round pointer chase over the embedded 230 MB corpus: read 8 bytes at
the current offset, mix them into a 64-bit state, and let those bytes pick
the next offset. The final state is expanded through `splitmix64` into the
matrix. `b` is 47 baked bytes. An opaque predicate — `SHA-256(matrix_buf[0:32])`
compared against a baked digest — gates progress past this layer.

The entry point itself is obfuscated: `_start` folds an FNV-1a-64 hash over
145 bytes of its own code (via a RIP-relative `lea`), masks the low 14 bits
of the result, and jumps to the computed address — landing one byte into
`real_check_thunk`, where the bytes `B8 EB 24 00 00` decode as
`mov eax, 0x24eb` from the boundary and as `jmp rel8` from one byte later.
No `.rodata` qword anywhere holds this jump target; it's computed, not
stored. An 8-byte inert filler at the tail of the checksummed range was
brute-forced at build time (~17,000 FNV-1a tries) so the checksum lands
exactly.

**L2–L5** reuse this board's shared mechanisms (the x87 FSIN divergence, the
credential-gated VM, the round-robin scheduler signature, and the
TracerPid-based tamper trace — each described in more depth in later
stages), scoped to this stage's own domain separator.

## The break

Reproduce the pointer walk to recover `A1`, read `b1` from the binary, and
run GF(2) Gaussian elimination — then repeat for each subsequent layer,
using the previous layer's solution to seed the next. In practice this was
solved with a Python script that reproduces the runtime derivation for each
layer and runs GF(2) elimination in sequence, recovering the flag from the
shipped artifact in about 0.11s of elimination and 1.70s end to end.

Layer 3's opcode table is decrypted under a key derived from the *output* of
`sha512crypt`, never from a plaintext password — so a candidate password can
only be tested by paying one full 5,000-round `sha512crypt`, not a cheap
SHA-256 over the guess. Cracking it:

```
hashcat -a 6 -m 1800 cinder.shadow vocab.txt '78?d?d?d?1' \
        -1 '!@#$%&' -j 'c' -w 4 --hwmon-temp-abort 95
```

- **Class:** staff · **base token:** `hollinrake` (audited absent from
  rockyou) · **seam:** 78 · **shot:** 037 → password `Hollinrake78037@`
- Vocabulary harvested from the dump: 5,172 `[a-z]{5,}` tokens, 914 (17.7%)
  already in rockyou; the author's base token is picked from the remainder.
- A planted "lamp account" card in the corpus discloses the seam number,
  narrowing the *mask*, not the wordlist — narrowing the wordlist instead was
  measured to be a placebo, since a short list can't keep a GPU fed and
  gives back in throughput what it saves in keyspace.
- With the seam known: 31,032,000 candidates (~10.4 min full sweep at
  49,700 H/s). With the seam unknown: 3.1 billion candidates (~17.3 hours).

## Anti-analysis tricks

- **Computed, not stored, control flow.** The real entry redirect is an
  FNV-1a hash of the binary's own code, masked and jumped to — there is no
  static jump table entry for a disassembler to find.
- **Overlapping instruction encoding.** The same five bytes decode as two
  different instructions depending on which byte you land on, so a
  disassembly pass that starts at the "obvious" boundary reads the wrong
  one.
- **Opaque predicate on SHA-256.** `SHA-256(matrix_buf[0:32])` vs a baked
  digest between the walk and the matrix step stalls symbolic execution
  outright — z3 cannot invert SHA-256, so a symbolic solver can't reason
  past this branch and has to fall back to concrete execution.
- **Fully stripped binary.** No local symbol sits at the overlap offset, so
  a disassembler gets no resync point and can't expose the real path.
- **Debugger-aware tamper trace (L5).** TracerPid is folded into the final
  layer, so *attaching a debugger changes which system you're solving.* A
  player who runs the finished binary under gdb to confirm their own
  correct flag will be told it is wrong — that's the L5 decoy doing its
  job, and it cuts both ways.
- **Anti-patch.** Flipping a single bit inside the tamper-checksummed
  window makes the binary reject the real flag; there's no patch that turns
  this into a "printer," because there's nothing to print.

## Notes

- **A real build bug:** a `.bss` symbol referenced with an index register
  inside the checksummed range fell back to absolute addressing, whose
  value turned out to be corpus-size-dependent — this broke a two-pass tune
  build. Fixed by moving that scratch buffer to the stack.
- **Cold-cache timing:** first run pays ~1.18s for the 50,000 dependent
  random reads over 230 MB; a warm run completes in single-digit
  milliseconds. Recorded rather than hidden, since a player's first run is
  always the cold one.
- **Architectural assumption:** layer 2 keys on the x87 `FSIN` result for a
  large argument, specified by the 66-bit pi constant both Intel and AMD
  implement. A machine whose FSIN implementation diverges from that
  reference would make this stage unsolvable there — the one assumption on
  this stage that isn't purely self-contained.
- **Verification rigor:** 56 internal engine checks (GF(2) arithmetic,
  masking, serial-dependency proofs), 84 differential checks (C vs. Python,
  run against a probe binary that includes the shipped C source directly so
  the functions under test are literally the shipped ones), and 32
  end-to-end checks against the shipped artifact.
- **Flag absence, measured, not assumed:** not present as plaintext,
  reversed, or any 16/24-byte fragment; not recoverable under any of the
  255 single-byte XOR keys, 255 ADD keys, or 7 bit rotations; absent from a
  real memory dump taken while the process was stopped at its verdict
  `write()`, run with a *wrong* candidate. None of the five decoys is
  stored anywhere either — they exist only as solutions to their own
  systems.
