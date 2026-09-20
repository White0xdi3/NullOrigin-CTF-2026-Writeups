#!/usr/bin/env python3
"""09-catalogue -- solve.

What the DLL gives up (no key in the lot, so nothing in it runs):

    point_of(acc) = ((acc*0x0F4243 + 0x0A95B7) mod 10^12) * 0x03D091
                    + 0x02C1A3   mod 10^12
    halves        19 and 21 bits, addition modulo the half, three rounds:
                    R1 = L0 + F1[R0]  (mod 2^19)
                    L3 = R0 + F2[R1]  (mod 2^21)
                    R3 = R1 + F3[L3]  (mod 2^19)
                  packed out as  R3 * 2^21 + L3, cycle-walked while >= 10^12
    HELDBACK      0x3ADE68B1, never issued

The unbalanced shape is the lever. Eliminating R1 between rounds 1 and 3:

    R3 - L0 = F1[R0] + F3[L3]   (mod 2^19)

which does not mention F2 at all. Every index record is one equation on the
bipartite graph (R0, L3); the graph has average degree 24 and is connected, so
F1 and F3 fall out by propagation from a single free choice -- the translation
gauge, which cancels in the cipher.

~9% of the records went round the cycle-walk twice and are not Feistel pairs.
A first-write-wins fill therefore lands about 40% of both tables wrong. The
repair is the whole trick: if F1[r] is wrong by delta, every honest record
touching r has residual exactly delta, so the per-entry mode of the residual
IS the correction. Two or three rounds of that reach the poisoning floor with
zero wrong entries, and then F2 comes out of one more vote.

Run:  python3 solve/solve.py [dist_dir]
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

import numpy as np
from Crypto.Cipher import AES

SLUG = "09-catalogue"
LW, RW = 19, 21
A, B = 1 << LW, 1 << RW
DOM = 1_000_000_000_000
K1, K2, K3, K4 = 0x0F4243, 0x0A95B7, 0x03D091, 0x02C1A3
HELDBACK = 0x3ADE68B1
REC = 40


def point_of(acc):
    return ((acc * K1 + K2) % DOM * K3 + K4) % DOM


def read_index(path: pathlib.Path):
    """Two 32-bit columns and one 64-bit column out of a 40-byte record,
    streamed: the file is 2 GB and only three of its ten fields matter."""
    size = path.stat().st_size
    count = (size - 32) // REC
    L0 = np.empty(count, np.int32); R0 = np.empty(count, np.int32)
    L3 = np.empty(count, np.int32); Z = np.empty(count, np.int32)
    step = 1 << 21
    with path.open("rb") as fh:
        assert fh.read(4) == b"SHLF"
        fh.seek(32)
        done = 0
        while done < count:
            k = min(step, count - done)
            blk = np.frombuffer(fh.read(k * REC), dtype=np.uint32).reshape(k, REC // 4)
            acc = blk[:, 0].astype(np.int64)
            sm = blk[:, 1].astype(np.int64) | (blk[:, 2].astype(np.int64) << 32)
            x = point_of(acc)
            L0[done:done + k] = (x >> RW).astype(np.int32)
            R0[done:done + k] = (x & (B - 1)).astype(np.int32)
            L3[done:done + k] = (sm & (B - 1)).astype(np.int32)
            Z[done:done + k] = (((sm >> RW) - (x >> RW)) % A).astype(np.int32)
            done += k
    return L0, R0, L3, Z


def quick(ent, val, size, trials=6):
    """Per-entry modal value, by sampling one record per entry several ways
    and counting agreement. Cheap; exact enough while errors are common."""
    best = np.full(size, -1, np.int64); bestc = np.zeros(size, np.int64)
    for k in range(trials):
        cand = np.full(size, -1, np.int64)
        sl = slice(None, None, 1) if k == 0 else (
            slice(None, None, -1) if k == 1 else slice(k - 2, None, 5))
        cand[ent[sl]] = val[sl]
        cnt = np.bincount(ent[cand[ent] == val], minlength=size)
        up = cnt > bestc
        best[up] = cand[up]; bestc[up] = cnt[up]
    return best, bestc


def exact_mode(ent, val, size, flag, mod):
    """True per-entry mode, restricted to the flagged entries."""
    sel = flag[ent]
    out = np.zeros(size, np.int64); cnt = np.zeros(size, np.int64)
    if not sel.any():
        return out, cnt
    key = ent[sel].astype(np.int64) * mod + val[sel].astype(np.int64)
    u, c = np.unique(key, return_counts=True)
    e = u // mod; v = u % mod
    order = np.lexsort((-c, e)); e = e[order]; v = v[order]; c = c[order]
    first = np.ones(e.size, bool); first[1:] = e[1:] != e[:-1]
    out[e[first]] = v[first]; cnt[e[first]] = c[first]
    return out, cnt


def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t0 = time.time()
    idx = dist / "shelf.idx"
    print(f"[00] shelf.idx = {idx.stat().st_size:,} B")
    t = time.time()
    L0, R0, L3, Z = read_index(idx)
    print(f"[01] {L0.size:,} pairs decoded to (L0, R0, L3, R3-L0) ({time.time()-t:.0f}s)")

    tot1 = np.bincount(R0, minlength=B)
    tot3 = np.bincount(L3, minlength=B)
    print(f"[02] records per F1 entry: min {tot1.min()} mean {tot1.mean():.1f}; "
          f"per F3 entry: min {tot3.min()} mean {tot3.mean():.1f}")

    # ---- propagate ---------------------------------------------------------
    t = time.time()
    G1 = np.full(B, -1, np.int64); G3 = np.full(B, -1, np.int64)
    G1[0] = 0                                   # the translation gauge
    for it in range(80):
        ch = False
        m = (G1[R0] >= 0) & (G3[L3] < 0)
        if m.any():
            G3[L3[m]] = (Z[m] - G1[R0[m]]) % A; ch = True
        m = (G3[L3] >= 0) & (G1[R0] < 0)
        if m.any():
            G1[R0[m]] = (Z[m] - G3[L3[m]]) % A; ch = True
        if not ch:
            break
    res = (Z - G1[R0] - G3[L3]) % A
    print(f"[03] first-write-wins fill: F1 {int((G1>=0).sum())}/{B}, "
          f"F3 {int((G3>=0).sum())}/{B}, residual {float((res!=0).mean())*100:.1f}% "
          f"-- most of that is wrong tables, not poisoning ({time.time()-t:.0f}s)")

    # ---- repair -------------------------------------------------------------
    t = time.time()
    for rep in range(14):
        res = ((Z - G1[R0] - G3[L3]) % A).astype(np.int64)
        frac = float((res != 0).mean())
        if frac < 0.10:
            bad1 = np.bincount(R0, weights=(res != 0).astype(np.float64), minlength=B)
            bad3 = np.bincount(L3, weights=(res != 0).astype(np.float64), minlength=B)
            s1 = bad1 > 0.5 * np.maximum(tot1, 1)
            s3 = bad3 > 0.5 * np.maximum(tot3, 1)
            if not (s1.any() or s3.any()):
                break
            before = (G1.copy(), G3.copy())
            dl, c = exact_mode(R0, res, B, s1, A); G1 = (G1 + np.where(c >= 2, dl, 0)) % A
            res = ((Z - G1[R0] - G3[L3]) % A).astype(np.int64)
            dl, c = exact_mode(L3, res, B, s3, A); G3 = (G3 + np.where(c >= 2, dl, 0)) % A
            if np.array_equal(before[0], G1) and np.array_equal(before[1], G3):
                break
        else:
            dl, c = quick(R0, res, B); G1 = (G1 + np.where(c >= 2, dl, 0)) % A
            res = ((Z - G1[R0] - G3[L3]) % A).astype(np.int64)
            dl, c = quick(L3, res, B); G3 = (G3 + np.where(c >= 2, dl, 0)) % A
        print(f"     repair {rep}: residual {frac*100:.3f}%")
    res = (Z - G1[R0] - G3[L3]) % A
    floor = float((res != 0).mean())
    print(f"[04] residual {floor*100:.2f}% -- the cycle-walk poisoning rate, so F1 and "
          f"F3 are exact up to the gauge ({time.time()-t:.0f}s)")
    assert 0.06 < floor < 0.12

    # ---- F2 ------------------------------------------------------------------
    t = time.time()
    R1 = ((L0.astype(np.int64) + G1[R0]) % A).astype(np.int32)
    V2 = ((L3.astype(np.int64) - R0) % B).astype(np.int64)
    G2, _ = quick(R1, V2, A)
    totr = np.bincount(R1, minlength=A)
    agree = np.bincount(R1, weights=(G2[R1] == V2).astype(np.float64), minlength=A)
    s = agree <= 0.5 * np.maximum(totr, 1)
    if s.any():
        dl, cc = exact_mode(R1, V2, A, s, B)
        G2 = np.where(cc >= 1, dl, G2)
    assert int((G2 < 0).sum()) == 0, "F2 incomplete"
    print(f"[05] F2 filled, {int(s.sum())} entries needed an exact vote "
          f"({time.time()-t:.0f}s)")
    del L0, R0, L3, Z, R1, V2

    # ---- the held-back accession number ---------------------------------------
    def issue(y: int) -> int:
        for _ in range(64):
            l0 = y >> RW; r0 = y & (B - 1)
            r1 = (l0 + int(G1[r0])) % A
            l3 = (r0 + int(G2[r1])) % B
            r3 = (r1 + int(G3[l3])) % A
            y = r3 * B + l3
            if y < DOM:
                return y
        raise RuntimeError("cycle-walk did not terminate")

    mark = issue(int(point_of(HELDBACK)))
    secret = f"{mark:014d}".encode()
    print(f"[06] binding copy shelfmark = {secret.decode()}")

    box = (dist / "catalogue.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    c = AES.new(hashlib.sha256(secret).digest(), AES.MODE_GCM, nonce=box[8:20])
    c.update(SLUG.encode())
    data = json.loads(c.decrypt_and_verify(box[20:-16], box[-16:]))
    print(f"[07] share bytes for the meta = {secret.hex()}")
    print(f"[08] total {time.time()-t0:.0f}s")
    print(data["flag"])
    assert data["flag"].startswith("Null0rigin{") and data["flag"].endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
