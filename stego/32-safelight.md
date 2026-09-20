# 32-safelight

**Category:** Steganography · **Difficulty:** easy · **Chain share:** share 2 of 6 for stage 37

**Flag:**
```
Null0rigin{two_cells_of_equal_weight_are_not_equal}
```

## What ships

- `print.png` — 319,407 B. 8-bit grayscale, 900x620, the pithead plate clamped into the range [3, 250]. Carries two tEXt chunks and one decoy in its bitplane 0.
- `negative.png` — 321,592 B. 8-bit grayscale, 900x620, no metadata at all. It's *almost* exactly `255 - print`.
- `keycard.txt` — the operator's card. It publishes the chain's key schedule, and that's this stage's real cargo.
- `description.txt` — story only, no hints.

## The mechanism

Neither image hides anything on its own. The channel exists only in the **disagreement** between them — a player working one file at a time can work forever.

```
r = print + negative - 255
```

An honest negative gives `r == 0` everywhere. Over the shipped pair, `r` takes four values, and their magnitudes are the entire puzzle:

| r | count | what it is |
|----|---------|--------------------------|
| 0 | 553,860 | honest negative |
| +3 | 3,580 | decoy — a centred glyph mask |
| +1 | 270 | data, bit 1 |
| -1 | 290 | data, bit 0 |

The 560 carrier pixels are drawn from every pixel the decoy glyph doesn't occupy, so the two classes never collide, and they're read **row-major**. 560 bits is 70 bytes — the works entry taught by stage 31, XORed with the keystream derived from the stage-31 flag. That XOR is what makes this a chain link rather than a standalone puzzle: the pair yields nothing to staring, only to typing stage 31's flag exactly.

The decoy class is always `+3`, never `-3` — sign does not separate the two classes; magnitude does. That's the whole discrimination puzzle.

This stage's real job is publishing the key schedule, the same way stage 31's was to teach the container. `keycard.txt` states it once, in full: `k = SHA-256(previous flag, braces and all)`, a stream of `SHA-256(k || counter)` with the counter from zero as four big-endian octets, cut to length and XORed on from the front. It also states the failure mode that saves you days:

> A seal that is one character out is not nearly right.

Stages 33 through 38 each key on the flag from the stage before, and not one of them explains it again — a couple reference the card obliquely without restating it. (One honesty note: the card also describes a numeric variant of the schedule that no stage on the chain actually uses.)

## Decoys

| # | Where | String |
|---|-------|--------|
| 1 | `print.png` tEXt `Comment` | `Null0rigin{developed_under_a_red_lamp}` |
| 2 | `print.png` bitplane 0, clean centred glyph | `Null0rigin{fixed_for_eleven_minutes}` |
| 3 | naive residual, sign-amplified | `Nu110rigin{what_the_print_kept_from_the_negative}` |

Decoy 3 is the most seductive route on the stage, and it's worth walking through why. Taking every non-zero residual, mapping sign to bit, and reading row-major gives 4,140 bits — not a multiple of 8, but XOR it against the stage-31 keystream anyway and the head comes out looking *right*: correct magic, correct version, a correct length field of 60, and a correct-looking CRC field. The payload even reads `Null0rigin{two_cells_of_` before turning to noise. **Only the CRC check fails.** The decoy glyph is vertically centred, so its first pixel lands at row 300 of 620, and 278 clean data bits arrive ahead of it before the decoy's 1-bits start polluting the stream. Anyone who trusts the magic bytes instead of actually running the CRC will be certain they're one small mistake away from a working flag. They aren't — the fix is to split by **magnitude**, not sign: `|r| == 1` is data, `r == 3` is glyph.

Decoy 3's text is also wrong twice over: the prefix is `Nu110rigin` (two digit ones for the double-L), and the content is the real stage-31 flag with `print` and `negative` swapped — so whoever solved 31 an hour ago reads it as confirmation, not bait.

A cleverer-looking route doesn't help either: XORing bitplane 0 of the two files marks exactly the 4,140 touched pixels and nothing else, because every non-zero residual is odd. It finds every carrier and cannot classify any of them.

## The break

1. `exiftool print.png` — the tEXt `Comment`. **Candidate 1.** Not in a works entry, not keyed by anything.
2. A bitplane viewer on `print.png`. Bitplane 0 shows clean, centred text on a clean field. **Candidate 2.** It reads as a genuine find because the LSB rewrite was whole-image, not a localized artifact.
3. Difference the two plates and amplify. **Candidate 3**, where most players stop — see above for why it's wrong.
4. Read `keycard.txt` and stage 31's `plate-card.txt` again. None of the three candidates begins with `PL8`, none has a check over it, none was keyed. Stop looking at the residual and start measuring it.
5. Split by magnitude: `|r| == 1` is the data (560 bits, exactly 70 bytes), `r == 3` is the glyph. Read row-major, XOR against the stage-31 keystream, and the CRC comes out clean.
6. Split the payload on `0x1F`: the flag, and eight bytes nothing asked for, `2a77be05c4198d3f`. Keep them.

## Solve

[`solve.py`](32-safelight/solve/solve.py) runs from the two shipped PNGs and the stage-31 flag, nothing else. It confirms the residual alphabet sits within `{-1, 0, 1, 3}`, that no decoy pixel is also a data pixel, that the recovered bit count divides evenly by 8, then prints the recovered flag and share. It also checks the traps mechanically: confirms the real flag is absent from bitplane 0, and prints the tEXt decoy as found.

```
python3 solve.py <path-to-32-safelight> <flag_31>
```
