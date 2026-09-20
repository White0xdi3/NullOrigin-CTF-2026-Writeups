# 07-daybook

**Category:** Cryptography · **Difficulty:** Entry

**Flag:**
```
Null0rigin{you_ran_a_dead_process_backwards}
```

Unlocked by **06-bindery**; solving it unlocks **08-errata**.

## What ships

`core.5711` — 419,868,672 bytes, a real ELF core dump from a real static binary that called `abort()` mid-record. The binary itself does not ship. Neither does a key, a spec, a test vector, or anything runnable. Also included: `daybook.sealed`, `verify`, `description.txt`.

## The mechanism

The cipher is a 320-bit permutation over five 64-bit lanes, copied into an anonymous **RWX** mapping at start-up. That mapping is the only copy of the code in existence, so the disassembly inside the dump *is* the specification:

- Twelve rounds of: a round constant folded into lane 2, a width-5 column layer, five lane rotations (7, 19, 31, 43, 57), and a lane shuffle.
- The column layer applies five updates, each touching one lane using only the others, so every update is invertible and so is the whole permutation — it can even be tabulated over 32 inputs if you'd rather not reverse the math.
- A reflected CRC with polynomial `0x82F63B78` serves as the per-record checksum.

### Three things that make the dump insufficient on its own

1. **There is no key.** The 32-byte key buffer was `explicit_bzero`'d immediately after the key schedule ran; the build asserts the bytes are not present anywhere in the dump. All four decoy `Null0rigin{...}` strings sit in the working set exactly where a naive key carve would land.
2. **The state is 128 bits short.** The output routine stages each block *in* the two leading lanes so the caller can lift it straight out, then restores them. The process died between those two steps, so the state in `.bss` has its rate replaced by the last ciphertext block — a naive backward run from the dumped state is impossible.
3. **What's in the dump is ciphertext, not keystream.** 61,520 bytes of already-written records means the mapping is *not* a free correctness oracle for a reconstructed permutation — a nearly-right inverse produces no ASCII and no discernible gradient toward the right answer.

## The break

The missing 128 bits are ciphertext XOR the writer's close-of-log trailer. `bc_finish` builds that trailer from two immediates in the instruction stream, and it appears nowhere else in the dump — it has to be read directly out of the emitted code. With the rate restored, the state is whole, the permutation runs backwards to the head of the log, and the per-record CRC (polynomial also pulled from the emitted code) confirms correctness.

One accident the build didn't plan for: the last staged block was still live in registers at the moment of the fault, so it also appears twice inside `NT_PRSTATUS`. The solve script finds three candidate locations for it and distinguishes the right one by which actually runs the permutation backwards successfully.

## Why it's hard / why there's no shortcut

There's no key, no runnable reference, and no oracle — the only way in is reconstructing the permutation from the RWX-mapped disassembly, recovering the missing rate bits from immediates buried in emitted code, and validating against the per-record CRC. Any near-miss on the recovered trailer produces garbage with no gradient signal to chase.

## Solve

[`solve.py`](07-daybook/solve/solve.py) runs in 1.8–2.0 s with the 420 MB dump warm in page cache, or 9.0 s on a cold first read. It walks `PT_LOAD`, picks the one RWX mapping, locates the ciphertext by entropy against a working set that's otherwise counter lines, restores the rate, steps the permutation backwards 3,853 times (the log itself is 3,845 blocks; the extra 8 are a deliberate alignment margin), and checks 496 record checksums — all pass.

**Feeds the finale:** the internal secret this stage contributes to 13-lantern is the 320-bit state *before* the two leading lanes were staged over (the restored state, not the dumped one), big-endian, lanes 0 through 4 in order, 40 bytes. The dumped state is the wrong one and differs in its first 128 bits — only the close-of-log trailer recovered from the emitted code tells the two apart.
