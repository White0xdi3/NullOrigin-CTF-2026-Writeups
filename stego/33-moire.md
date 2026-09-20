# 33-moire

**Category:** Steganography · **Difficulty:** medium · **Chain share:** share 3 of 6 for stage 37

**Flag:**
```
Null0rigin{a_carrier_laid_across_the_whole_room}
```

## What ships

- `moire.png` — 40,980 B. A 1-bit PNG, 1024x768, of the pithead plate screened to a 4x4 ordered halftone. Carries all three decoys — none of them inside a works entry.
- `screen-notes.txt` — the process room's notes on the job. States the entire mechanism in the trade's own language, and never uses the word "bit."
- `description.txt` — story only, no hints.

Labelled medium, built brutal: a 1-bit PNG has exactly one bitplane, and it *is* the picture, so there's no LSB to speak of. `zsteg` — which models bitplanes and channel orders — has nothing here to walk. This is the first stage where the standard kit does not apply at all.

## The mechanism

The plate is screened into 4x4 cells — 256 across by 192 down, 49,152 of them. A cell's ink weight `k` is its popcount (0 to 16), and that weight is always honoured: the picture is exactly the picture the photograph asked for. What's free is *which* pixels within a cell of weight `k` are inked.

For weights 5 through 11, the pattern book contains **three distinct arrangements** of the same weight: a canonical pattern `C_k` used for non-carrier cells, and two more, `A_k`/`B_k`, encoding bit 0 and bit 1 for carrier cells. The hard limit only bites at the ends — weight 0 and weight 16 admit exactly one arrangement each — and the 5–11 carrying band is a design choice above that floor, chosen to keep the midtones free of visible directional texture.

The pattern book is **not a secret, and it can't be** — every cell at a carrying weight in the shipped plate is a carrier, so the canonical pattern `C_k` never appears at a carrying weight. A histogram of the 4x4 patterns actually used, grouped by weight, shows exactly two distinct arrangements at each carrying weight and exactly one everywhere else:

```
k= 4  5,725 cells  1 arrangement     k= 9    790  2  5A5B 5A5E
k= 5  8,900 cells  2  141A 14A4      k=10  1,673  2  5B5E 5E5B
k= 6  7,787 cells  2  1A4A 2585      k=11  8,168  2  5BEB 5EBE
k= 7  5,692 cells  2  1A5A 25A5      k>=12 7,858  1 arrangement each
k= 8  2,559 cells  2  3C3C 5A5A
```

The image hands you the alphabet for free. What's left is seven unknown polarity bits — one per carrying weight, deciding which of each pair means 1 — and those brute-force in 128 tries against the container check in well under a second. Without the previous stage's flag, all 128 assignments fail; the pattern book is the alphabet, but the flag is the lock.

One subtlety: the obvious convention (lower mask integer = bit 0) is correct at six of the seven weights, and wrong at `k=8`. At that weight the canonical pattern `C_8 = 0xA5A5` is itself the lowest-energy non-canonical-looking pattern, tied with `0x5A5A`, so the ranking has to explicitly filter out the canonical pattern to find the real carrier pair, `0x3C3C` and `0x5A5A` — the one weight where the pairing doesn't follow the naive rule.

Carrier cells are read in **serpentine order** — down one furrow and back along the next, the way an ox ploughs a field. Bits pack MSB-first and are XORed with the keystream derived from the stage-32 flag. The payload is 67 bytes of works entry (536 bits); the remaining 35,033 carrier bits are seed-based coin flips, so the payload length is never visible as a change in texture on the face of the plate. Measured: 35,569 of 49,152 cells (72.4%) are carriers, with a near-even bit balance (17,929 ones of 35,569, 0.5041) so nothing about the fill looks structured either.

## Decoys

The moire ghost decoy biases 484 cells' weight by +1, inside a 42pt glyph mask centred over the middle of the plate. At 100% zoom it's an invisible, uniform screen; on a 4x box downscale — one output pixel per cell, so its value literally becomes `k/16` — or under a light blur and contrast stretch, it reads as text.

This decoy is entangled with the real channel, not layered on top of it: biasing a cell's weight can change whether it's a carrier at all. Of the 484 ghost cells, 460 are carriers; 459 of those stay carriers with `k` shifted by +1 (and so read out of a different A/B pair), one crosses *into* the carrying band (`k=4 → 5`), and one crosses *out* (`k=11 → 12`). The total carrier count is unaffected, but the *set* of carrier cells is — and there's no way to subtract the decoy's effect out cleanly. It's still a fake: no works entry, no CRC.

| # | Where | String |
|---|-------|--------|
| 1 | appended trailer after IEND (fake PostScript) | `Null0rlgin{two_cells_of_equal_weight}` |
| 2 | PNG tEXt `Comment` | `Null0rigin{the_screen_was_turned_fifteen_degrees}` |
| 3 | moire ghost, visible on 4x downscale/blur | `Null0rigin{eighty_five_lines_to_the_inch}` |

Decoy 1 is the nastiest of the three: an `l` in place of the `i`, and content that's stage 32's flag with its tail cut off — the string you were holding five minutes before you got here.

**A practical note on durability:** this plate is pure black and white, so a lossless PNG re-save or even a JPEG round-trip at quality 40 leaves 100% of carriers legal. What actually destroys the channel is anything that **moves the pixel grid** — a 1-pixel shift leaves only 10.3% of carriers legal, a 2x downscale-and-back-up leaves 2.2%, a 4x box downscale leaves 1.8%. If you're piping this through a tool that resamples the image, expect it to break even though the tool never touches "content."

## The break

1. `file`/PIL confirm a 1-bit PNG, 1024x768. `zsteg` just returns the image — nothing to walk.
2. `strings` finds the trailer (**Candidate 1**), then `exiftool` the tEXt `Comment` (**Candidate 2**).
3. The stage is called *moire*, and two decoys now agree on a ruling/angle. FFTs, screen-angle hunting, downscaling — a 4x downscale or a light blur raises the ghost (**Candidate 3**), the most convincing of the three because it took real work to find. One lie, three channels, no works entry among them.
4. Read `screen-notes.txt`: four to the cell, the weight is sacred, only the middle weights have room to move, the machine lays them "as the ox ploughs" — and the message is not *in* the sheet, it's in what the sheet was broken into.
5. Cut into 4x4 cells, popcount each, histogram the distinct 16-bit arrangements by weight. Two arrangements at every weight from 5 to 11, one everywhere else — the whole break, and it needs no author-side information.
6. Walk the carriers in serpentine order, pack MSB-first, XOR with the stage-32 keystream, and look for `PL8`. Polarity is seven unknown bits, one per weight — brute-force all 128 and let the CRC-32 decide.
7. Read the payload's length field, stop there, ignore the remaining fill bits. Split the payload on `0x1F`. Keep the 8 bytes nobody asked for.

## Solve

[`solve.py`](33-moire/solve/solve.py) opens only the shipped `moire.png` and takes the stage-32 flag as its key — no private build state, no RNG, no length hint from outside the payload itself. It rederives the pattern book from first principles (a pure function of the halftone's own clumping-energy ranking), requires every carrier cell to be one of its weight's two legal arrangements before emitting a bit (so a broken screen stops the solve rather than producing garbage), then prints the recovered flag and share.

```
python3 solve.py <path-to-33-moire> <flag_32>
```
