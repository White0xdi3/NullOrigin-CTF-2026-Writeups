# 35-pentimento

**Category:** Steganography · **Difficulty:** hard · **Chain share:** share 5 of 6 for stage 37

**Flag:**
```
Null0rigin{keep_the_grain_and_burn_the_chaff}
```

## What ships

- `pentimento.gif` — 1,195,851 B. GIF89a, 480x360, 11 frames, looping forever. Every frame is full-canvas, non-interlaced, and — critically — carries its **own 256-entry local colour table**. The global colour table is just a grey ramp for old viewers and is overridden by every frame.
- `dish-notes.txt` — the colourman's note: states the mechanism in trade language, and warns about the one thing that destroys it.
- `description.txt` — story only.

## The mechanism

The frames are honest. Every rendered pixel is exactly the image the stage intends — nothing hides in a bitplane, a residual, or any statistic computed over pixel values, because there's nothing in the pixels to find. The message is the **order of the colour table**.

Take a copy of a frame's 256-entry local table, sort it ascending by `(R<<16)|(G<<8)|B` — call this the *canonical* palette — and split it into 128 consecutive pairs: `(0,1), (2,3), ..., (254,255)`. A pair left in canonical order encodes bit 0; a swapped pair encodes bit 1. Eleven frames × 128 pairs = 1408 bits of capacity.

The invisibility trick is the remap: whenever a pair is swapped, every pixel index using either colour in that frame is XORed with 1 as well, so the actual colour that ends up at each pixel is unchanged — only which palette slot points to it moves. The picture and the message table move together, and the render is provably identical either way.

The payload is a works entry — 45-byte flag, `0x1F`, 8-byte share, plus a 10-byte header, 64 bytes = 512 bits — XORed with the keystream derived from the stage-34 flag, then padded out to the full 1408 bits with pseudo-random filler so the real payload length isn't visible as a texture change partway through the table.

### The picture provably doesn't move when the message changes

This was tested, not just argued: re-permuting every table under a completely different, freshly-random 1408-bit body and re-emitting the file gives **pixel-identical** rendered frames under every seed tried, and — because a pair swap only relabels the index alphabet without touching the underlying LZW parse structure — the re-emitted file is **exactly the same size**, down to the byte, even though roughly 8.7% of the file's bytes differ. There is no pixel side channel and no length side channel here.

## Decoys

| # | Where | String |
|---|-------|--------|
| 1 | header comment extension | `Null0rigin{eleven_frames_and_none_of_them_true}` |
| 2 | comment extension planted before frame 6, pointed at by the frame delays | `Null0rigin{the_delay_between_frames_is_the_message}` |
| 3 | frame-difference stack, parity split or second-difference route | `Nu110rigin{the_order_of_the_colours_is_the_message}` |

The eleven frame delays, read as ASCII bytes, spell out `SEE FRAME 6` — pointing at a second comment extension planted right before that frame. It's a decoy pointing at another decoy, and it's the nicest trick in the stage: it does real work convincing you the delays were the hidden message, which is exactly what you just proved to yourself by decoding it.

Decoy 3 is the worst of the three. A plain frame-to-frame absolute-difference stack shows essentially nothing, because the plate is visibly *developing* across the sequence — the development rate swamps the small signal. But a **parity split** (mean of even frames minus mean of odd frames, which cancels the development trend because both halves share the same average position in the sequence) or a **second-difference stack** (which zeroes out any purely linear trend) both raise a ghost reading `Nu110rigin{the_order_of_the_colours_is_the_message}` — stage 34's flag verbatim, under the `Nu110rigin` homoglyph (two digit ones for the double-L). Anyone holding flag 34 reads this as confirmation of what they already have and burns time deciding whether they mis-transcribed it. It's bait, and cruelly, the string it uses to bait you is also *true*: the order of the colours really is the message — just not this one.

## The break

1. `strings`/`exiftool` surface the header comment extension immediately: **Candidate 1**, and with eleven frames in the file, the content fits.
2. Dump the frame delay values and read them as ASCII bytes: they spell `SEE FRAME 6`.
3. A second comment extension sits immediately before frame 6: **Candidate 2** — a decoy pointing at another decoy.
4. `dish-notes.txt` says to "stack them, difference them, pull them apart to the last dot." A plain absolute-difference stack shows nothing meaningful; a parity split or second-difference stack raises **Candidate 3**, the worst of the bunch (see above).
5. None of the three candidates begins with `PL8`, and none has a check over it. Read the notes properly: what's *not* the same from frame to frame is the palette (the "tray") — all 256 colours present every time, sorted darkest to lightest by `(R<<16)|(G<<8)|B`, two colours to a slot, "careless which goes left" (128 pairs, one bit each), and the picture rides along with a remap so the colour moves but nothing on screen does.
6. A naive approach with an image library only gets you the first frame's table in written order — 128 of the 1408 bits, `PL8` and a length field but nowhere near enough for the CRC to pass. You need to write your own GIF parser: image descriptor, local colour table flag, the 256 RGB triples, LZW decode. Sort a copy of each table and walk the 128 pairs to read 0 for in-order, 1 for swapped.
7. Pack MSB-first, XOR against the stage-34 keystream, and the header comes out with a correct magic, length, and CRC. Split on `0x1F`: the flag, and eight bytes nothing asked for. Keep them.
8. Don't re-encode the file to inspect it further. Any competent tool rewrites the palette back into canonical order — which is exactly what "correct" GIF handling looks like — and because the picture rides the remap, the frames look completely unchanged afterward with nothing left in them to recover. It's the one hazard you reach *by being careful*, and it's unspottable after the fact. The notes warn about this explicitly.

## Solve

`solve_35.py` opens `pentimento.gif` and nothing else, parsing it byte by byte with its own GIF reader and LZW decoder — an image library only appears at the end, as an independent renderer to cross-check against. It asserts the file's shape (11 frames, 480x360, full-canvas, non-interlaced, a 256-entry local table on every frame), the 1408 pair-bits, the works-entry header and CRC under the correct key, and the payload against ground truth — and separately confirms that the *wrong* key (the stage-33 flag) does not unwrap it, so the keying claim is checked mechanically rather than asserted in prose.
