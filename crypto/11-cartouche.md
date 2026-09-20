# 11-cartouche

**Category:** Cryptography · **Difficulty:** Hard

**Flag:**
```
Null0rigin{you_read_the_damage_instead_of_the_data}
```

Unlocked by **10-carillon**; solving it unlocks **12-lastpage**.

## What ships

- `nand.bin` — 2,214,592,512 bytes of raw NAND: 4096+128-byte pages, 64-page blocks, 8192 blocks, two planes interleaved one slot at a time, worn blocks, bad-block markers, erased and partially erased blocks, and per-page CRC/ECC-looking spare bytes.
- `recover.elf` — a stripped static ELF that refuses to run without a service token that doesn't ship. It contains the plane de-interleave logic, the address-seeded data randomizer, and the rank/unrank routines.
- `cartouche.sealed` — AES-256-GCM under `SHA-256(rank as 56 big-endian bytes)` — nothing else is concatenated into the key material.

## The mechanism

The flaw is that the damage *is* the message. The device didn't store the key as data and didn't protect it with ECC. Instead it **wrote** the key by deliberately flipping 40 cells in an otherwise-constant recovery page, and the key is the **combinatorial rank** of that flip-position set:

```
rank = Σ_{i=0..39} C(pos_i, i+1)          # pos ascending, 0 ≤ pos < 32768
```

`C(32768, 40) ≈ 2^440`, so the recovered integer is 438 bits wide and uniformly distributed. Every reflex in the standard forensics kit — ECC decode, syndrome decoding, information-set decoding, file carving — is aimed at *correcting* errors. Here that's exactly the wrong instinct: the errors are the payload.

### Why it's separable at all

Real bit rot is present at the same order of magnitude (Poisson-distributed, mean 6 per copy) and is **indistinguishable from payload within any single copy**. Separation is only possible because the recovery page was programmed as 32 shadow copies at 32 physical addresses: the payload flips were *written*, so they're identical across the 8 copies burned after the key, while rot is independently random per copy.

Measured flip counts per copy:
```
[1,1,2,2,3,3,3,3,3,4,4,4,5,5,6,6,7,7,7,8,9,9,10,10,
 44,44,44,45,45,45,46,46]
```

The two populations separate cleanly on flip count. Majority-voting the 32 copies gives the clean page; differencing each copy against it gives that copy's flip set; the two populations separate by flip count, and intersecting the 8 heavy ones isolates the 40 payload cells and nothing else. The build asserts no rot cell appears in more than 2 of the 8 key copies (measured worst case: 1), and every payload cell appears in all 8.

## The break

1. Locate the 32 shadow copies of the recovery page via the `ORIGIN-RECOVERY` header (only visible after reversing the scrambler and de-interleaving planes).
2. Majority-vote across all 32 copies to recover the clean baseline page.
3. XOR each copy against the baseline to get its individual flip set; separate the 8 "heavy" copies (> 27.0 flips) from the 24 rot-only copies by flip count.
4. Intersect the 8 heavy copies to isolate exactly the 40 payload cells.
5. Compute the combinatorial rank of the sorted flip positions and use it as the AES-256-GCM key material.

## Why it's hard / why there's no shortcut

- **The scrambler.** Copies are XOR-masked by a 31-bit Galois LFSR (`x^31 + x^28 + 1`) seeded from the *physical* page address — a real NAND controller idiom. Without reversing `seed_of` and the tap polynomial out of `recover.elf`, and without the plane de-interleave (`slot s → plane s&1, local s>>1`), the 32 copies look like 32 unrelated random pages and the locating header is invisible.
- **The wear map.** Payload positions are drawn uniformly over the whole index space with no reference to erase counts — the build asserts a one-sample KS test against uniform (`D = 0.1005 < 0.2150` at α = 0.05), so "restrict to unworn positions" buys nothing.
- **The index space convention.** `byte*8 + bit` with bit 0 as LSB, and the rank convention `Σ C(pos_i, i+1)`, live only inside `recover.elf`. The build script cross-checks the compiled binary against a Python reference on the randomizer, rank, and unrank routines, so the two can never drift apart.
- **No oracle.** The key is uniform; 39 of 40 positions correct is indistinguishable from wrong. `recover.elf` never validates a candidate — it simply refuses to run at all without the service token.

## Measured

```
2,214,592,512 B = 524,288 raw pages of 4096+128, 8192 blocks, 2 planes
32 shadow copies of the recovery page (0.5-0.7s warm; 9.5s on a cold read of the 2.2 GB image)
8 heavy copies (> 27.0 flips) carry the payload
intersection across the heavy copies: 40 cells
combinatorial rank = 003a3b71…ceb6  (log2 437.9)
```

## Solve

The recovery pipeline above is implemented end-to-end in [`solve.py`](11-cartouche/solve/solve.py), running against the raw 2.2 GB image in under 10 seconds cold, well under 1 second warm.

**Feeds the finale:** the internal secret this stage contributes to 13-lantern is the 40 payload cell positions, sorted ascending in the index space `recover.elf` fixes (`byte*8 + bit`, bit 0 = LSB), encoded as their combinatorial rank and exported as 56 bytes big-endian. That encoding is exactly what resolves the flip-set-versus-scrambled-complement ambiguity — the unrank routine in `recover.elf` pins it down.
