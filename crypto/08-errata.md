# 08-errata

**Category:** Cryptography · **Difficulty:** Medium

**Flag:**
```
Null0rigin{you_took_the_plaintext_out_of_the_checksum}
```

Unlocked by **07-daybook**; solving it unlocks **09-catalogue**.

## What ships

`bus.cap` — 1,429,878,127 bytes of raw logic-analyser capture. No header, no protocol document, no firmware, no reference implementation.

`bench-notes.txt` — 214 bytes, carrying four decoy flags.

`errata.sealed` — 320 bytes, AES-256-GCM.

## Recovering the bus

The capture has to be decoded before anything else is possible. There are four `(CPOL, CPHA)` combinations to try, scored by odd-parity success over 9-bit LSB-first words; the score is genuinely bimodal, measured at `{40/40, 40/40, 0/40, 0/40}` over a 40-frame probe.

The catch is a real degeneracy: **two of the four combinations score 40/40 and decode to byte-for-byte identical output.** The decoder can only ever distinguish "sample on the rising edge" from "sample on the falling edge" — two outcomes, not four, since idling-high and idling-low collapse into the same effective sampling once framed the same way. The bus was built idling high with sampling on the rising edge; a reference decoder may report the other CPOL/CPHA label that produces an identical bitstream. The label is cosmetic — what matters is that the bits it produces are correct.

## The flaw

Group the decoded frames by `(type, length)`. **1,467** heartbeat frames share a byte-identical 64-byte trailer while their ciphertexts differ wildly. A trailer that doesn't vary with the ciphertext can't depend on the key — it has to be a GF(2)-linear map of the *plaintext* instead.

## Finding the generator

Drop the heartbeats. What's left is one burst at the head of each of the 21 power-ups: a walking-ones memory self-test whose trailers, taken in capture order, are the columns of the linear map `G`. The self-test frames carry the same type byte and the same length as the heartbeats, so this structural pattern — not any field in the frame itself — is the only way to locate them.

Of the 21 bursts, lengths vary across `[509, 510, 511, 512]`, and only **10 of the 21** decode to a full, untruncated 512-frame burst; the rest lose one to three frames to decode noise. Cross-checking the ten full-length bursts against each other is still an overwhelming confirmation, and all 512 linearly independent columns (trailers) of `G` come out of it.

## The key transfer

The key-transfer frame belongs to a different frame class entirely. Once `G` is known, its plaintext falls out directly as `G⁻¹ · trailer`.

## Solve

`solve.py` runs in about 33 seconds end to end against the built artifact, streaming the 1.4 GB capture rather than loading it whole.

**Feeds the finale:** the internal secret this stage contributes to 13-lantern is `SHA-256` over the 512 columns of `G`, taken in walking-ones order — 32 bytes.
