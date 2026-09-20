# 14-slackwater

**Category:** Forensics · **Difficulty:** Easy

**Flag:**
```
Null0rigin{ink_before_dawn}
```

## What ships

`card.img` — 111.9 MB, a raw FAT32 volume with no MBR or partition table (this is the partition itself, as if pulled with `dd if=/dev/mmcblk0p1`). It was built byte for byte by a custom FAT32 writer: every boot sector field, FAT entry, and directory entry is placed by hand rather than produced through a kernel mount.

A sealed AES-256-GCM box ships alongside it, keyed by `SHA-256(flag)`. It doesn't hand you the flag — it opens only after you already have it, as confirmation that you found the right one.

This is the entry point of the forensics chain and unlocks 15-handoff.

## The mechanism

The card looks like a DCIM recovery job: 40 small JPEG-shaped files in the root and a `DCIM/` subfolder, a `flag.txt` whose directory entry is marked deleted (`0xE5`) but whose data cluster was never overwritten, and one JPEG carrying a second flag in its file slack — the unused tail of its last cluster, past the length the directory entry declares. All four of these are genuine and recoverable, and all four are wrong. `verify` rejects every one of them.

The real flag isn't in any file at all. A block of 28,512 clusters — allocated in the FAT but referenced by *no* directory entry anywhere on the volume — holds one bit per cluster: allocated (`0x0FFFFFFF`, an orphaned single-cluster chain, exactly what a partial deletion leaves behind) or free (`0x00000000`). Read in cluster order and reshaped to a width of 792, those 28,512 bits form a Floyd-Steinberg-dithered rendering of the flag text itself.

Two things let this survive casual tooling:

1. **The directory/FAT split.** `fls`, `icat`, and `photorec` all answer "what exists" by walking directory entries. None of them treat "allocated but unreferenced" as a first-class thing to surface — `fls` on this image's `$OrphanFiles` virtual entry comes back empty. The picture is real disk state that standard listing tools have no reason to ever show you.
2. **The halftone itself.** Floyd-Steinberg dithering has no clean edges for an entropy scanner or byte-diff to catch on, and at native 1:1 scale the bitmap reads as pure static. It only resolves into text once rendered as an image and actually looked at.

The width, 792, isn't hidden — it's the boot sector's Volume ID field (`0x318` in the clear), which `file` prints as "serial number 0x318" without comment. That a camera card's "serial number" is a suspiciously round decimal number is the whole tell.

### Why the box is keyed the way it is

An earlier draft derived the sealed box's AES key from the width plus a whole-image hash — both mechanically obtainable without ever looking at a bit of the image content. That meant a script with zero vision could parse the FAT, derive the key, open the box, and read the flag from the decrypted JSON, skipping the halftone entirely. It was fixed by keying the box off `SHA-256(flag)` instead: the box now opens only *after* you already have the flag by reading the picture, so it can never be the way you get it.

The same reasoning sets this stage's share for the stage-20 meta: `SHA-256(flag)[:8]`, never a mechanical quantity like the ghost-run's start cluster or the Volume ID. A mechanical share would make the meta easier than this stage, which defeats the point of a meta.

## The break

1. Parse the boot sector by hand (`BPB_VolID` at offset `0x43` gives the width).
2. Read the FAT, walk every directory chain from root, and record every cluster that walk actually visits.
3. The largest run of clusters visited by *no* walk is the ghost region — 28,512 of them here, immediately obvious against roughly 100 real-file clusters.
4. Take one bit per cluster (FAT entry nonzero = 1), reshape at width 792, and render as a PNG.
5. Look at the PNG. That's the only non-scripted step.

## Solve

`solve/solve.py` performs steps 1–4 mechanically and asserts the rendered bitmap is byte-for-byte identical (0 pixel diffs) to an independently re-rendered reference of the known flag text, proving the reduction pipeline end to end. It does not perform step 5: it hardcodes the intended answer and uses it only to confirm `verify` and the sealed box are wired correctly. Any approach that reaches a correct flag on this stage without a human — or a vision-capable reader — actually looking at a rendered image hasn't solved it the way it was designed to be solved.
