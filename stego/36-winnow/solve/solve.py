#!/usr/bin/env python3
"""36-winnow -- standalone solve.

Keyed by stage 35's flag. Rivest's chaffing and winnowing: 2048 cells of
32x32, row-major, taken in pairs. Each cell's first 17 pixel LSBs are
bit || tag16. A record is WHEAT iff its tag matches the first two octets
of sha256(key || cell_index_be16 || bit_octet). For each pair, exactly one
of the two cells authenticates under the correct key -- take that bit,
discard the other. There is no statistical attack: with the wrong key,
zero cells validate.

Run:  python3 solve.py <path-to-36-winnow-dir> <flag_35>
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import zlib

import numpy as np
from PIL import Image

PLATE_MAGIC = b"PL8"
CELL = 32
COLS, ROWS = 64, 32
NCELL = COLS * ROWS
NPAIR = NCELL // 2


def K(flag: str) -> bytes:
    return hashlib.sha256(flag.encode()).digest()


def stream(k: bytes, n: int) -> bytes:
    out, c = b"", 0
    while len(out) < n:
        out += hashlib.sha256(k + struct.pack(">I", c)).digest()
        c += 1
    return out[:n]


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


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(f"usage: {sys.argv[0]} <ship_dir> <flag_35>")
    ship, prev_seal = sys.argv[1], sys.argv[2]

    im = Image.open(os.path.join(ship, "sheet.png"))
    assert im.mode == "L", im.mode
    img = np.asarray(im, dtype=np.uint8)
    W, H = COLS * CELL, ROWS * CELL
    assert im.size == (W, H)

    bits = np.zeros(NCELL, dtype=np.uint8)
    tags = np.zeros(NCELL, dtype=np.int64)
    for i in range(NCELL):
        r, c = divmod(i, COLS)
        rec = img[r * CELL, c * CELL:c * CELL + 17] & 1
        bits[i] = rec[0]
        t = 0
        for v in rec[1:]:
            t = (t << 1) | int(v)
        tags[i] = t

    key = K(prev_seal)

    def valid(k, i):
        h = hashlib.sha256(k + i.to_bytes(2, "big") + bytes([int(bits[i])])).digest()
        return tags[i] == int.from_bytes(h[:2], "big")

    authentic = [[k for k in (2 * j, 2 * j + 1) if valid(key, k)] for j in range(NPAIR)]
    counts = [len(a) for a in authentic]
    npay = next((j for j in range(NPAIR) if counts[j] == 0), NPAIR)
    if not all(c == 1 for c in counts[:npay]):
        raise SystemExit("a payload pair did not authenticate exactly once -- wrong previous flag?")

    wheat_bits = [int(bits[authentic[j][0]]) for j in range(npay)]
    blob = bytes_of(wheat_bits)
    clear = bytes(a ^ b for a, b in zip(blob, stream(key, len(blob))))
    payload = unplate(clear)
    if payload is None:
        raise SystemExit("PLATE did not verify")

    flag, share = payload.split(b"\x1f", 1)
    print(f"wheat pairs: {npay} of {NPAIR}")
    print("flag  :", flag.decode())
    print("share :", share.hex(), "(share 6 of 6 -- the last one stage 37 needs)")

    # the trap: reading every cell without winnowing, ignoring the tags
    naive = bytes_of(bits.tolist())
    print("decoy (naive full read, no winnowing, tail):", naive[-60:].decode("ascii", "replace"))

    print("note: cell 890 also encodes a genuine QR-code decoy; decoding it isn't")
    print("      needed to solve this stage, so it's omitted here (see the writeup)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
