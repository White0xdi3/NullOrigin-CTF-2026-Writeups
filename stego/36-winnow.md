# 36-winnow

**Category:** Steganography · **Difficulty:** hard · **Chain share:** share 6 of 6 for stage 37 (the last one it needs)

**Flag:**
```
Null0rigin{nothing_takes_until_it_is_fixed}
```

## What ships

- `sheet.png` — 1,352,579 B. A 2048x1024 8-bit grayscale contact sheet: 64x32 = 2048 thumbnails, each exactly 32x32 with no gutter between them. Cell `i = r*64 + c` sits at rows `r*32..r*32+31`, columns `c*32..c*32+31`. Frames are procedural pithead plates and ledger scans.
- `contact-sheet.txt` — the sleeve document: states the cell pairing, the record construction in full, and what reading the sheet unsorted costs you.
- `description.txt` — story only, no hints.

## The mechanism

This is Rivest's chaffing and winnowing, implemented literally rather than as an analogy.

Every cell carries a record in the LSBs of its first 17 pixels, read row-major within the cell: pixel 0's LSB is the record's bit `b`, and pixels 1 through 16's LSBs form a 16-bit tag, MSB first. A record is **wheat** if and only if:

```
tag == SHA-256( k || cell_index.to_bytes(2, "big") || bytes([b]) )[:2]
```

where `k = SHA-256(stage-35 flag)`, the ordinary chain key schedule. Cells go in pairs — pair `j` is cells `2j` and `2j+1`. For the payload-carrying pairs, exactly one of the two cells authenticates and carries the real message bit; the other carries the *opposite* bit under a 16-bit tag drawn uniformly at random (redrawn if it happens to authenticate by chance).

There is no encryption inside this particular channel — the authentication itself *is* the channel. Recovering wheat from every pair, then XORing the winnowed bits against the keystream, gives a 62-byte works entry: 496 bits, so pairs 0 through 495 carry the payload and pairs 496 through 1023 carry no wheat at all — pure chaff, no valid record on either side.

## Why there's no shortcut

Take any single pair. Both cells hold a bit and a 16-bit tag; the bits disagree by construction; one tag is a genuine keyed hash and the other is 16 bits of uniform noise. Without the key, the first tag isn't computable and the second isn't distinguishable from it — same 17 pixels, same bit plane, same distribution. The chaff isn't weak, disguised, sparse, or badly made; it's the majority of the sheet (1,552 cells against 496 real ones). This stage isn't hard to read — it's impossible to read without the key, and `contact-sheet.txt` says so directly:

> The whole of the trick is that the chaff is not disguised. It is not hidden, it is not weak, it is not badly made. It is perfectly good chaff and there is more of it than there is grain, and without the die there is no reading on this earth that will separate them.

With the key it's one hash per cell and it's over: every payload-carrying pair authenticates exactly once on exactly one side, no pair authenticates twice, and nothing past the payload region authenticates at all. Feed it the *wrong* key and zero of the 2048 cells validate. The solver also isn't told where the payload ends in advance — it walks pairs until one authenticates nothing on either side, which is how the length falls out naturally.

## Decoys

Five decoys, so every fast reflex pays out — none of them sit inside a works entry.

| # | Where | String |
|---|-------|--------|
| 1 | naive full LSB read, byte 165 | `Null0rigin{read_every_cell_and_you_read_nothing}` |
| 2 | naive full LSB read, byte 214 | `Null0rigin{grain_eight_hundred_and_ninety}` |
| 3 | cell 890, a real scannable QR code | `Null0rigin{one_thousand_and_twenty_four_grains}` |
| 4 | PNG tEXt `Comment` | `Null0rigin{the_sheet_was_never_contact_printed}` |
| 5 | bitplane 1 (not the LSB plane) | `NullOrigin{keep_the_grain_and_burn_the_chaff}` |

Reading every cell's LSB straight through, tags ignored entirely, is meant to pay out: it produces a clean tail of printable ASCII holding two flags back to back. That's deliberate — the naive read is a trap that rewards the reader with something that *looks* complete, and decoy 2 conveniently names cell 890, chaining you straight into the next trap.

Cell 890 really is a scannable QR code. Since no QR-generation library was available in the build environment, it was constructed from first principles — Reed-Solomon error correction over GF(256), format-information encoding, finder/timing/alignment patterns, and full mask scoring — and it decodes cleanly with any standard reader. It's still a decoy: no works entry, no CRC.

Decoy 5 is the cruellest: it's stage 35's flag — the key you're already holding — with a capital O in place of the zero, sitting in bitplane 1 rather than the LSB plane, verified not to disturb a single LSB bit.

## The break

1. `exiftool sheet.png` surfaces the tEXt `Comment`. **Candidate 1** — nothing on this sheet lives in a works entry.
2. Bitplane 1 spells out a flag across the whole sheet. **Candidate 2** — stage 35's flag, misspelled.
3. Read the LSBs straight through, all 2048 cells, tags ignored: most of it is noise, but a run near the end is clean printable ASCII holding two flags. **Candidates 3 and 4** — reading the sheet unsorted is the trap, and it's meant to pay out.
4. The second of those names cell 890 explicitly. It's a real QR code. Scan it. **Candidate 5.**
5. None of the five candidates sit behind `PL8` with a passing check. Read `contact-sheet.txt`: the cells go in pairs, the pairs must be "sorted" (winnowed), and the authenticating hash runs over the key, the cell index as two big-endian bytes, then the single bit byte, keeping only the first two output bytes.
6. Compute that hash for both cells of every pair, using `k` derived from the stage-35 flag. Exactly one cell per pair authenticates; keep its bit.
7. Stop when a pair authenticates on neither side — that's the end of the payload (pair 496). Nothing needs to tell you the length in advance.
8. XOR the winnowed bits against the same key's stream: `PL8`, correct length, correct CRC. Split on `0x1F` — the flag, and 8 bytes nothing asked you to keep. This is share 6 of 6, the last one stage 37 needs.

## Solve

`solve_36.py` works from the shipped `sheet.png` and the previous flag alone. It reads all 2048 records, winnows under the key, discovers the payload length itself rather than being told it, and confirms the payload matches ground truth byte-for-byte. It also proves the negative case rather than just asserting it: re-running the winnowing under the *wrong* key (stage 34's flag) confirms exactly zero cells validate, and it pulls all five decoys for cross-checking.
