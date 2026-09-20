# 22-dovetail

**Category:** Reverse Engineering · **Difficulty:** Easy

**Flag:** `Null0rigin{the_loader_never_read_the_label}`

**Decoys:**

| # | Route (the plausible wrong turn) | Lands on |
|---|---|---|
| D1 | Seed the walk from the `SEED` value the lying section header points at | `Null0rigin{you_followed_the_headers_home}` |
| D2 | Keep parsing PNG chunks past `IEND` | `Null0rigin{the_image_never_ended}` |
| D3 | Run the bytecode through the plaintext `.data` opcode table | `Null0rigin{the_label_said_otherwise}` |
| D4 | Assume the task scheduler is strict round-robin | `Null0rigin{four_tasks_one_order}` |
| D5 | Measure the tamper trace with a debugger attached | `Null0rigin{observed_is_not_the_same}` |

D1 is also a standalone, fully baked 328×328 system: a complete matrix and
target sitting at file offset `0x2000`, solvable by elimination alone with
no execution required at all — which is exactly what makes it tempting.

## The mechanism

This binary has three `PT_LOAD` segments. Two of them map file offset
`0x1000` to virtual addresses `0x500000` and `0x600000` — and a `.rodata`
section header *lies*, claiming that `0x600000` is backed by file data at
offset `0x2000`. That lie is real bytes in the file, at offset `0xb8b20`
(119,804 bytes), covered by **no** `PT_LOAD` — verified against the program
header table, not assumed. The kernel has never read it.

Following the header (as `readelf -S`, `objdump`, and most decompilers do
by default) gets you a complete, fully baked, full-rank 328×328 system — a
clean elimination with no execution needed, landing on a valid, wrong flag.
The lie doesn't just pick which string you decode; **it picks which entire
cascade you solve.** The section header claims the job is one system long
(`nlayers = 1`). It's actually five, chained:

```
A1.x1 = b1  ->  seed(A2)  ->  ...  ->  A5.x5 = b5,   x5 = flag
```

| Layer | n | Rank | Mechanism |
|---|---|---|---|
| L1 | 344 | 344/344 (full) | walk over the reused 240 MB `dovetail.png` "plate" |
| L2 | 320 | 320/320 (full) | walk over the PNG *container* (chunk types, lengths, CRC-32s) |
| L3 | 288 | 288/288 (full) | VM under the credential-gated live opcode table |
| L4 | 256 | 256/256 (full) | scheduler signature |
| L5 | 344 | 344/344 (full) | tamper trace |

L1 and L2 are this stage's own; L3–L5 are the board-level mechanisms
(credential-gated VM, scheduler signature, tamper trace) scoped under this
stage's own domain separator, so no value is shared with 21-cinder even
where the *derivation* is identical in shape.

**L1 — the real read.** Only the kernel-honoured mapping matters:
`[SEED:8][N_BYTES:1][B:43]`. `SEED` seeds a 50,000-round walk over the
reused 240 MB `dovetail.png`; the walk's final state expands into a fresh
344×344 matrix, built in a stack buffer every run and written nowhere. The
comparison itself — `A.x == B` — is a hand-written parity-based row compare
in raw NASM with no libc involved. An opaque predicate
(`SHA-256(final_state)` vs. a baked digest) gates progress between the walk
and the matrix step.

**L2 — the container walk.** A second walk over the PNG's own chunk
structure: chunk types, lengths, and CRC-32s, stopping at `IEND`. The plate
has eight *extra* chunks after `IEND` with real four-letter type codes,
plausible lengths, and deliberately wrong CRCs. The walk folds CRC validity
in as a *value* rather than raising an error on mismatch — so a parser that
doesn't stop at `IEND` gets a clean (wrong) answer instead of a crash, which
is the only kind of wrong turn that actually costs a solver time.

## The break

`readelf -l` (program headers, what the kernel honours) against `readelf -S`
(section headers, what most tools read) immediately exposes the lie. Follow
the program headers, reproduce the two walks to recover `A1`/`A2`, and chain
through L3–L5 the same way as the sibling stages.

Layer 3's key is derived from the *output* of `sha512crypt`, never the
plaintext password:

```
hashcat -a 6 -m 1800 dovetail.shadow vocab.txt '41?d?d?d?1' \
        -1 '!@#$%&' -j 'c sa4 se3 si1 so0 ss5' -w 4 --hwmon-temp-abort 95
```

- **Class:** contractor · **base token:** `shufflebridge` (audited absent
  from rockyou) · **seam:** 41 · **shot:** 009 → password
  `Shuffl3br1dg341009#`
- The vocabulary salt is `"dovetail"`, so this stage's harvested wordlist
  (5,174 tokens, 914 already in rockyou) is disjoint from 21-cinder's — a
  wordlist built there is worth nothing here, and the harvest is paid again.
- Seam known: 31,044,000 candidates (~10.4 min full sweep). Seam unknown:
  3.1 billion candidates (~17.4 hours).

The reference solve recovers the flag from the shipped artifact in 0.13s of
elimination, 2.70s end to end.

## Anti-analysis tricks

- **A lying section header used against the tools that trust it.**
  `Elf64_Shdr.sh_offset` was rewritten so `readelf -S`/decompilers see a
  perfectly formed, plausible decoy region that the kernel never maps.
- **A container-format bait.** The PNG's own chunk structure carries fake,
  parseable chunks with valid-looking metadata and deliberately invalid
  CRCs — folded in as data, not an error, so naive parsing "succeeds" into
  a wrong answer.
- **Opaque predicate on SHA-256** between the walk and the matrix build,
  which stalls symbolic execution the same way as on 21-cinder.
- **Debugger-aware tamper trace (L5).** As on 21-cinder, this cuts both
  ways: a player confirming their own correct flag under gdb will be told
  it's wrong.
- **Anti-patch.** A single flipped bit inside the tamper window makes the
  binary reject the real flag.

## Notes

- **Cold-cache timing:** accept measured at ~1.30s on first run (50,000
  dependent random reads over the 240 MB plate); warm runs complete in tens
  of milliseconds. The same effect was recorded on 21-cinder for the same
  reason.
- **The plate doubles as a real PNG.** It's valid up to `IEND` and opens in
  any image viewer. Everything after `IEND` is salvage — including the
  planted "lamp account" card that discloses the credential seam number.
- **Verification rigor:** 43 differential checks (C vs. Python against a
  probe binary built from the shipped C source) and 36 end-to-end checks
  against the shipped artifact, including an explicit assertion that
  exactly one parameter block is covered by a `PT_LOAD` and the other by
  none.
- **Flag absence, measured:** not present as plaintext or reversed, no
  16-byte fragment, not under any of 255 XOR or 255 ADD keys, and absent
  from a memory dump taken at the verdict `write()` on a run carrying a
  wrong candidate — checked over both the binary and the plate.
