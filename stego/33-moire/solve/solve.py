#!/usr/bin/env python3
"""33-moire -- standalone solve.

Keyed by stage 32's flag. The channel is a 4x4-cell halftone: a cell's ink
weight (popcount) is always honoured, but for weights 5..11 there are two
extra arrangements of the same weight beyond the canonical dither pattern
-- those two arrangements ("A" and "B") are the carrier, one meaning bit 0
and the other bit 1. The pattern book itself is rederived here from first
principles (it's a pure function of the halftone's own void-and-cluster
energy ranking -- no external table needed), so nothing here depends on
private build state.

Run:  python3 solve.py <path-to-33-moire-dir> <flag_32>
"""
from __future__ import annotations

import hashlib
import itertools
import os
import struct
import sys
import zlib

import numpy as np
from PIL import Image

PLATE_MAGIC = b"PL8"

# ---------------------------------------------------------------- key schedule
def K(flag: str) -> bytes:
    return hashlib.sha256(flag.encode()).digest()


def stream(k: bytes, n: int) -> bytes:
    out, c = b"", 0
    while len(out) < n:
        out += hashlib.sha256(k + struct.pack(">I", c)).digest()
        c += 1
    return out[:n]


def xs(k: bytes, data: bytes) -> bytes:
    ks = stream(k, len(data))
    return bytes(a ^ b for a, b in zip(data, ks))


def unplate(buf: bytes):
    if len(buf) < 10 or buf[:3] != PLATE_MAGIC:
        return None
    ln = struct.unpack("<H", buf[4:6])[0]
    crc = struct.unpack("<I", buf[6:10])[0]
    pay = buf[10:10 + ln]
    if len(pay) != ln or (zlib.crc32(pay) & 0xFFFFFFFF) != crc:
        return None
    return pay


def bytes_of(bits) -> bytes:
    out = bytearray()
    acc = cnt = 0
    for b in bits:
        acc = (acc << 1) | (b & 1)
        cnt += 1
        if cnt == 8:
            out.append(acc)
            acc = cnt = 0
    return bytes(out)


# ------------------------------------------------------ halftone pattern book
# For each ink weight k, there are three named 4x4 arrangements: the
# canonical Bayer-order pattern C_k (used by every non-carrier cell), and
# for carrier weights (5..11) two more, A_k/B_k, chosen as the two lowest
# clumping-energy k-subsets that are not C_k. This is a pure function of
# hard constants -- the halftone plate itself hands you the alphabet.
CELL = 4
NPOS = CELL * CELL
CARRIER_LO, CARRIER_HI = 5, 11

BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
ORDER = tuple(sorted(range(NPOS), key=lambda p: BAYER[p // CELL][p % CELL]))
_KERNEL = {1: 3679, 2: 1353, 4: 183, 5: 67, 8: 3}


def mask_of(positions) -> int:
    m = 0
    for p in positions:
        m |= 1 << p
    return m


def energy(mask: int) -> int:
    pts = [p for p in range(NPOS) if (mask >> p) & 1]
    e = 0
    for i in range(len(pts)):
        ri, ci = divmod(pts[i], CELL)
        for j in range(i + 1, len(pts)):
            rj, cj = divmod(pts[j], CELL)
            dr = min((ri - rj) % CELL, (rj - ri) % CELL)
            dc = min((ci - cj) % CELL, (cj - ci) % CELL)
            e += _KERNEL[dr * dr + dc * dc]
    return e


def ranked(k: int):
    cands = sorted((energy(mask_of(c)), mask_of(c))
                   for c in itertools.combinations(range(NPOS), k))
    return [m for _, m in cands]


def pattern_book():
    book = {}
    for k in range(NPOS + 1):
        c = mask_of(ORDER[:k])
        a = b = None
        if CARRIER_LO <= k <= CARRIER_HI:
            a, b = [m for m in ranked(k) if m != c][:2]
        book[k] = (c, a, b)
    return book


def serpentine(n_rows, n_cols):
    for r in range(n_rows):
        cols = range(n_cols) if r % 2 == 0 else range(n_cols - 1, -1, -1)
        for c in cols:
            yield r, c


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(f"usage: {sys.argv[0]} <ship_dir> <flag_32>")
    ship, prev_seal = sys.argv[1], sys.argv[2]
    path = os.path.join(ship, "moire.png") if os.path.isdir(ship) else ship

    im = Image.open(path)
    assert im.mode == "1", "expected a 1-bit halftone, got mode %r" % im.mode
    W, H = im.size
    arr = np.asarray(im)
    ink = ~(arr if arr.dtype == bool else arr > 0)   # True where the paper is black
    NC, NR = W // CELL, H // CELL
    assert NC * CELL == W and NR * CELL == H

    cells = ink.reshape(NR, CELL, NC, CELL).transpose(0, 2, 1, 3)
    weight = (1 << np.arange(CELL * CELL)).reshape(CELL, CELL)
    mask = (cells * weight).sum(axis=(2, 3)).astype(np.int64)
    kpc = cells.sum(axis=(2, 3)).astype(np.int16)

    book = pattern_book()
    bit_of_mask = {}
    for k in range(CARRIER_LO, CARRIER_HI + 1):
        c, a, b = book[k]
        bit_of_mask[a], bit_of_mask[b] = 0, 1

    carrier = (kpc >= CARRIER_LO) & (kpc <= CARRIER_HI)
    n_carrier = int(carrier.sum())

    bits = []
    for r, c in serpentine(NR, NC):
        if not carrier[r, c]:
            continue
        m = int(mask[r, c])
        if m not in bit_of_mask:
            raise SystemExit(f"cell ({r},{c}) weight {kpc[r, c]} matches neither A nor B")
        bits.append(bit_of_mask[m])

    raw = bytes_of(bits)
    clear = xs(K(prev_seal), raw)
    payload = unplate(clear)
    if payload is None:
        raise SystemExit("no PLATE under the stage-32 key stream -- wrong previous flag?")

    flag, _, share = payload.partition(b"\x1f")
    print(f"carrier cells: {n_carrier} of {NR * NC} ({100.0 * n_carrier / (NR * NC):.1f}%)")
    print("flag  :", flag.decode())
    print("share :", share.hex(), "(share 3 of 6)")

    print("decoy (tEXt Comment):", repr(im.text.get("Comment")))
    blob = open(path, "rb").read()
    tail = blob[blob.rindex(b"IEND") + 8:]
    if tail:
        print("decoy (trailer after IEND):", tail.decode("ascii", "replace").strip())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
