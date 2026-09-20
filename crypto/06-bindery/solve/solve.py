#!/usr/bin/env python3
"""06-bindery -- solve.

`bindery.o` is a relocatable with no entry point and four unresolved externs.
Stub the four undefined symbols and it links and runs, giving a local oracle; nothing shipped does that for you. Everything below is read out of it.

  1. The register is two 128-bit bit-planes (four 64-bit words in .rodata at
     offset 0x20) and a cell is one bit from each:
     (0,0), (1,0), (0,1). `cadd` is the carry-free identity on those planes,
     which is addition modulo three -- there is no 3 anywhere in the object,
     no reciprocal-multiply constant and no 1/3/9/27/81 ladder to recognise.
  2. `.rodata` holds the 121 multipliers as one bit-plane pair, and the 28
     fixed leading cells of every entry as another.
  3. `pack` writes an entry as ONE integer, cell 0 most significant, and the
     runtime then tops it up: the record is x + u*3^512 in 110 bytes, so the
     entry is x = y mod 3^512. That is the only place the base is stated.
  4. Six entries give 6*28 = 168 equations on the 121-cell seed over GF(3).
     Rank 121 is reached well before that; Gaussian elimination mod 3 in plain
     int64 numpy takes milliseconds.
  5. Rerun the register, subtract, and the index falls out.

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

SLUG = "06-bindery"
CELLS = 121
SPAN = 512
HDR = 28
WIDE = 110
BODY = SPAN - HDR
CHUNKB = 95
NCH = 16
POW3_SPAN = 3 ** SPAN
POW3_32 = 3 ** 32
PW32 = np.array([3 ** (31 - i) for i in range(32)], dtype=np.int64)


# ------------------------------------------------------------------- the .o
def rodata(path: pathlib.Path) -> bytes:
    b = path.read_bytes()
    shoff = struct.unpack_from("<Q", b, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", b, 0x3A)
    def sh(i):
        o = shoff + i * shentsize
        name, typ, flags, addr, off, size = struct.unpack_from("<IIQQQQ", b, o)
        return name, off, size
    _, stroff, _ = sh(shstrndx)
    for i in range(shnum):
        name, off, size = sh(i)
        end = b.index(b"\0", stroff + name)
        if b[stroff + name:end] == b".rodata":
            return b[off:off + size]
    raise RuntimeError("no .rodata in the object")


def constants(rd: bytes):
    """Two 32-bit words then, on its own 32-byte boundary, four 64-bit words."""
    a, bq = struct.unpack_from("<II", rd, 0)
    taps = struct.unpack_from("<QQQQ", rd, 32)
    c = np.zeros(CELLS, dtype=np.int64)
    for i in range(CELLS):
        w, bit = i >> 6, i & 63
        if (taps[w] >> bit) & 1:
            c[i] = 1
        elif (taps[2 + w] >> bit) & 1:
            c[i] = 2
    return c, a, bq


def stamp_from(lo: int, hi: int) -> np.ndarray:
    s = np.zeros(HDR, dtype=np.int64)
    for i in range(HDR):
        if (lo >> i) & 1:
            s[i] = 1
        elif (hi >> i) & 1:
            s[i] = 2
    return s


# ------------------------------------------------------------- the register
def matrix(c):
    M = np.zeros((CELLS, CELLS), dtype=np.int64)
    for j in range(CELLS - 1):
        M[j, j + 1] = 1
    M[CELLS - 1, :] = c
    return M


def matpow(M, e):
    R = np.eye(CELLS, dtype=np.int64)
    B = M % 3
    while e:
        if e & 1:
            R = (R @ B) % 3
        B = (B @ B) % 3
        e >>= 1
    return R


def rows(c, upto: int) -> np.ndarray:
    """row 0 of M^n for n = 0 .. upto-1: the linear form giving cell n."""
    out = np.zeros((upto, CELLS), dtype=np.int64)
    r = np.zeros(CELLS, dtype=np.int64)
    r[0] = 1
    for n in range(upto):
        out[n] = r
        nr = np.zeros(CELLS, dtype=np.int64)
        nr[1:] = r[:-1]
        nr = (nr + r[CELLS - 1] * c) % 3
        r = nr
    return out


def solve_mod3(Arows: np.ndarray, rhs: np.ndarray):
    A = np.concatenate([Arows % 3, (rhs % 3).reshape(-1, 1)], axis=1)
    m, n = A.shape[0], CELLS
    piv = []
    r = 0
    for col in range(n):
        nz = np.nonzero(A[r:, col])[0]
        if nz.size == 0:
            continue
        i = r + int(nz[0])
        if i != r:
            A[[r, i]] = A[[i, r]]
        inv = 1 if A[r, col] == 1 else 2
        A[r] = (A[r] * inv) % 3
        for k in range(m):
            if k != r and A[k, col]:
                A[k] = (A[k] - A[k, col] * A[r]) % 3
        piv.append(col)
        r += 1
        if r == n:
            break
    if len(piv) != n:
        return None, len(piv)
    x = np.zeros(n, dtype=np.int64)
    for i, col in enumerate(piv):
        x[col] = A[i, n]
    return x, n


def keystream(M, s0, nblocks: int) -> np.ndarray:
    m = 1024
    T = matpow(M, CELLS).astype(np.float64)
    panel = np.empty((CELLS, m), dtype=np.float64)
    panel[:, 0] = s0
    for k in range(1, m):
        panel[:, k] = (T @ panel[:, k - 1]) % 3
    Tm = matpow(matpow(M, CELLS), m).astype(np.float64)
    out = np.empty((nblocks, CELLS), dtype=np.int8)
    done = 0
    while done < nblocks:
        k = min(m, nblocks - done)
        out[done:done + k] = panel[:, :k].T.astype(np.int8)
        done += k
        if done < nblocks:
            panel = (Tm @ panel) % 3
    return out


def cells_of(raw: bytes, lo: int, n: int) -> np.ndarray:
    """records lo .. lo+n-1 -> (n, 512) int8 cells, cell 0 most significant."""
    ch = np.empty((n, NCH), dtype=np.int64)
    for i in range(n):
        y = int.from_bytes(raw[(lo + i) * WIDE:(lo + i + 1) * WIDE], "big")
        v = y % POW3_SPAN
        for k in range(NCH - 1, -1, -1):
            v, r = divmod(v, POW3_32)
            ch[i, k] = r
    out = np.empty((n, NCH, 32), dtype=np.int8)
    t = ch.copy()
    for p in range(31, -1, -1):
        out[:, :, p] = (t % 3).astype(np.int8)
        t //= 3
    return out.reshape(n, SPAN)


def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t0 = time.time()
    rd = rodata(dist / "bindery.o")
    c, w0, w1 = constants(rd)
    nz = int((c != 0).sum())
    print(f"[00] .rodata: {len(rd)} B -> 121 multipliers ({nz} non-zero), "
          f"two 32-bit stamp planes")

    raw = (dist / "index.sealed").read_bytes()
    nrec = len(raw) // WIDE
    print(f"[01] index.sealed {len(raw):,} B / 110 = {nrec:,} fixed-width entries")

    t = time.time()
    NP = 6
    cells = cells_of(raw, 0, NP)
    print(f"[02] first {NP} entries decoded: x = y mod 3^512, then base 3 "
          f"({time.time()-t:.2f}s)")

    R = rows(c, (NP - 1) * SPAN + HDR)
    for lo, hi in ((w0, w1), (w1, w0)):
        stamp = stamp_from(lo, hi)
        A, rhs = [], []
        for rec in range(NP):
            for j in range(HDR):
                A.append(R[rec * SPAN + j])
                rhs.append((int(cells[rec, j]) - int(stamp[j])) % 3)
        s0, rank = solve_mod3(np.array(A), np.array(rhs))
        if s0 is None:
            print(f"[03] stamp planes the other way: rank {rank} of 121")
            continue
        # held-out check: the 28 stamp cells of an entry we did not use
        chk = cells_of(raw, NP + 3, 1)[0]
        n0 = (NP + 3) * SPAN
        Rk = rows(c, n0 + HDR)[n0:n0 + HDR]
        pred = (Rk @ s0) % 3
        got = (chk[:HDR].astype(np.int64) - pred) % 3
        if np.array_equal(got, stamp % 3):
            print(f"[03] {NP*HDR} equations, rank {rank} of 121, and the seed "
                  f"predicts the stamp of an entry it never saw")
            break
        print("[03] rank reached but the held-out stamp disagrees; "
              "trying the other plane order")
    else:
        raise SystemExit("could not pin the seed")

    print(f"[04] seed = {''.join(str(int(v)) for v in s0[:40])}... "
          f"({CELLS} cells)")

    t = time.time()
    ks = keystream(matrix(c), s0, (nrec * SPAN) // CELLS + 2
                   ).reshape(-1)[:nrec * SPAN].reshape(nrec, SPAN)
    print(f"[05] register rerun, {nrec*SPAN:,} cells ({time.time()-t:.1f}s)")

    t = time.time()
    text = bytearray()
    BATCH = 8192
    for base in range(0, nrec, BATCH):
        k = min(BATCH, nrec - base)
        cc = cells_of(raw, base, k)
        plain = (cc - ks[base:base + k]) % 3
        assert np.array_equal(plain[0, :HDR], plain[k - 1, :HDR])
        body = plain[:, HDR:].astype(np.int64)
        for j in range(k):
            x = 0
            for p in range(0, BODY, 32):
                seg = body[j, p:p + 32]
                x = x * (3 ** seg.size) + int((seg * PW32[-seg.size:]).sum())
            text += x.to_bytes(CHUNKB, "big")
    print(f"[06] index recovered, {len(text):,} B ({time.time()-t:.1f}s)")

    head = bytes(text[:400]).decode("ascii", "replace")
    flag = [ln for ln in head.split("\n") if ln.startswith("Null0rigin{")][0]

    secret = bytes(int(v) for v in s0)
    box = (dist / "bindery.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    cph = AES.new(hashlib.sha256(secret).digest(), AES.MODE_GCM, nonce=box[8:20])
    cph.update(SLUG.encode())
    data = json.loads(cph.decrypt_and_verify(box[20:-16], box[-16:]))
    assert data["flag"] == flag

    share_x = 0
    for i in range(CELLS - 1, -1, -1):
        share_x = share_x * 3 + int(s0[i])
    share = share_x.to_bytes(24, "big")
    print(f"[07] share bytes for the meta = {share.hex()}")
    print(f"[08] total {time.time()-t0:.1f}s")
    print(flag)
    assert flag.startswith("Null0rigin{") and flag.endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
