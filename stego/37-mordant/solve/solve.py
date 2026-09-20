#!/usr/bin/env python3
"""37-mordant -- standalone solve.

Two independent locks, neither of which opens the stage alone:
  outer: the ordinary chain key, derived from stage 36's flag
  inner: SHA-256 of the six mordant shares (stages 31-36), concatenated
         in stage order

The channel is the PNG's scanline FILTER-TYPE byte (2 bits per line, from
f & 3), which no steganography tool inspects. The PNG is parsed and
unfiltered here from scratch, independent of PIL, then cross-checked
against PIL's own decode.

Run:  python3 solve.py <ship_dir> <flag_36> <share1> <share2> <share3> <share4> <share5> <share6>
(shares are the six 8-byte hex strings recovered from stages 31-36, in
stage order)
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import zlib

import numpy as np

PLATE_MAGIC = b"PL8"


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


def main() -> int:
    if len(sys.argv) < 9:
        raise SystemExit(
            f"usage: {sys.argv[0]} <ship_dir> <flag_36> <share1> ... <share6>"
        )
    ship, prev_seal = sys.argv[1], sys.argv[2]
    shares = [bytes.fromhex(s) for s in sys.argv[3:9]]
    art = os.path.join(ship, "mordant.png")
    data = open(art, "rb").read()

    # -------------------------------------------------------- 1. walk chunks
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, idat, text = 8, bytearray(), {}
    W = Hh = None
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        (crc,) = struct.unpack(">I", data[pos + 8 + ln:pos + 12 + ln])
        assert crc == zlib.crc32(typ + body) & 0xFFFFFFFF, ("bad CRC", typ)
        if typ == b"IHDR":
            W, Hh, depth, ctype, comp, filt, ilace = struct.unpack(">IIBBBBB", body)
            assert (depth, ctype, comp, filt, ilace) == (8, 0, 0, 0, 0)
        elif typ == b"IDAT":
            idat += body
        elif typ == b"tEXt":
            k, _, v = body.partition(b"\x00")
            text[k.decode("latin-1")] = v.decode("latin-1")
        pos += 12 + ln
        if typ == b"IEND":
            break

    raw = zlib.decompress(bytes(idat))
    assert len(raw) == Hh * (W + 1)

    # ------------------------------------------- 2. the channel: filter bytes
    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

    img = np.zeros((Hh, W), dtype=np.uint8)
    filters = []
    stride = W + 1
    prev = [0] * W
    for y in range(Hh):
        base = y * stride
        f = raw[base]
        filters.append(f)
        line = list(raw[base + 1:base + 1 + W])
        if f == 0:
            cur = line
        elif f == 1:
            cur = (np.cumsum(np.array(line, dtype=np.int64)) & 0xFF).tolist()
        elif f == 2:
            cur = [(line[x] + prev[x]) & 0xFF for x in range(W)]
        elif f == 3:
            cur, a = [], 0
            for x in range(W):
                a = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
                cur.append(a)
        elif f == 4:
            cur, a, c = [], 0, 0
            for x in range(W):
                a = (line[x] + paeth(a, prev[x], c)) & 0xFF
                cur.append(a)
                c = prev[x]
        else:
            raise ValueError(f"bad filter type {f} on line {y}")
        img[y] = cur
        prev = cur

    bits = []
    for f in filters:
        v = f & 3
        bits.append((v >> 1) & 1)
        bits.append(v & 1)
    blob = bytes_of(bits)
    print(f"scanlines: {Hh} -> channel {len(blob)} bytes")

    # --------------------------------------------------------- 3. two locks
    peel1 = xs(K(prev_seal), blob)          # outer lock: ordinary chain key
    mkey = hashlib.sha256(b"".join(shares)).digest()   # inner lock: the six shares
    clear = xs(mkey, peel1)
    payload = unplate(clear)
    if payload is None:
        raise SystemExit("PLATE did not verify -- wrong previous flag or shares?")

    flag = payload.decode()
    print("mordant key:", mkey.hex())
    print("flag       :", flag)

    # ------------------------------------------ 4. cross-check against PIL
    try:
        from PIL import Image
        pil = np.asarray(Image.open(art))
        print("sanity: hand-unfiltered image matches PIL's decode:", np.array_equal(img, pil))
    except Exception as e:
        print("sanity check skipped:", e)

    # --------------------------------- 5. the poisoned LSB entry (the trap)
    lsbbits = (img.reshape(-1)[:8192] & 1).tolist()
    d1 = unplate(bytes_of(lsbbits))
    if d1 is not None:
        d1flag, d1share = d1.split(b"\x1f", 1)
        print("decoy (plain LSB plane, VALID container -- the trap):", d1flag.decode())
        diff = [i for i, (a, b) in enumerate(zip(d1flag.decode(), prev_seal)) if a != b]
        if len(diff) == 1:
            i = diff[0]
            print(f"  homoglyph at index {i}: {prev_seal[i]!r} -> {d1flag.decode()[i]!r};"
                  f" this decoy carries a poisoned 'seventh share' ({d1share.hex()})"
                  " that breaks the inner lock if used")

    print("decoy (tEXt Comment):", text.get("Comment"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
