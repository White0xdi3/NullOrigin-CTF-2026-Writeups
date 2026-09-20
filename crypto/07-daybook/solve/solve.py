#!/usr/bin/env python3
"""07-daybook -- solve.

Only a core dump ships. The binary does not, the key does not, and neither
does anything runnable that models the cipher. (The generic `verify`
flag-checker ships, as on every stage; it is no oracle.)

  1. Walk PT_LOAD. Exactly one mapping is anonymous and RWX: that is the
     scratch page the writer copied its cipher into at start-up, and the only
     copy of the cipher that exists. Disassembling it gives a 320-bit state in
     five lanes, twelve rounds of {constant, a width-5 column layer, five lane
     rotations, a lane shuffle}, and a reflected CRC with polynomial
     0x82F63B78.
  2. The key buffer is zero -- it was wiped straight after the schedule. The
     four Null0rigin strings sitting in the heap where a key carve lands are
     decoys.
  3. The working set holds 61,520 bytes of high-entropy data: already-written
     CIPHERTEXT, not keystream, so the mapping is no correctness oracle.
  4. The state in .bss has its two leading lanes equal to the LAST ciphertext
     block: the output routine stages each block in the rate lanes and puts
     them back afterwards, and the process stopped in between. 128 bits short.
  5. Those 128 bits are ciphertext XOR the writer's close-of-log trailer,
     which `bc_finish` builds from two immediates and which appears nowhere
     else in the dump.
  6. With the state whole, every layer inverts, so the permutation runs
     backwards to the start of the log. The per-record CRC says it worked.

Run:  python3 solve/solve.py [dist_dir]
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import struct
import sys
import time

import numpy as np
from Crypto.Cipher import AES

SLUG = "07-daybook"
M64 = (1 << 64) - 1
ROT = (7, 19, 31, 43, 57)
TRAILER = (0xFFFFFFFF4C4E524A.to_bytes(8, "little")
           + 0x005245544941525455.to_bytes(8, "little"))


def rol(x, n):
    return ((x << n) | (x >> (64 - n))) & M64


def ror(x, n):
    return rol(x, 64 - n)


def rc(r):
    return (0x0F0E0D0C0B0A0908 + r * 0x0101010101010101) & M64


def perm(s):
    a, b, c, d, e = s
    for r in range(12):
        c ^= rc(r)
        a ^= b & c
        b ^= c | d
        c ^= d & ~e & M64
        d ^= e | a
        e ^= a & b
        a = rol(a, ROT[0]); b = rol(b, ROT[1]); c = rol(c, ROT[2])
        d = rol(d, ROT[3]); e = rol(e, ROT[4])
        a, b, c, d, e = d, e, a, b, c
    return [a, b, c, d, e]


def iperm(s):
    a, b, c, d, e = s
    for r in range(11, -1, -1):
        a, b, c, d, e = c, d, e, a, b          # undo the lane shuffle
        a = ror(a, ROT[0]); b = ror(b, ROT[1]); c = ror(c, ROT[2])
        d = ror(d, ROT[3]); e = ror(e, ROT[4])
        e ^= a & b                              # undo the column layer, in
        d ^= e | a                              # reverse
        c ^= d & ~e & M64
        b ^= c | d
        a ^= b & c
        c ^= rc(r)
    return [a, b, c, d, e]


def crc32c(buf: bytes) -> int:
    c = 0xFFFFFFFF
    for byte in buf:
        c ^= byte
        for _ in range(8):
            c = (c >> 1) ^ (0x82F63B78 & -(c & 1))
    return (~c) & 0xFFFFFFFF


def loads(raw: bytes):
    phoff = struct.unpack_from("<Q", raw, 0x20)[0]
    phentsize, phnum = struct.unpack_from("<HH", raw, 0x36)
    out = []
    for i in range(phnum):
        o = phoff + i * phentsize
        typ, flags, offset, vaddr, paddr, filesz, memsz, align = \
            struct.unpack_from("<IIQQQQQQ", raw, o)
        if typ == 1 and filesz:
            out.append((flags, offset, filesz, vaddr))
    return out


def high_entropy_run(raw: bytes, segs, block=4096):
    """The one region in the working set that is not text."""
    best = None
    for flags, off, size, _ in segs:
        if not (flags & 2):
            continue
        n = size // block
        if n < 4:
            continue
        arr = np.frombuffer(raw[off:off + n * block], dtype=np.uint8).reshape(n, block)
        ent = np.empty(n)
        for i in range(n):
            cnt = np.bincount(arr[i], minlength=256).astype(np.float64)
            p = cnt / block
            p = p[p > 0]
            ent[i] = -(p * np.log2(p)).sum()
        hot = ent > 7.5
        i = 0
        while i < n:
            if hot[i]:
                j = i
                while j < n and hot[j]:
                    j += 1
                if best is None or (j - i) > best[1]:
                    best = (off + i * block, j - i)
                i = j
            else:
                i += 1
    assert best, "no ciphertext region found"
    return best


def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t0 = time.time()
    core = next(dist.glob("core.*"))
    raw = core.read_bytes()
    print(f"[00] {core.name}: {len(raw):,} B")

    segs = loads(raw)
    rwx = [s for s in segs if s[0] == 7]
    print(f"[01] {len(segs)} PT_LOAD, {len(rwx)} of them anonymous RWX")
    assert len(rwx) == 1
    blob = raw[rwx[0][1]:rwx[0][1] + rwx[0][2]]
    code = blob[:blob.rfind(b"\xc3") + 1]
    print(f"[02] scratch mapping {rwx[0][2]:,} B; emitted code {len(code)} B, "
          f"sha256 {hashlib.sha256(code).hexdigest()[:16]}")

    off, nblocks = high_entropy_run(raw, segs)
    print(f"[03] one high-entropy region in the working set at file offset "
          f"0x{off:x}, about {nblocks*4096:,} B -- ciphertext, already written")

    # The working set is 64-byte counter lines; the sealed records were written
    # over a stretch of them. The exact edges come from where the lines stop
    # and start again, not from the entropy window.
    mid = off + (nblocks * 4096) // 2
    i = raw.rfind(b"ENT ", max(0, off - 8192), mid)
    while i > 0 and raw[i + 64:i + 68] == b"ENT ":
        i += 64
    ct_start = i + 64
    j = raw.find(b"ENT ", mid)
    assert j > ct_start, "could not find where the counter lines resume"

    # the tail edge is fixed by the state, not by the text: one 16-byte block
    # in this window turns up a second time outside the working set
    ct_end = None
    for end in range(j, j - 64, -16):
        cand = raw[end - 16:end]
        if all(32 <= c < 127 for c in cand):
            continue                    # still inside the counter lines
        hits = []
        k = raw.find(cand)
        while k != -1:
            if not (ct_start - 4096 <= k < end):
                hits.append(k)
            k = raw.find(cand, k + 1)
        if hits:
            ct_end, where = end, hits
            break
    assert ct_end is not None, "could not find the state"
    # blocks are 16-byte aligned to that edge, so the head edge only has to be
    # early enough; the framing says where the log really starts
    ct_start = ct_end - 16 * ((ct_end - ct_start) // 16 + 8)
    ct = raw[ct_start:ct_end]
    p0, p1 = struct.unpack("<QQ", TRAILER)
    print(f"[04] {len(ct)//16} blocks up to 0x{ct_end:x}; the last block turns up "
          f"again at {', '.join('0x%x' % w for w in where)} -- registers at the "
          f"fault, and the state itself")

    # only one of those is the state: restore its rate from the trailer and see
    # whether the log comes back
    n = len(ct) // 16
    plain = st = None
    for state_at in where:
        d = list(struct.unpack_from("<5Q", raw, state_at))
        cur = [d[0] ^ p0, d[1] ^ p1, d[2], d[3], d[4]]
        out = [b""] * n
        for k in range(n - 1, -1, -1):
            ks = cur[0].to_bytes(8, "little") + cur[1].to_bytes(8, "little")
            out[k] = bytes(x ^ y for x, y in zip(ct[16 * k:16 * k + 16], ks))
            cur = iperm(cur)
        cand_plain = b"".join(out)
        if b"JRNL\x00\x00\x00\x00" in cand_plain:
            plain, dumped = cand_plain, d
            print(f"[05] the state is at file offset 0x{state_at:x}; its rate "
                  f"restored as ciphertext XOR the close-of-log trailer")
            break
    assert plain is not None, "no candidate state runs the permutation backwards"

    head = plain.find(b"JRNL\x00\x00\x00\x00")
    assert head % 16 == 0, "record zero is not block-aligned"
    plain = plain[head:]
    print(f"[06] permutation run backwards {n} blocks; record zero is "
          f"{head//16} blocks in, so the log is {len(plain)//16} blocks")

    # the per-record checksum, with the polynomial out of the emitted code
    ok = bad = 0
    p = 0
    while p + 16 <= len(plain) - 16:
        magic, seq, ln, crc = struct.unpack_from("<4sIII", plain, p)
        if magic != b"JRNL" or p + 16 + ln > len(plain):
            break
        body = plain[p + 16:p + 16 + ln]
        if crc32c(body) == crc:
            ok += 1
        else:
            bad += 1
        p += 16 + ln
    print(f"[07] record checksums: {ok} good, {bad} bad")
    assert ok > 100 and bad == 0

    flag = None
    for chunk in plain.split(b"\n"):
        if b"Null0rigin{" in chunk:
            s = chunk[chunk.index(b"Null0rigin{"):]
            flag = s[:s.index(b"}") + 1].decode()
            break
    assert flag, "no flag in the recovered journal"

    secret = b"".join(v.to_bytes(8, "big") for v in
                      [dumped[0] ^ p0, dumped[1] ^ p1, dumped[2], dumped[3], dumped[4]])
    box = (dist / "daybook.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    c = AES.new(hashlib.sha256(secret).digest(), AES.MODE_GCM, nonce=box[8:20])
    c.update(SLUG.encode())
    data = json.loads(c.decrypt_and_verify(box[20:-16], box[-16:]))
    assert data["flag"] == flag
    print(f"[08] share bytes for the meta = {secret.hex()}")
    print(f"[09] total {time.time()-t0:.1f}s")
    print(flag)
    assert flag.startswith("Null0rigin{") and flag.endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
