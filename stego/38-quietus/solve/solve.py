#!/usr/bin/env python3
"""38-quietus -- standalone solve.

Keyed by stage 37's flag. Nothing is hidden in the pixels -- the message
is which choice the DEFLATE encoder made at every position where it had
one. The IDAT stream is fixed-Huffman only, so it's parseable by hand
straight out of RFC 1951. At a decision point (a position whose 3 bytes
reoccurred earlier in the window), a length-3 match is bit 1 and a
literal is bit 0; positions with no choice available carry nothing.

This is a second, independent DEFLATE reader -- it doesn't reuse the
challenge's own encoder code, only the public RFC 1951 fixed-Huffman
tables.

Run:  python3 solve.py <path-to-38-quietus-dir> <flag_37>
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import zlib

PLATE_MAGIC = b"PL8"
WINDOW = 32768


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


LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43,
            51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LEN_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3,
             4, 4, 4, 4, 5, 5, 5, 5, 0]
DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257,
             385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289,
             16385, 24577]
DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8,
              9, 9, 10, 10, 11, 11, 12, 12, 13, 13]


class BitReader:
    def __init__(self, buf):
        self.b, self.p = buf, 0

    def bit(self):
        v = (self.b[self.p >> 3] >> (self.p & 7)) & 1
        self.p += 1
        return v

    def bits(self, k):
        v = 0
        for s in range(k):
            v |= self.bit() << s
        return v

    def code(self, k):
        v = 0
        for _ in range(k):
            v = (v << 1) | self.bit()
        return v


def litlen(br):
    """RFC 1951 3.2.6 fixed literal/length alphabet."""
    c = br.code(7)
    if c <= 0b0010111:
        return 256 + c
    c = (c << 1) | br.bit()
    if 0b00110000 <= c <= 0b10111111:
        return c - 0b00110000
    if 0b11000000 <= c <= 0b11000111:
        return 280 + (c - 0b11000000)
    c = (c << 1) | br.bit()
    assert 0b110010000 <= c <= 0b111111111, bin(c)
    return 144 + (c - 0b110010000)


def inflate_fixed(deflated):
    br = BitReader(deflated)
    out = bytearray()
    tok_at = {}
    while True:
        bfinal, btype = br.bit(), br.bits(2)
        assert btype == 1, f"expected fixed-Huffman only, got BTYPE={btype}"
        while True:
            start = len(out)
            sym = litlen(br)
            if sym == 256:
                break
            if sym < 256:
                tok_at[start] = (0, sym)
                out.append(sym)
            else:
                k = sym - 257
                ln = LEN_BASE[k] + (br.bits(LEN_EXTRA[k]) if LEN_EXTRA[k] else 0)
                dc = br.code(5)
                d = DIST_BASE[dc] + (br.bits(DIST_EXTRA[dc]) if DIST_EXTRA[dc] else 0)
                tok_at[start] = (1, (ln, d))
                for _ in range(ln):
                    out.append(out[len(out) - d])
        if bfinal:
            break
    return bytes(out), tok_at


def prev_occurrence(buf):
    n = len(buf)
    prev = [-1] * n
    last = {}
    for i in range(n - 2):
        k = buf[i:i + 3]
        prev[i] = last.get(k, -1)
        last[k] = i
    return prev


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(f"usage: {sys.argv[0]} <ship_dir> <flag_37>")
    ship, prev_seal = sys.argv[1], sys.argv[2]
    path = os.path.join(ship, "quietus.png") if os.path.isdir(ship) else ship
    blob_png = open(path, "rb").read()

    assert blob_png[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    off, idat = 8, bytearray()
    while off < len(blob_png):
        ln = struct.unpack(">I", blob_png[off:off + 4])[0]
        typ = blob_png[off + 4:off + 8]
        body = blob_png[off + 8:off + 8 + ln]
        if typ == b"IDAT":
            idat += body
        off += 12 + ln
        if typ == b"IEND":
            break

    zstream = bytes(idat)
    assert zstream[:2] == b"\x78\x01", zstream[:2].hex()
    deflated = zstream[2:-4]

    data, tok_at = inflate_fixed(deflated)
    assert zlib.decompress(zstream) == data, "hand parse disagrees with zlib"

    prev = prev_occurrence(data)
    n = len(data)
    bits, i = [], 0
    while i < n:
        kind, v = tok_at[i]
        avail = i + 3 <= n and prev[i] >= 0 and (i - prev[i]) <= WINDOW
        if avail:
            bits.append(kind)
            if kind == 1:
                ln, d = v
                i += 3
            else:
                i += 1
        else:
            i += 1

    raw = bytes_of(bits)
    clear = xs(K(prev_seal), raw[:288])
    payload = unplate(clear)
    if payload is None:
        raise SystemExit("PLATE did not verify -- wrong previous flag?")

    print("flag:", payload.decode())

    # decoys, printed as found
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(path)
        pix = np.asarray(im)
        lsb = bytes_of((pix & 1).reshape(-1).tolist())
        d1 = lsb[:lsb.index(b"\x00")].decode("latin-1")
        print("decoy (bitplane 0):", repr(d1))
        print("decoy (tEXt Comment):", im.text.get("Comment"))
    except Exception as e:
        print("decoy printout skipped:", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
