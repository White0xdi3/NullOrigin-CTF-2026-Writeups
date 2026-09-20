# 31-driftwood

**Category:** Steganography · **Difficulty:** easy · **Chain share:** share 1 of 6 for stage 37

**Flag:**
```
Null0rigin{what_the_negative_kept_from_the_print}
```

## What ships

- `driftwood.png` — 534,120 B. An RGBA PNG, 900x620, of a procedurally synthesized photographic plate: winding gear over a colliery yard, with film grain, a vignette, and scratch dust. Everything after the IEND chunk is an appended ZIP archive, so the file is simultaneously a valid PNG and a valid ZIP.
- `plate-card.txt` — the plate room's index card. This is the single most important document on the entire chain, and it's deliberately parked on the easiest stage.
- `description.txt` — story only, no hints.

## The mechanism

This is the entry point, and it's the only stage in the chain whose payload isn't keyed — there's no previous flag yet to derive a key from.

The real entry is written one bit per pixel into the **alpha plane's LSB, read column-major** (down the first column, then down the second, and so on). The payload is a works entry carrying `flag || 0x1F || share`, where the share is `9e4c1af0d3b27651` — the first of the six mordant shares that stage 37 needs.

`plate-card.txt` states the container's shape and then states the rule that carries the whole chain:

> If you have pulled something out of a plate and it does not begin with the stamp, and the check over it does not come out, then it is not a works entry. It is somebody's handwriting.

Because this chain ships no `verify` binary, that check is your only oracle — it tells you whether you have the *channel* right, and nothing ever tells you whether a *flag* is right except whether it opens the next stage.

## Decoys

Three decoys are placed so that every fast reflex pays out — and none of the three sits inside a works entry:

| # | Where | String |
|---|-------|--------|
| 1 | red plane LSB, row-major | `Null0rigin{pit_head_plate_number_four}` |
| 2 | PNG tEXt `Comment` | `NullOrigin{the_tide_returns_what_it_took}` |
| 3 | appended ZIP, `shingle.txt` | `Null0rigin{recovered_from_the_shingle}` |

Decoy 2 uses a capital O in place of the zero. Decoy 1 is placed in the red plane specifically because `zsteg -a` walks the R, G, B planes before the alpha plane, and row-major reads before column-major ones — so the first flag-shaped string you see is the wrong one, sitting several lines above the correct one in the same block of output.

## The break

1. `binwalk driftwood.png` / `strings` finds an appended ZIP after IEND. Extract it, read `shingle.txt`. **Candidate 1** — not inside a container.
2. `exiftool driftwood.png` surfaces the tEXt `Comment`. **Candidate 2** — not inside a container, and the prefix is `NullOrigin`, not `Null0rigin`.
3. `zsteg -a driftwood.png` reports the red-plane, row-major run first. **Candidate 3** — not inside a container.
4. Read `plate-card.txt`. None of the above begins with `PL8` and none has a check over it. Keep reading the `zsteg` output.
5. `b1,a,lsb,yx` — the alpha plane, column-major — begins `PL8\x01`. Parse the length and CRC-32, run the check, and it comes out.
6. Split the payload on `0x1F`: the flag, and 8 bytes that nothing has asked you to keep. Keep them anyway.

Done by hand, without `zsteg`, in six lines:

```python
a = numpy.asarray(PIL.Image.open("driftwood.png"))[:, :, 3]
H, W = a.shape
bits = [int(a[y, x] & 1) for x in range(W) for y in range(H)]
raw = bytes_from_bits(bits)
assert raw[:3] == b"PL8"
# length u16 LE at [4:6], crc32 u32 LE at [6:10], payload follows
```

## Solve

[`solve.py`](31-driftwood/solve/solve.py) performs the extraction from the shipped bytes only and prints the recovered flag and share. It also confirms mechanically that a *row-major* read of the same alpha plane does **not** validate — so the write-up's claim about read order is checked, not just asserted — and pulls all three decoys, confirming each one fails the container check.

```
python3 solve.py <path-to-31-driftwood>
```
