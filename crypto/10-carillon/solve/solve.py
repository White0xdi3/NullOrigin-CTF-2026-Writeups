#!/usr/bin/env python3
"""10-carillon -- solve.

Nothing in the shipped artifacts names a binary quadratic form, a class group,
or an infrastructure. Everything below is read off the two ledgers and the
daemon.

  1. Parse the container. Records are three signed integers plus three 64-bit
     fields. b^2-4ac is CONSTANT across each file -- the triples are forms.
     Its SIGN differs between the two files, and that is the whole stage.
  2. The three trailing fields are uniform until the daemon's bytecode is
     reversed: they are one 192-bit fixed-point accumulator XOR-folded with a
     keystream the machine derives from the record's own coefficients.
  3. ledger-R (D > 0): the accumulator is additive under composition, so
     seq(seal)/seq(genesis) = n. It is written with 56 significant bits, so
     that pins n only to a window of ~2^45.
  4. ledger-I (D < 0): a finite abelian group. quadclassunit gives h and the
     structure; Pohlig-Hellman on the genesis form gives n mod ord(genesis),
     about 2^48.4.
  5. One n satisfies both. The archive key is H(n || h_I || genesis form of
     chain I || D_R).

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
import cypari2
from Crypto.Cipher import AES

SLUG = "10-carillon"
M64 = (1 << 64) - 1


# --------------------------------------------------- what the bytecode does
def keystream(words: np.ndarray) -> np.ndarray:
    h = np.full(words.shape[0], 0x9E3779B97F4A7C15, dtype=np.uint64)
    m1 = np.uint64(0xFF51AFD7ED558CCD); m2 = np.uint64(0xC4CEB9FE1A85EC53)
    s33 = np.uint64(33); s29 = np.uint64(29); s32 = np.uint64(32)
    for k in range(words.shape[1]):
        h = (h ^ words[:, k]) * m1
        h ^= h >> s33
    out = np.empty((words.shape[0], 3), dtype=np.uint64)
    for j in (1, 2, 3):
        x = h ^ np.uint64(j)
        x ^= x >> s33
        x = x * m1
        x ^= x >> s29
        x = x * m2
        x ^= x >> s32
        out[:, j - 1] = x
    return out


class Ledger:
    def __init__(self, path: pathlib.Path):
        self.path = path
        with path.open("rb") as fh:
            hdr = fh.read(32)
        assert hdr[:4] == b"LDGR", f"{path.name}: not a ledger"
        self.cw = hdr[5]
        self.rec = struct.unpack("<H", hdr[6:8])[0]
        self.count = struct.unpack("<q", hdr[8:16])[0]
        self.mm = np.memmap(path, dtype=np.uint8, mode="r", offset=32,
                            shape=(self.count, self.rec))

    def coeffs(self, i: int):
        r = bytes(self.mm[i])
        cw = self.cw
        return tuple(int.from_bytes(r[k * cw:(k + 1) * cw], "little", signed=True)
                     for k in range(3))

    def seq(self, i: int) -> int:
        r = bytes(self.mm[i])
        nw = (3 * self.cw) // 8
        w = np.frombuffer(r[:8 * nw], dtype="<u8").reshape(1, nw)
        ks = keystream(np.ascontiguousarray(w))[0]
        o = 3 * self.cw
        f = [struct.unpack("<Q", r[o + 8 * k:o + 8 * k + 8])[0] ^ int(ks[k])
             for k in range(3)]
        return f[0] | (f[1] << 64) | (f[2] << 128)

    def disc(self, i: int) -> int:
        a, b, c = self.coeffs(i)
        return b * b - 4 * a * c


def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t0 = time.time()
    pari = cypari2.Pari(); pari.allocatemem(1 << 32, silent=True)

    LI = Ledger(dist / "ledger-I.dat")
    LR = Ledger(dist / "ledger-R.dat")
    print(f"[00] ledger-I: {LI.count:,} records, {LI.cw}-byte coefficients")
    print(f"[01] ledger-R: {LR.count:,} records, {LR.cw}-byte coefficients")

    # ---- 1. the discriminant is constant, and its sign is the stage --------
    probe = [0, 1, 2, 7, LI.count // 3, LI.count // 2, LI.count - 2]
    D_I = LI.disc(0); D_R = LR.disc(0)
    for i in probe:
        assert LI.disc(i) == D_I and LR.disc(i) == D_R, "discriminant not constant"
    print(f"[02] b^2-4ac constant on both files. D_I < 0: {D_I < 0} "
          f"({D_I.bit_length()} bits).  D_R > 0: {D_R > 0} ({D_R.bit_length()} bits)")
    assert D_I < 0 < D_R

    # ---- 2. the accumulator ------------------------------------------------
    sg_R = LR.seq(0)
    s2, s3 = LR.seq(1), LR.seq(2)
    print(f"[03] chain R accumulator: seq(0)={sg_R}, seq(1)/seq(0)={s2/sg_R:.6f}, "
          f"seq(2)/seq(0)={s3/sg_R:.6f}  -> additive")
    assert abs(s2 / sg_R - 2) < 1e-9 and abs(s3 / sg_R - 3) < 1e-9

    seal_R = LR.seq(LR.count - 1)
    # the genesis field is exact, so its width is the precision the whole
    # column was written at: everything wider than that is the accumulator's
    # own noise, which is what leaves a window instead of an answer.
    sig = sg_R.bit_length()
    shift = max(0, seal_R.bit_length() - sig)
    lo = max(0, seal_R - (1 << shift)) // sg_R
    hi = (seal_R + (1 << shift)) // sg_R + 1
    window = hi - lo
    print(f"[04] chain R alone: n in [{lo}, {hi}], width 2^{window.bit_length()-1}+ "
          f"-- {'not enough' if window > 1 else 'enough'}")
    assert window >= 2 ** 40

    # chain I's accumulator: the same field, and it says nothing
    sg_I, seal_I_seq = LI.seq(0), LI.seq(LI.count - 1)
    print(f"[05] chain I alone: seq(seal)/seq(genesis) = {seal_I_seq/sg_I:.3f} "
          f"-- the accumulator wrapped; no magnitude here")

    # ---- 3. chain I: the class group ---------------------------------------
    t = time.time()
    cu = pari.quadclassunit(D_I)
    h_I = int(cu[0]); struc = [int(x) for x in cu[1]]
    print(f"[06] quadclassunit(D_I): h = {h_I}, structure {struc} "
          f"({time.time()-t:.2f}s)")

    g = pari.Qfb(*LI.coeffs(0))
    tgt = pari.Qfb(*LI.coeffs(LI.count - 1))
    ident = pari.qfbpow(g, 0)
    M = struc[0]
    fac = pari.factor(M)
    pe = [(int(p), int(e)) for p, e in zip(fac[0], fac[1])]
    # order of the genesis form
    o = M
    for p, e in pe:
        for _ in range(e):
            if pari.qfbpow(g, o // p) == ident:
                o //= p
            else:
                break
    print(f"[07] ord(genesis) = {o} (2^{o.bit_length()-1}+)")

    def bsgs(base, target, order):
        m = int(order ** 0.5) + 1
        tab = {}
        cur = pari.qfbpow(base, 0)
        for j in range(m):
            tab.setdefault(str(cur), j)
            cur = pari.qfbcomp(cur, base)
        factor = pari.qfbpow(base, -m)
        y = target
        for i in range(m + 1):
            j = tab.get(str(y))
            if j is not None:
                return (i * m + j) % order
            y = pari.qfbcomp(y, factor)
        raise RuntimeError("no discrete log")

    t = time.time()
    res, mods = [], []
    for p, e in pe:
        q = p ** e
        if o % q:
            continue
        gq = pari.qfbpow(g, o // q)
        tq = pari.qfbpow(tgt, o // q)
        x = bsgs(gq, tq, q)
        res.append(x); mods.append(q)
    # CRT
    r, m = 0, 1
    for x, q in zip(res, mods):
        while r % q != x:
            r += m
        m *= q
    print(f"[08] Pohlig-Hellman: n = {r} mod {m} ({time.time()-t:.2f}s)")
    assert m == o

    # ---- 4. glue ------------------------------------------------------------
    first = lo + ((r - lo) % m)
    cands = list(range(first, hi + 1, m))
    print(f"[09] candidates satisfying both chains: {len(cands)}")
    assert len(cands) == 1, cands
    n = cands[0]
    print(f"[10] n = {n} ({n.bit_length()} bits)")

    # ---- 5. the key ---------------------------------------------------------
    gen_I = LI.coeffs(0)
    secret = (n.to_bytes(13, "big") + h_I.to_bytes(8, "big")
              + b"".join(int(v).to_bytes(16, "big", signed=True) for v in gen_I)
              + int(D_R).to_bytes(36, "big"))
    box = (dist / "carillon.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    c = AES.new(hashlib.sha256(secret).digest(), AES.MODE_GCM, nonce=box[8:20])
    c.update(SLUG.encode())
    data = json.loads(c.decrypt_and_verify(box[20:-16], box[-16:]))
    share = n.to_bytes(13, "big") + b"".join(
        int(v).to_bytes(16, "big", signed=True) for v in LI.coeffs(LI.count - 1))
    print(f"[11] share bytes for the meta = {share.hex()}")
    print(f"[12] total {time.time()-t0:.1f}s")
    print(data["flag"])
    assert data["flag"].startswith("Null0rigin{") and data["flag"].endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
