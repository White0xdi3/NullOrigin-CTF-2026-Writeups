#!/usr/bin/env python3
"""31-driftwood -- standalone solve.

Unkeyed entry point of the stego chain. Recovers the works entry from the
alpha plane's LSB, read column-major, and pulls out the flag and the first
of the six mordant shares. Also demonstrates the three decoys and confirms
each one sits outside a valid container.

Run:  python3 solve.py <path-to-31-driftwood-dir-or-driftwood.png>
"""
from __future__ import annotations

import io
import os
import struct
import sys
import zipfile
import zlib

import numpy as np
from PIL import Image

PLATE_MAGIC = b"PL8"


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
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    png_path = os.path.join(path, "driftwood.png") if os.path.isdir(path) else path

    im = Image.open(png_path)
    assert im.mode == "RGBA", im.mode
    a = np.asarray(im)
    H, W = a.shape[:2]

    # --- real channel: alpha plane, COLUMN-major, first 2048 bits ----------
    al = a[:, :, 3]
    bits = [int(al[y, x] & 1) for x in range(W) for y in range(H)][:8 * 256]
    payload = unplate(bytes_of(bits))
    if payload is None:
        raise SystemExit("no works entry in the alpha plane (column-major)")
    flag, share = payload.split(b"\x1f")
    print("flag  :", flag.decode())
    print("share :", share.hex(), "(share 1 of 6, needed by stage 37)")

    # --- sanity: the row-major read of the same plane must NOT validate ----
    rm = [int(al[y, x] & 1) for y in range(H) for x in range(W)][:8 * 256]
    assert unplate(bytes_of(rm)) is None, "row-major should not validate"
    print("sanity: row-major read of the same plane does not unplate  OK")

    # --- decoys: none of the three sits inside a valid works entry ---------
    r = a[:, :, 0]
    d1_bytes = bytes_of([int(r[y, x] & 1) for y in range(H) for x in range(W)][:8 * 64])
    d1 = d1_bytes.split(b"\x00")[0].decode("ascii", "ignore")
    d1_full = bytes_of([int(r[y, x] & 1) for y in range(H) for x in range(W)][:8 * 256])
    assert unplate(d1_full) is None, "red-plane decoy should not be a valid works entry"
    print("decoy 1 (red plane, row-major, no container):", repr(d1))

    print("decoy 2 (PNG tEXt Comment, no container):", repr(im.text.get("Comment")))

    blob = open(png_path, "rb").read()
    z = zipfile.ZipFile(io.BytesIO(blob[blob.index(b"PK\x03\x04"):]))
    d3 = z.read("shingle.txt").decode()
    print("decoy 3 (appended ZIP, shingle.txt, no container):", repr(d3.strip()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
