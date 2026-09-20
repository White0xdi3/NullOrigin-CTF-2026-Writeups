# 34-undertone

**Category:** Steganography · **Difficulty:** medium · **Chain share:** share 4 of 6 for stage 37

**Flag:**
```
Null0rigin{the_order_of_the_colours_is_the_message}
```

## What ships

- `undertone.wav` — 7,056,152 B. 40.000 s of telephone room tone, 16-bit PCM stereo at 44,100 Hz. The LEFT channel carries the stage; the RIGHT channel carries plain tone plus every decoy.
- `linetest.wav` — 2,822,444 B. 16.000 s, same format, same scheme on the left channel, but keyed on a **published** string over a **published** plaintext. No decoys, nothing planted.
- `line-notes.txt` — the engineer's note. Names the calibration plaintext in full, points at the left channel, and says the key comes "off the card, in the ordinary way, from the run before this one."
- `description.txt` — story only, no hints.

The tone itself is band-limited hiss at -42 dBFS RMS with 50 Hz mains hum and a few relay clicks, drawn independently per channel so that comparing left against right never unmasks the carrier.

## The mechanism

No technique name is written anywhere on this stage, and no tool reads it out. You get the scheme applied twice — once keyed with a secret, once keyed with a published string over published plaintext — and you're meant to reconstruct the mechanism by comparing the two.

The mechanism is **direct-sequence spread spectrum**, left channel only. Each payload bit is spread over 2,048 samples using a ±1 chip sequence derived from the keystream (amplitude 48 int16 LSBs), added directly onto the tone. Decoding means correlating each chunk of samples against its own PN segment and taking the sign of the result. The payload is a works entry, 70 bytes (560 bits), so it occupies 1,146,880 chips — about 26.0 seconds of the 40-second carrier — leaving nearly 14 seconds of clean tail.

The chips are white noise sitting about 15 dB under the room tone, so the left channel's spectrogram looks like featureless noise and its LSBs read as ordinary tone. There is genuinely nothing to see; there's only something to correlate against.

### The calibration file

`linetest.wav` exists purely to teach the mechanism: same scheme, keyed on `SHA-256(b"LINE TEST")` — the ordinary key schedule applied to a fixed string instead of a flag — over the plaintext `NULL0RIGIN LINE TEST 1 OF 1`, stated in full in the notes "as a works entry, stamp and check and all." You hold ciphertext, key, and plaintext; only the mechanism itself is missing. That's the actual exercise — derivation, not recognition. There's nothing to look up and nothing off-the-shelf to run.

One consequence of that design: the chip length is never written down anywhere a player can read. But known plaintext turns finding it into a one-dimensional sweep — try a handful of candidate chip lengths and see which one turns the correlated bits into a valid works entry:

```
chip length   256 : -
chip length   512 : -
chip length  1024 : -
chip length  2048 : PLATE, b'NULL0RIGIN LINE TEST 1 OF 1'
chip length  4096 : -
chip length  8192 : -
```

The CRC check makes this decidable: a wrong chip length produces bits, and bits are cheap, but not `PL8` with a check that actually passes. Once 2048 is confirmed on `linetest.wav`, the same chip length applies to `undertone.wav`.

## Decoys

All four decoys sit on `undertone.wav`'s RIGHT channel — exactly what the standard audio-stego reflex checks first. All four are fakes.

| # | Where | String |
|---|-------|--------|
| 1 | painted spectrogram, 1.5–6 kHz, seconds 22–30 | `Null0rigin{line_test_three_of_seven}` |
| 2 | Morse code in a 700 Hz envelope, from second 34 | `NULL0RIGIN DIAL NINE FOR THE SURFACE` |
| 3 | sample LSBs, first 336 samples | `Null0rigin{the_room_tone_was_added_later}` |
| 4 | RIFF `LIST`/`INFO` comment (`ICMT`) | `NullOrigin{a_carrier_laid_across_the_room}` |

Decoy 4 is the meanest of the four: a capital O for the zero, and content that's a reworded version of stage 33's flag — the exact string this stage is keyed on. Feeding the `ICMT` text into the key schedule yields a key that recovers nothing.

Decoy 3 is right-channel-only, deliberately. Its text is written into the de-interleaved right array, so a flat read of the WAV's `data` chunk (the kind a generic LSB-extraction tool does, interleaving both channels together) pulls alternating left/right samples and returns garbage. A channel-split read finds the fake cleanly — nothing here is unfair, the notes point straight at the right leg.

`linetest.wav` itself carries none of this. It has to be clean; a worked calibration example with a trap hidden in it would teach the wrong lesson.

## The break

1. Open the spectrogram first, because everyone does. Seconds 22–30, 1.5–6 kHz, right channel: painted text. **Candidate 1.** The left channel in the same view is flat noise.
2. Past second 34, the right channel keys a 700 Hz tone — decode the Morse by ear or with any decoder. **Candidate 2.**
3. Run the standard reflexes in any order. `exiftool` reads the RIFF `LIST`/`INFO` comment (**Candidate 3**); a flat LSB read of the `data` chunk returns garbage, but splitting the channels and reading the right leg's LSBs returns text (**Candidate 4**).
4. Stop and apply the container rule: none of the four begins with `PL8` or has a check over it, so none is a works entry. Note candidate 3's capital O, and that it's a reworded stage-33 flag.
5. That leaves the left channel, which looks empty: no strings, no tags, LSBs that read as tone, a spectrogram with nothing visible. The notes describe the message as "laid down the whole length, thin enough to sit under the noise," recoverable only by "adding many seconds together, with the right thing to add them against." That's spread spectrum, and nothing names it for you — deriving it is the actual challenge.
6. Work out the rest on `linetest.wav`, where key and plaintext are both published: derive the key with the ordinary schedule over `SHA-256(b"LINE TEST")`, take the keystream MSB-first as ±1 chips, and sweep chip lengths — correlate, take signs, pack MSB-first, test for `PL8` and a passing CRC. Only 2048 produces a works entry, and it recovers the published banner exactly — pinning chip length, bit order, sign convention, and offset all at once.
7. Re-key with `SHA-256` of the stage-33 flag and run the identical decode on `undertone.wav`'s left channel. `PL8`, 60 bytes, CRC comes out. Split on `0x1F` for the flag and 8 bytes nothing asked you to keep.

## Solve

`solve_34.py` re-derives every step from the shipped files rather than trusting build-side state. Part A sweeps the chip length on `linetest.wav`. Part B decodes `undertone.wav` with the stage-33 key at the length A found, and confirms the payload byte-for-byte. Part C prints every bit's correlation margin and fails if the weakest one is too close to the noise floor. Part D reads all four decoys back with independent detectors and confirms none of them touched the left channel.
