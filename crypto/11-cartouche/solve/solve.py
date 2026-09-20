#!/usr/bin/env python3
"""11-cartouche -- solve.

The damage is the message.

The device wrote the key by deliberately flipping 40 cells in an
otherwise-constant recovery page. Real rot sits on top of it at the same
order of magnitude and is indistinguishable from payload in any single copy.
The page was programmed into 32 shadow copies at 32 physical addresses:
payload flips are in the 8 copies written after the key was burned and are
identical in all 8; rot is per-copy. Majority-vote the 32 to get the clean
page, difference each copy against it, then intersect the 8 heavy copies.

Everything in the standard kit -- ECC decode, information-set decoding, file
carving -- corrects the errors. That is the opposite of the task.

Run:  python3 solve/solve.py [dist_dir]
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import sys
import time

import numpy as np
from Crypto.Cipher import AES

SLUG = "11-cartouche"
PAGE_DATA, PAGE_SPARE = 4096, 128
PAGE_RAW = PAGE_DATA + PAGE_SPARE
BLK_PAGES, PLANES = 64, 2
UNIVERSE = PAGE_DATA * 8
KSET = 40
MAGIC = b"ORIGIN-RECOVERY\0"


# ---- reversed out of recover.elf -----------------------------------------
def seed_of(addr: np.ndarray) -> np.ndarray:
    s = (addr.astype(np.uint64) * np.uint64(0x9E3779B1)) & np.uint64(0xFFFFFFFF)
    s ^= s >> np.uint64(15)
    s = (s * np.uint64(0x85EBCA6B)) & np.uint64(0xFFFFFFFF)
    s ^= s >> np.uint64(13)
    s &= np.uint64(0x7FFFFFFF)
    return np.where(s == 0, np.uint64(0x2A5D1FEB), s)


def basis(nbytes: int) -> np.ndarray:
    """The register is GF(2)-linear in its seed, so 31 precomputed keystreams
    generate every keystream by XOR -- that is what makes half a million
    scrambled pages tractable."""
    out = np.zeros((31, nbytes), dtype=np.uint8)
    for b in range(31):
        s = 1 << b
        for i in range(nbytes):
            o = 0
            for k in range(8):
                lsb = s & 1
                s >>= 1
                if lsb:
                    s ^= 0x48000000       # x^31 + x^28 + 1
                o |= lsb << k
            out[b, i] = o
    return out


def keystream_batch(addrs: np.ndarray, nbytes: int, bas: np.ndarray) -> np.ndarray:
    seeds = seed_of(addrs)
    out = np.zeros((addrs.size, nbytes), dtype=np.uint8)
    for b in range(31):
        idx = np.nonzero((seeds >> np.uint64(b)) & np.uint64(1))[0]
        if idx.size:
            out[idx] ^= bas[b, :nbytes]
    return out


def slot_to_addr(slots: np.ndarray, total: int) -> np.ndarray:
    return (slots & 1) * (total // PLANES) + (slots >> 1)


def rank_of(positions) -> int:
    return sum(math.comb(int(c), i + 1) for i, c in enumerate(sorted(positions)))


def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t0 = time.time()
    img = dist / "nand.bin"
    total = img.stat().st_size // PAGE_RAW
    print(f"[00] {img.stat().st_size:,} B = {total:,} raw pages of "
          f"{PAGE_DATA}+{PAGE_SPARE}, {total // BLK_PAGES} blocks, {PLANES} planes")

    raw = np.memmap(img, dtype=np.uint8, mode="r", shape=(total, PAGE_RAW))
    slots = np.arange(total, dtype=np.uint64)
    addrs = slot_to_addr(slots, total)
    print("[01] de-interleaved planes: slot s -> plane (s&1), local s>>1")

    # ---- find the shadow copies by their descrambled header ---------------
    t = time.time()
    b16 = basis(16)
    hit = []
    CH = 1 << 16
    for base in range(0, total, CH):
        m = min(CH, total - base)
        head = np.array(raw[base:base + m, :16])
        ks = keystream_batch(addrs[base:base + m], 16, b16)
        ok = np.all((head ^ ks) == np.frombuffer(MAGIC, dtype=np.uint8), axis=1)
        hit.extend((base + np.nonzero(ok)[0]).tolist())
    print(f"[02] {len(hit)} shadow copies of the recovery page "
          f"({time.time()-t:.1f}s)")
    assert len(hit) >= 8, "scrambler not reversed correctly"

    # ---- descramble them in full ------------------------------------------
    bfull = basis(PAGE_DATA)
    sel = np.array(hit, dtype=np.uint64)
    pages = np.array(raw[sel, :PAGE_DATA]) ^ keystream_batch(addrs[sel], PAGE_DATA, bfull)
    bits = np.unpackbits(pages, axis=1, bitorder="little")      # (copies, 32768)

    # ---- majority vote = the page as it was written before the key --------
    ref = (bits.sum(axis=0) * 2 > bits.shape[0]).astype(np.uint8)
    diff = bits ^ ref
    weights = diff.sum(axis=1)
    print(f"[03] flip counts per copy: {sorted(weights.tolist())}")

    # two populations: rot only, and rot + payload
    order = np.sort(weights)
    gap = int(np.argmax(np.diff(order))) + 1
    thresh = (order[gap - 1] + order[gap]) / 2
    key_idx = np.nonzero(weights > thresh)[0]
    print(f"[04] {key_idx.size} heavy copies (> {thresh:.1f} flips) carry the payload")

    common = np.ones(UNIVERSE, dtype=bool)
    for i in key_idx:
        common &= diff[i].astype(bool)
    positions = np.nonzero(common)[0]
    print(f"[05] intersection across the heavy copies: {positions.size} cells")
    assert positions.size == KSET, f"expected {KSET} payload cells, got {positions.size}"
    print(f"[06] payload cells: {positions.tolist()}")

    rank = rank_of(positions)
    secret = rank.to_bytes(56, "big")
    print(f"[07] combinatorial rank = {secret.hex()}  (log2 {math.log2(rank):.1f})")

    box = (dist / "cartouche.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    c = AES.new(hashlib.sha256(secret).digest(), AES.MODE_GCM, nonce=box[8:20])
    c.update(SLUG.encode())
    data = json.loads(c.decrypt_and_verify(box[20:-16], box[-16:]))
    print(f"[08] total {time.time()-t0:.1f}s")
    print(data["flag"])
    assert data["flag"].startswith("Null0rigin{") and data["flag"].endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
