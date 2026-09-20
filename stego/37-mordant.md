# 37-mordant

**Category:** Steganography · **Difficulty:** insane

**Flag:**
```
Null0rigin{he_set_two_sorts_where_one_would_do}
```

This stage is the payoff of the entire chain: two independent locks, and neither one opens anything alone. It carries no share of its own for a later stage — by the time you reach it, all six mordant shares from stages 31–36 should already be in hand.

## What ships

- `mordant.png` — 1,656,336 B. A 1400x1900 8-bit grayscale scan of a dye house ledger page, built by hand rather than through a normal PNG encoder — because the encoder's free choices *are* the channel, and no library is allowed to make them for you. 1,656,015 B of that is the PNG itself; the last 321 bytes are an appended ZIP, so the file opens correctly as both a PNG and a ZIP from the same path.
- `mordant-notes.txt` — the bath 5 working notes: the entire mechanism in a dyer's metaphor, including an explicit warning about the seventh share.
- `description.txt` — story only; "it was fixed six times" is the only mention of the number six outside the notes.

## The mechanism

### Outer lock: the scanline filter bytes

Every PNG scanline is stored as one filter-type byte followed by the filtered row data. Which of the five standard filter types the encoder picks for a given row is a completely free choice — all five reconstruct the same pixels — and nothing downstream ever reports which one was used. Decoders discard it after unfiltering, bitplane tools only ever see the already-decoded image, file carvers work off signatures, and metadata tools read chunk headers. It's invisible in every direction the usual toolchain looks, which is exactly why it's the channel here.

Each scanline contributes 2 bits, taken as `filter_byte & 3`:

```
f=0  None   -> 0        f=3  Avg    -> 3
f=1  Sub    -> 1        f=4  Paeth  -> 0
f=2  Up     -> 2
```

1900 scanlines × 2 bits = 3800 bits = 475 bytes of capacity. The payload itself is only 57 bytes (456 bits, 228 lines); the remaining 1672 lines carry a deterministic pseudo-random 2-bit value, so nothing in the filter-type histogram marks where the real payload stops. Note the one degeneracy in the channel: `f=4` (Paeth) always produces the same 2-bit value as `f=0` (None) — that's the only slack available, and it's spent entirely on making the overall histogram look like a normal adaptive encoder's output rather than a deliberately structured one.

What's written into this channel isn't the plaintext payload directly — it's been through *both* locks already:

```
inner = works_entry(flag37)                 # 57 bytes
lock2 = inner XOR stream(mordant_key)       # inner lock applied
lock1 = lock2 XOR stream(K(stage-36 flag))  # outer lock applied, written to the file
```

So reading the file back means peeling the outer lock (the ordinary chain key schedule, keyed on stage 36's flag) first — but what comes out the other side is still ciphertext.

### Inner lock: the six shares

The second key is:

```
SHA-256(share_31 || share_32 || share_33 || share_34 || share_35 || share_36)
= 6a740af806883729614d6e8114eb2059f4555b33d1f29320be1a67aefa9c1208
```

— the eight bytes sitting after the `0x1F` in every works entry since stage 31, that nothing in any of those six stages ever explicitly asked you to keep. If you discarded them, you have to go back and re-open all six. The notes state this plainly:

> There is ... eight octets that were not the seal and that nothing asked you to keep. ... You will have thrown them away. Most do. Go back and get them.

Both locks bite independently: peeling only the outer lock (with the stage-36 keystream) does not produce a valid works entry, and applying only the inner lock (the six shares, with no outer peel) doesn't either. Neither lock is decoration sitting over one "real" one — you need both, in the right order.

## Decoys

### The poisoned entry — the nastiest trap on the chain

Reading bitplane 0, row-major, MSB-first, unkeyed, starting from pixel 0 — the very first place any generic tool looks, in the first order it tries — produces a **complete, valid, CRC-correct works entry**:

```
Null0rlgin{nothing_takes_until_it_is_fixed}  ||  0x1F  ||  c8b41d7e93502af6
```

Correct `PL8` stamp, correct length, correct CRC-32. The container check — your only oracle for six straight stages on a chain with no verify binary — says yes. It's lying, on purpose, twice over:

- The flag text is stage 36's real flag with a single substitution: a lowercase `l` where an `i` belongs (`Null0rlgin`, not `Null0rigin`). It isn't even *this* stage's flag — it's the flag you already hold, misspelled, which reads as familiar rather than suspicious.
- The trailing bytes are a **seventh share**. Substitute it for the real stage-36 share and the derived inner-lock key becomes a different 32 bytes entirely — the inner lock stays shut, and unwrapping the payload just silently returns nothing, with no indication of how close you were.

This is the one deliberate exception on the whole chain: a fake sitting inside a container with a passing check. `mordant-notes.txt` warns about it directly:

> There is a seventh share on these premises. It is lying where anybody would find it, in the first place anybody would look, inside a perfectly good works entry with a perfectly good check over it. ... We did not use it. Neither should you.

The README (this one) warns about the flag's prefix character by character: it's a zero, and the rest is lowercase after the capital N. Both warnings are trivially easy to ignore, and that's the intended failure mode, not an accident of it.

Two more decoys, plain metadata this time and thrown out on sight once you're applying the container rule consistently:

| # | Where | String |
|---|-------|--------|
| 2 | PNG tEXt `Comment` | `Null0rigin{alum_and_cream_of_tartar}` |
| 3 | ZIP after IEND, `assay.txt` | `Null0rigin{the_dye_was_never_the_secret}` |

## Why standard tools miss it

A full sweep of 8 bitplanes × {row-major, column-major} × {MSB-first, LSB-first} — 32 combinations total — finds exactly one valid works entry in the entire file: the poisoned entry described above, at bitplane 0, row-major, MSB-first, offset 0. That's inside every generic stego scanner's default sweep, meaning the poisoned entry isn't just findable — it's the *first* thing found. Carving the file for known signatures turns up only the PNG at offset 0 and the appended ZIP's header, central directory, and end-of-central-directory records — all legitimate, none hiding anything new.

## An honest limitation

The filter-byte channel pins types Sub, Up, and Avg at roughly 25% each (each is the unique way to encode one particular 2-bit value), with only the "0-bucket" free to split between None and Paeth. A real PNG encoder run over this same ledger-page image produces an Up-dominant histogram with None and Average essentially at zero — a shape this channel cannot reproduce at any tuning, because it's fundamentally constrained by needing all five filter types represented in roughly fixed proportions. The resulting file is also about 8% larger than a straightforwardly-encoded equivalent. An analyst who tabulates filter-type frequency against a real encoder's output on the same pixels will notice something is off, and will have earned that observation. It's also worth repeating: nothing about this channel survives a re-encode. Any tool that writes the PNG back out — even one that changes nothing visible — picks its own filter bytes and silently destroys the stage.

## The break

1. Bitplane 0, row-major, offset 0 — ten lines of Python, or a generic scanner's default sweep — returns a works entry with a good stamp and a good CRC in seconds. Six stages of training say that's the answer. It is not: check the prefix character by character (`Null0rlgin`) and recognize it as stage 36's flag, not this stage's.
2. The rest of the bitplane/order/traversal space yields nothing; a ZIP carver finds the appended archive, a metadata tool finds the comment — neither inside a works entry.
3. Read the notes: nothing is written directly on the page; a page is laid down one scanline at a time; there are five ways to lay a line; four of them say something distinct and the fifth repeats the first. That's the entire channel description, including the `f=0`/`f=4` degeneracy.
4. Parse the PNG by hand: concatenate every IDAT chunk, inflate, take the two low bits of each row's filter-type byte across all 1900 rows, MSB-first, to get 475 bytes.
5. XOR with the keystream derived from the stage-36 flag. The container check fails. This is where the stage is actually won or lost: the channel is right, and the oracle still says no.
6. The notes already told you why: the chain key opens the outer lock; the six shares open what's underneath; neither alone opens anything. Go back through stages 31–36, pull the eight bytes after each `0x1F`, concatenate them in stage order, and hash.
7. XOR again with that derived key. `PL8`, correct length, CRC comes out clean. Do **not** substitute the seventh share sitting in the poisoned entry.

## Solve

[`solve.py`](37-mordant/solve/solve.py) runs against the shipped bytes plus the stage-36 flag and all six mordant shares, using an independent PNG reader — it walks the chunk stream itself, verifies every chunk's CRC, inflates the IDAT stream, and unfilters all 1900 lines by hand (including Paeth prediction) rather than relying on an image library, cross-checking the result against PIL's own decode. It also finds and decodes the poisoned plain-LSB decoy, and dynamically detects the one-character homoglyph against the stage-36 flag it was given.

```
python3 solve.py <path-to-37-mordant> <flag_36> <share_31> <share_32> <share_33> <share_34> <share_35> <share_36>
```
