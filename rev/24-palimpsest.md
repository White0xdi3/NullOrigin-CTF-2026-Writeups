# 24-palimpsest

**Category:** Reverse Engineering · **Difficulty:** Medium

**Flag:** `Null0rigin{the_table_wrote_itself_at_dawn}`

**Decoys:**

| # | Route (the plausible wrong turn) | Lands on |
|---|---|---|
| D1 | Read the bytecode through the plaintext `.data` opcode table instead of the runtime-decrypted one | `Null0rigin{you_trusted_the_first_draft}` |
| D2 | Use the second table under its static (unmoved) key | `Null0rigin{the_key_never_moved}` |
| D3 | Use the un-permuted handler table | `Null0rigin{you_kept_the_filing_order}` |
| D4 | Decode the bytecode aligned instead of shifted | `Null0rigin{you_read_on_the_lines}` |
| D5 | Use the table as it stood at its first decryption, before it self-mutates | `Null0rigin{the_first_reading_held}` |

## The mechanism

This stage's VM doesn't compute a flag — **it evaluates a constraint.** The
"real" verification matrix, `M_real`, is never stored anywhere as a matrix.
It exists only as *(a)* which of 64 checksum-gated opcode slots the
runtime-decrypted table resolves to `LOADCAND` and `XORF`, and *(b)* the
candidate-byte immediates the build placed beside those opcodes in the live
bytecode record. Read the exact same bytecode bytes through the
never-executed `.data` decoy table instead, and a *different* pair of
opcodes takes on those roles — over an independently built, genuinely
solvable system whose unique solution is the D1 decoy above.

`REAL_TARGET` and `DECOY_TARGET` both sit openly in `.rodata` — plaintext,
and meaningless without the resolved matrix; they're bait for anyone who
assumes finding plaintext constants means progress.

This is the last layer of a five-layer cascade, each seeded by a different
answer to the same question — *which semantics are live right now?*:

| Layer | n | Rank | Source |
|---|---|---|---|
| L1 | 352 | 352/352 | runtime-decrypted opcode table |
| L2 | 312 | 312/312 | trace-keyed second table |
| L3 | 280 | 280/280 | checksum-permuted handler table |
| L4 | 248 | 248/248 | shifted bytecode decode |
| L5 | 344 | 344/344 | self-mutated table |

At the real/decoy split (the layer described above): `rank(M_real) = 42`,
`rank(M_decoy) = 38`, with 60 of 64 table entries differing between the two
tables and 2 more forced to differ by construction. Every rank in the table
above was confirmed by running elimination and checking the recovered
vector, not by trusting the forward construction.

One property is board-critical: `.text` SHA-256 is *identical* before and
after the runtime table build finishes. The shared 27-hourglass meta stage
hashes every prior stage binary's `.text` as part of its own gate, so any
stage that perturbed its own `.text` at runtime would silently break every
downstream dependency on it, and no individual solve would ever notice.

## The break

Dump the live (runtime-decrypted) table, decode the bytecode record under
its real semantics, and eliminate. The credential gate on the table's
decryption key is derived from the *output* of `sha512crypt`, never the
plaintext:

```
class      bundle
plaintext  pl-netherburn64180&
base       netherburn        seam 64   shot 180   marker &
rule       ^-^l^p
mask       64?d?d?d?1        blind: ?d?d?d?d?d?1
```

Keying off `SHA256(plaintext)` instead of the crypt output would let a
solver test candidates roughly 5,000× cheaper, deleting the GPU wall
entirely.

Reference solve, measured: **exit 0, 0.365s.** Run without `--password`, it
stops at layer 1 and prints the hashcat line — the intended first
experience for a player who hasn't cracked the credential yet.

## Anti-analysis tricks

- **The debugger corrupts the very thing it's watching.** Layer 3 hashes a
  live window covering nearly all of `.text`. Because the binary ships
  stripped, an ordinary breakpoint set *anywhere* inside that window
  (including at the raw ELF entry point) splices `0xCC` into exactly the
  bytes about to be hashed — a naive `gdb` breakpoint corrupts the checksum
  before it's even read. The reference solve instead uses
  `catch syscall mprotect`, which doesn't touch `.text` at all. It's the
  stage's own lesson, catching the solver who reaches for the obvious tool.
  Verified both ways on the shipped binary: native gives `exit 0`, and gdb
  via `catch syscall mprotect` also gives `exit 0` — a plain breakpoint
  does not.
- **Plaintext bait sitting in the open.** `REAL_TARGET`/`DECOY_TARGET` and
  the never-executed `.data` opcode table are both fully readable and both
  useless without the resolved live table — a decompiler finds "the
  answer" immediately and it's inert.

## Notes

- A late-development correction updated the shipped flag string to its
  canonical form (`the_table_wrote_itself_at_dawn`) after an earlier draft
  had briefly shipped a different string; the binary was rebuilt and the
  corrected string confirmed live before release.
- **Verification:** the reference solve recovers both the real and decoy
  matrices by walking-ones probing and confirms both independently. All
  five layers and all five decoys were solved to confirm each is genuinely
  reachable and genuinely wrong.
