# 38-quietus

**Category:** Steganography · **Difficulty:** insane

**Flag:**
```
Null0rigin{the_channel_closes_from_the_inside}
```

The finale. No share is hidden here — stage 37 spent all six, and there's no next stage to key. `description.txt` sets the tone directly: "There is nothing hidden in this file. There is something hidden in the decision to write it this way."

## What ships

- `quietus.png` — 49,917 B. 8-bit grayscale, 320x240, a plate quantized onto a 13-level grey ladder. One IDAT chunk, nothing after IEND. Critically, the zlib stream inside that IDAT was **not** written by a normal compressor: it's a single DEFLATE block, fixed-Huffman coding, and every row uses filter type 0.
- `press-notes.txt` — the composing room's note; the only place the extraction rule is stated.
- `description.txt` — the line quoted above, plus the flag format.

## The mechanism

Nothing is hidden in the pixels at all. The message is **which DEFLATE token the encoder chose** at every point where two different, byte-identical encodings were both available.

The filtered scanline stream — 240 rows of one filter byte plus 320 samples each, 77,040 bytes total — is what DEFLATE actually compresses. Because every filter byte is 0, the filter-byte channel that stage 37 used is deliberately left empty here; those bytes are still ordinary *positions* in the stream, and 235 of the 240 row starts are genuine decision points.

The rule is a property of the decompressed byte stream alone, so both the encoder and any reader can compute it identically:

```
available(i)   iff   i+3 <= len(data)
                and  data[i:i+3] occurs at some earlier position p < i
                and  i - p <= 32768

available, bit 1  ->  emit a length-3 match to the MOST RECENT such p;  i += 3
available, bit 0  ->  emit the literal byte at i;                       i += 1
not available     ->  emit the literal byte at i (carries no bit);      i += 1
```

The bits are the works entry for this stage's flag, XORed with the keystream derived from the stage-37 flag, MSB first: 56 bytes total (448 bits), laid down starting from the very first decision point. Across the shipped file there are 38,560 tokens total (19,320 literals, 19,240 matches) and 38,423 decision points — meaning the payload occupies only about 1.2% of the available channel, all at the front. The rest is filled with a seeded pseudo-random sequence, so the payload's length never shows up as a shift in texture partway through.

Fixed-Huffman coding throughout is what keeps this fair — there's no dynamic Huffman table to reverse-engineer, and the token stream is parseable by hand directly against RFC 1951's specification.

### `press-notes.txt`, read literally

The note describes the whole mechanism as a compositor's choices, and every clause maps onto the rule exactly:

- *"A compositor has choices. That is the only thing about him that is worth anything."* — the pixels are honest and exhaustively so; the channel lives entirely in the encoder's freedom, never in its output.
- *"When the sort he wants next is one he has already set... he may take it from there — or he may go to the case and set it fresh. No reader alive can tell you which he did by looking at the page."* — match versus literal; both encodings decompress to identical bytes, so nothing on the pixel side reveals the choice.
- *"Three characters make a ligature. Never two, never four. And he always reached for the nearest one."* — every match is exactly length 3, and always to the single most recent earlier occurrence. This second constraint isn't decoration: a match to an *older* copy decompresses just as correctly, so without pinning "nearest," a match would carry more than one bit of ambiguity and there'd be no canonical reading.
- *"Where he had no such choice... that means nothing."* — positions where no earlier 3-byte match exists carry no bit at all.
- *"Do not reset the forme."* — re-saving the PNG through any normal encoder leaves the picture bit-identical and silently destroys the channel.

### A subtlety in how the rule has to be applied

The rule as stated — "test availability against everything decoded so far" — isn't literally executable in one pass: a literal at position `i` only emits one byte, but checking availability at position `i` needs the two bytes *after* it, which don't exist yet at decode time. The construction is self-consistent, just deferred: first parse every token and rebuild the full decompressed stream without consulting availability at all, then make a second pass over completed positions computing `available(i)` and reading off the bit each already-known token represents. This doesn't weaken the channel — the "most recent occurrence before `i`" search is still built strictly left to right — it only reorders the computation, not the inputs.

### The size tell — kept on purpose

At 49,917 bytes for a 320x240 plate with only thirteen distinct grey levels, this file is absurdly large: a standard compressor over the identical filtered stream produces about 3,123 bytes — roughly **16x** smaller. The inflation is inherent to the construction: about half of all decision points spend their bit on a literal where a match was available, and every match taken is capped at length 3 rather than the long runs a real encoder would find on a mostly-flat image.

This tell was kept deliberately. It's the fairest possible hint that the compressor itself is the channel — running `zlib.compress` over the same data and comparing sizes reproduces the anomaly in one line, and it points only at the *subsystem*, leaking nothing about the payload's content, length, or position. The alternative — biasing the filler bits toward matches to shrink the file — would actually be worse: the real payload's 448 decisions would then stand out as the *only* even-odds stretch in an otherwise biased stream, handing over its length and position for free.

## Decoys

| # | Where | String |
|---|-------|--------|
| 1 | bitplane 0, row-major | `Null0rigin{set_solid_and_no_leading}` |
| 2 | PNG tEXt `Comment` | `Null0rigin{the_compositor_went_home_at_six}` |
| 3 | watermark at half a quantization step, revealed by auto-contrast | `NullOrigin{the_channel_closes_from_the_inside}` |

Decoy 3 is the cruellest trap on the entire chain. The plate's actual pixel range only spans 16 to 60, so any auto-contrast or level stretch multiplies everything by roughly 4x — and a watermark sitting at exactly half a quantization step (invisible at native contrast, applied to about 2,227 pixels) comes up as hard, legible text. It's this stage's real flag, character for character, with a single capital O in place of the zero — every word, every underscore otherwise correct. A player who runs auto-levels, watches this string rise cleanly out of a blank grey plate, and submits it will have solved nothing and will believe they finished. Nothing external contradicts them — there's no verify binary, and there's no stage 39 to fail to open. Only the container check from stage 31 catches this one: it's a bare string with no works-entry wrapper around it at all.

## The break

1. Standard PNG tools (`pngcheck`, `file`, an image library) show an ordinary grey8 PNG with one IDAT chunk and nothing after IEND. A bitplane scanner immediately hits bitplane 0, row-major: **Candidate 1.**
2. Metadata tools surface the tEXt `Comment`: **Candidate 2** — and its closing words echo the press notes, which makes it read like corroboration rather than a trap.
3. Auto-level or contrast-stretch the image. The watermark comes up as hard text: **Candidate 3.** Read that string character by character — it's the correct flag with the zero swapped for a capital O, and it's the last, cruellest trap on the chain, because it looks completely finished.
4. Read `press-notes.txt` properly. Every candidate so far is a string sitting directly in the pixels or metadata; the note describes a choice exactly three characters wide, always reaching for the nearest earlier copy. Nothing in the raw pixel data has that shape — LZ77 does.
5. Parse the DEFLATE stream by hand: one block, fixed Huffman (the whole code table comes straight from the RFC), keeping track of each token's start offset. Build a table of the most recent prior occurrence of every 3-byte sequence, walk from position 0, and record a 1 for every match taken where one was available and a 0 for every literal where a match was available.
6. XOR the recovered bits against the keystream derived from the stage-37 flag, and unwrap the works entry: correct magic, correct length, correct CRC.

## Solve

[`solve.py`](38-quietus/solve/solve.py) is an independent, second bit-level DEFLATE implementation with its own bit reader, symbol decoder, and copy logic, built only from the public RFC 1951 fixed-Huffman tables — nothing here reuses the challenge's own encoder code. It verifies the PNG container end to end (chunk CRCs, header fields, the exact zlib framing, block type), decodes the channel rule itself (every match is length 3 to the most recent prior occurrence; every unavailable position emits an uncounted literal), then prints the final recovered flag — the last one on the chain.

```
python3 solve.py <path-to-38-quietus> <flag_37>
```

## Closing note

The difficulty on this board was never meant to sit in raw analysis — that's the part any competent player, tool, or model handles easily. It was built to sit somewhere else: in channels no general-purpose tool models (dither-cell arrangement at equal ink weight, palette permutation, authenticated wheat hidden among indistinguishable chaff, PNG filter bytes, and finally the choice between two byte-identical encodings), each one keyed on the flag before it so that nothing in a later file carries any signal at all without the earlier flags in hand, and in decoys engineered to be fully solvable and to actually pay out — 27 flag-shaped strings across the chain, most of them reachable in well under a minute, every one of them wrong. The cost was never meant to be comprehension. It was meant to be the hours spent correctly solving something placed there specifically to be solved correctly.
