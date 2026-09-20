# 17-greylist

**Category:** Forensics · **Difficulty:** Medium

**Flag:**
```
Null0rigin{the_second_buffer_never_ran}
```

## What ships

`physmem.img` — 12.6 MB, a custom (not captured-from-a-real-OS) physical address space: a 24-byte header naming CR3, followed by six 2 MB frames — PML4, PDPT, PD, a code frame, a heap frame, and a hidden frame. It uses x86-64 4-level paging with 2 MB pages (the `PS` bit set at the PD level), so a single populated PD page is the entire page-table structure worth walking.

`vma_list.txt` — the process's own self-reported memory map, listing two regions: code and heap. The page tables actually map a third.

No Volatility profile ships, because there's no real kernel here to profile — this is a deliberately synthetic address space built to make manual page-table walking the honest way through, rather than a prop pretending to be a genuine captured Linux system. Faking the latter convincingly enough to survive a determined audit is its own project; this stage is upfront about what it is.

This stage is unlocked by 16-nightshift and unlocks 18-carrier.

## The mechanism

Every PD entry in the one populated PD page is enumerated, not guessed at by trying likely virtual addresses. Three entries are present. Two of them appear in `vma_list.txt`, and one does not — that third mapping is real: present, writable, backed by an actual physical frame, and simply never self-reported.

That hidden frame holds three equal-size bit-buffers (X, Y, Z) and two `FBM1`-tagged metadata structs giving a generation number and a `(front, back)` physical-address pair. Generation 1 (stale) pairs X with Z. Generation 2 (current) pairs X with Y. `X XOR Y` reproduces the flag's crisp bitmap exactly — this is 2-share visual cryptography, not an approximation, and the solve script's cross-check confirms 0 pixel diffs. `X XOR Z` (the stale, wrong pairing) is uniform noise.

Six decoy `Null0rigin{...}` strings sit in the heap frame in the clear, free to `strings` — volume, not a twist.

## Why there are only two candidate pairings, not three

The original design notes for this stage called for three candidate framebuffers, with two of the three pairings rendering readable text (both fake). That doesn't survive the algebra: with three buffers there are exactly three pairwise XORs, and `(X^Y) XOR (X^Z) XOR (Y^Z) = 0` always. If two pairings are independently chosen to be legible images, the third is forced to be whatever their XOR happens to be — generically noise, never a third chosen phrase. You cannot get two independent clean reveals *and* a real one out of three shares this way. This was caught during design, before any code was written to fake it, so the stage ships the honest version instead: one real pairing (marked by the higher-generation metadata), one wrong pairing (noise, not a decoy flag), with the six heap-string decoys carrying the "wrong answer" volume instead.

## Why the final image is crisp, not halftoned

Every other perceptually-gated stage in this chain dithers its rendered text so raw byte inspection can't shortcut past looking at an actual image. This stage doesn't, on purpose: the reveal here is an exact 2-share XOR, and dithering the two shares independently would break the exact cancellation (dithering is nondeterministic per-pixel thresholding, so XOR of two independently-dithered versions of the same text does not reproduce that text). The difficulty here is upstream of the image — finding the undeclared mapping and picking the right generation — not in reading it once revealed.

## The break

1. Parse the header for CR3. Find the one populated PML4 entry, the one populated PDPT entry, and enumerate every present PD entry under it (2 MB pages, `PS` bit) — three mappings.
2. Parse `vma_list.txt`'s ranges. Exactly one mapping isn't covered by any of them.
3. Scan that physical frame for `FBM1` metadata structs; keep the one with the higher generation.
4. XOR its named pair, render, look.

## Solve

`solve/solve.py` performs steps 1–4 mechanically and asserts the result is pixel-identical to an independently rendered reference of the known flag (0 diffs, exact by construction). As in the earlier stages, reading the final image is not what's automated here — everything upstream of it is.
