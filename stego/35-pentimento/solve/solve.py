#!/usr/bin/env python3
"""35-pentimento -- standalone solve.

Keyed by stage 34's flag. Every frame carries its own 256-entry LOCAL
colour table. Canonical order is ascending by (R<<16)|(G<<8)|B; split into
128 consecutive pairs, a pair written in canonical order is bit 0, swapped
is bit 1. 11 frames give 1408 bits. Swapping a pair also remaps the
frame's pixel indices, so the rendered picture never moves -- only the
table's *order* carries the payload.

Parses the GIF and its LZW streams from scratch (no reliance on any
external image library for the actual extraction), then uses PIL only at
the end as an independent cross-check that the rendered pixels match.

Run:  python3 solve.py <path-to-35-pentimento-dir-or-pentimento.gif> <flag_34>
"""
from __future__ import annotations

import os
import struct
import sys
import zlib

import numpy as np

PLATE_MAGIC = b"PL8"


def K(flag: str):
    import hashlib
    return hashlib.sha256(flag.encode()).digest()


def stream(k: bytes, n: int) -> bytes:
    import hashlib
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


# --------------------------------------------------------- our own GIF + LZW
def lzw_decode(data, min_code_size, npix):
    clear, eoi = 1 << min_code_size, (1 << min_code_size) + 1
    pos, nbits = 0, len(data) * 8
    table, code_size, prev = None, min_code_size + 1, None
    out, got = [], 0
    while got < npix and pos + code_size <= nbits:
        code = 0
        for k in range(code_size):
            code |= ((data[pos >> 3] >> (pos & 7)) & 1) << k
            pos += 1
        if code == clear:
            table = [bytes([i]) for i in range(clear)] + [b"", b""]
            code_size, prev = min_code_size + 1, None
            continue
        if code == eoi:
            break
        if table is None:
            table = [bytes([i]) for i in range(clear)] + [b"", b""]
        if code < len(table):
            entry = table[code]
        elif code == len(table) and prev is not None:
            entry = prev + prev[:1]
        else:
            raise ValueError(f"bad LZW code {code} (table {len(table)})")
        out.append(entry)
        got += len(entry)
        if prev is not None:
            table.append(prev + entry[:1])
            if len(table) == (1 << code_size) and code_size < 12:
                code_size += 1
        prev = entry
    return b"".join(out)[:npix]


def read_subblocks(data, p):
    out = bytearray()
    while True:
        n = data[p]
        p += 1
        if n == 0:
            return bytes(out), p
        out += data[p:p + n]
        p += n


def parse_gif(data):
    assert data[:6] in (b"GIF87a", b"GIF89a"), "not a GIF"
    sw, sh, packed, bg, aspect = struct.unpack("<HHBBB", data[6:13])
    p = 13
    gct = None
    if packed & 0x80:
        n = 2 << (packed & 7)
        p += n * 3
    frames, comments = [], []
    pending = None
    while p < len(data):
        b = data[p]
        if b == 0x3B:
            break
        if b == 0x21:
            label = data[p + 1]
            payload, p = read_subblocks(data, p + 2)
            if label == 0xF9:
                gp, delay, tidx = struct.unpack("<BHB", payload[:4])
                pending = dict(delay=delay)
            elif label == 0xFE:
                comments.append((len(frames), payload.decode("latin-1")))
            continue
        if b == 0x2C:
            left, top, iw, ih, ip = struct.unpack("<HHHHB", data[p + 1:p + 10])
            p += 10
            lct = None
            if ip & 0x80:
                n = 2 << (ip & 7)
                lct = [tuple(data[p + 3 * k:p + 3 * k + 3]) for k in range(n)]
                p += n * 3
            mcs = data[p]
            p += 1
            raw, p = read_subblocks(data, p)
            idx = np.frombuffer(lzw_decode(raw, mcs, iw * ih), dtype=np.uint8).reshape(ih, iw)
            frames.append(dict(w=iw, h=ih, lct=lct, idx=idx, gce=pending))
            pending = None
            continue
        raise ValueError(f"unknown block 0x{b:02X} at {p}")
    return dict(w=sw, h=sh, frames=frames, comments=comments)


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(f"usage: {sys.argv[0]} <ship_dir_or_gif> <flag_34>")
    ship, prev_seal = sys.argv[1], sys.argv[2]
    path = os.path.join(ship, "pentimento.gif") if os.path.isdir(ship) else ship
    blob = open(path, "rb").read()

    g = parse_gif(blob)
    frames = g["frames"]
    print(f"{len(frames)} frames, {g['w']}x{g['h']}")

    bits = []
    for f in frames:
        lct = f["lct"]
        if len(set(lct)) != 256:
            raise SystemExit("frame has duplicate colours")
        canon = sorted(lct, key=lambda c: (c[0] << 16) | (c[1] << 8) | c[2])
        for j in range(128):
            pair = (lct[2 * j], lct[2 * j + 1])
            ca, cb = canon[2 * j], canon[2 * j + 1]
            if pair == (ca, cb):
                bits.append(0)
            elif pair == (cb, ca):
                bits.append(1)
            else:
                raise SystemExit(f"pair {j} is not its canonical pair")

    raw = bytes_of(bits)
    clear = xs(K(prev_seal), raw)
    payload = unplate(clear)
    if payload is None:
        raise SystemExit("PLATE did not verify -- wrong previous flag?")
    flag, share = payload.split(b"\x1f")
    print("flag  :", flag.decode())
    print("share :", share.hex(), "(share 5 of 6)")

    # sanity: PIL's own renderer must agree pixel-for-pixel, proving the
    # table-order permutation never touched the visible picture
    try:
        from PIL import Image
        own = np.stack([np.asarray(f["lct"], dtype=np.uint8)[f["idx"]] for f in frames])
        im = Image.open(path)
        agree = all(np.array_equal(np.asarray(im.seek(i) or im.convert("RGB")), own[i])
                    for i in range(len(frames)))
        print("sanity: PIL's render matches our own parse, pixel for pixel:", agree)
    except Exception as e:
        print("sanity check skipped:", e)

    # decoys, printed as found
    delays = [f["gce"]["delay"] for f in frames]
    try:
        print("decoy (frame delays as ASCII):", bytes(delays).decode("ascii", "replace"))
    except Exception:
        pass
    for before, text in g["comments"]:
        print(f"decoy (comment before frame {before + 1}):", repr(text))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
