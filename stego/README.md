# Steganography — NullOrigin CTF 2026

Eight stages, hard-chained: **driftwood → safelight → moire → undertone → pentimento → winnow → mordant → quietus**.

There is no `verify` binary anywhere on this board, and that's deliberate. The flag you pull out of one stage *is* the decryption key for the next one. A wrong flag isn't rejected by a checker — it's simply the wrong key, and it opens nothing at all. The chain is its own checker. Stage 31 ships in the clear; every stage after it is opened with the flag before it.

Two conventions carry the entire chain. Both are taught in-band, early, and then never explained again — so it's worth having them straight before you start.

## The works entry

Every payload on this chain, in every channel, is packed into the same little container:

```
b'PL8' | version: u8 | length: u16 LE | crc32: u32 LE | payload
```

31's `plate-card.txt` teaches this shape, and it matters more than it looks: this board has dozens of flag-shaped strings sitting in plain metadata, obvious bitplanes, and amplified residuals, and *none of them* are wrapped in this container. The magic bytes plus the CRC check are the only oracle you get — they tell you whether you've found the right **channel**. Nothing on this chain ever tells you whether a **flag** is right, except whether it opens the next stage. Internalize this on stage 31, because by stage 33 the decoys stop being obviously wrong and start being CRC-plausible.

The `payload` for stages 31–36 is always `flag || 0x1F || share` — an 8-byte "share" tacked on after the flag that nothing in those stages asks you to keep. Hang onto it anyway (see "The mordant shares" below). Stage 37's payload has no share of its own; stage 38's payload is the flag alone.

## The key schedule

Stage 31 is the only unkeyed stage — there's no previous flag to key it with. Every stage from 32 onward encrypts its works entry with a stream cipher keyed on the *previous* stage's flag. 32's `keycard.txt` publishes the schedule in full, once:

```
k        = SHA-256(previous_flag)          # braces included, exact bytes
stream   = SHA-256(k || counter_be32) for counter = 0, 1, 2, ...
           concatenated and truncated to the needed length
payload  = ciphertext XOR stream           # octet for octet, from the front
```

Stages 33 through 38 all use this construction silently. A couple of the later stages' clue documents even reference it obliquely without restating it ("k is what the card says it is") — so if you skipped 32 because it looked cheap, go back and read the card properly.

## The mordant shares

Stages 31 through 36 each hide 8 bytes after the `0x1F` separator inside their works entry — bytes that nothing in those six stages ever explains. These are the **six mordant shares**. Stage 37 needs `SHA-256` of all six, concatenated in stage order, as its *second* key. Its first key is the ordinary chain key derived from stage 36's flag. Neither key alone opens stage 37 — you need both. If you extracted a stage's flag without keeping the trailing bytes, you'll have to go back and re-open it.

## Standard tools stop helping after stage 32

`zsteg`, `steghide`, `binwalk`, and `stegoveritas` will all return *something* on every stage in this chain — and past stage 32, that something is always a decoy. None of these channels (halftone cell arrangement, sub-noise-floor spread spectrum, GIF palette ordering, chaffing-and-winnowing, PNG filter bytes, DEFLATE token choice) is something a general-purpose stego scanner models. From stage 33 on, you're writing your own parser.

## Decoys are not noise

There are **27 strings on this chain that are in flag format and are not flags**. About ten of them sit in the clear, exactly where your first reflex looks. They fall into three families, and it's worth learning to recognize them on sight:

- **Plausible-but-wrong content** — a string that fits the stage's theme perfectly and reads as a natural "find."
- **Homoglyph prefixes** — `NullOrigin` (capital O), `Nu110rigin` (digit ones for the double-L), `Null0rlgin` (lowercase L for the i). Check the prefix character by character, every time.
- **Right-shape, wrong-run strings** — content that reads like a flag from a neighboring stage, often the one you just solved, which is exactly why it's convincing.

No fake ever sits inside a valid works entry (correct `PL8` magic, correct CRC) — with exactly one deliberate exception, on stage 37. That one is discussed on that stage's page, and it's the nastiest trap on the board.

## Re-encoding: what survives and what doesn't

Stages 35, 37, and 38 are destroyed by *any* re-encode — opening the file in an editor and resaving it, even losslessly, wipes the channel. Stage 33 is the interesting exception: its plate is bilevel (1-bit), so a lossless re-save or even a JPEG round-trip at q40 thresholds back pixel-identical and leaves every carrier cell legal. What kills stage 33 is anything that **moves the pixel grid** — a 1-pixel shift leaves only 10.3% of carriers legal, a 2x down-and-up scale 2.2%, a 4x box downscale 1.8% — or a genuine re-screening of the halftone. If you're inspecting these files with tools that touch and resave the image, know which category you're in before you start.

## The chain

| # | Stage | Tier | Channel | Write-up |
|---|-------|------|---------|----------|
| 31 | driftwood | easy | alpha-plane LSB, column-major | [31-driftwood.md](31-driftwood.md) |
| 32 | safelight | easy | print/negative residual, magnitude-1 class | [32-safelight.md](32-safelight.md) |
| 33 | moire | medium | halftone cell arrangement, serpentine read | [33-moire.md](33-moire.md) |
| 34 | undertone | medium | DSSS spread-spectrum, under the noise floor | [34-undertone.md](34-undertone.md) |
| 35 | pentimento | hard | GIF local colour table pair order | [35-pentimento.md](35-pentimento.md) |
| 36 | winnow | hard | chaffing and winnowing | [36-winnow.md](36-winnow.md) |
| 37 | mordant | insane | PNG scanline filter bytes + the six shares | [37-mordant.md](37-mordant.md) |
| 38 | quietus | insane | DEFLATE literal-vs-match choice | [38-quietus.md](38-quietus.md) |

Total shipped size across all eight stages: roughly 15 MB.
