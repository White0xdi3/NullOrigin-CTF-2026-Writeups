#!/usr/bin/env python3
"""32-safelight -- standalone solve.

Keyed by stage 31's flag. Recovers the works entry from the magnitude-1
class of the (print + negative - 255) residual, read row-major, XORed with
the chain's key-schedule stream.

Run:  python3 solve.py <path-to-32-safelight-dir> <flag_31>
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
        raise SystemExit(f"usage: {sys.argv[0]} <ship_dir> <flag_31>")
    ship, prev_seal = sys.argv[1], sys.argv[2]

    pr = np.asarray(Image.open(os.path.join(ship, "print.png")), dtype=np.int16)
    neg = np.asarray(Image.open(os.path.join(ship, "negative.png")), dtype=np.int16)
    assert pr.shape == neg.shape

    resid = pr + neg - 255
    vals, cnt = np.unique(resid, return_counts=True)
    hist = dict(zip(vals.tolist(), cnt.tolist()))
    assert set(vals.tolist()) <= {-1, 0, 1, 3}, hist
    print("residual histogram:", hist)

    decoy = resid == 3
    data = np.abs(resid) == 1
    assert not np.any(decoy & data), "decoy pixels leaked into the data channel"
    assert data.sum() % 8 == 0, data.sum()

    # data channel is read row-major; boolean indexing of a row-major array
    # already visits pixels in that order
    bits = (resid[data] == 1).astype(np.uint8)
    blob = bytes_of(bits.tolist())
    clear = bytes(a ^ b for a, b in zip(blob, stream(K(prev_seal), len(blob))))
    pay = unplate(clear)
    if pay is None:
        raise SystemExit("PLATE did not verify -- wrong previous flag?")

    flag, share = pay.split(b"\x1f", 1)
    print("carrier bits:", int(data.sum()))
    print("flag  :", flag.decode())
    print("share :", share.hex(), "(share 2 of 6)")

    # decoys, printed as found -- not asserted against any stored answer
    lsb = (pr & 1).astype(np.uint8)
    lsb_bytes = bytes_of(lsb.reshape(-1).tolist())
    assert flag not in lsb_bytes, "bitplane 0 should not leak the real flag"
    print("sanity: real flag not present verbatim in bitplane 0  OK")

    txt = Image.open(os.path.join(ship, "print.png")).text
    print("decoy (tEXt Comment):", repr(txt.get("Comment")))
    print("decoy (bitplane 0, amplified +3 class): see the writeup for the glyph render")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
