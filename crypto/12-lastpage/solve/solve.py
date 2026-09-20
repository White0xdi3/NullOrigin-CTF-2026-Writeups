#!/usr/bin/env python3
"""12-lastpage -- solve.

The jar's security note is true and irrelevant.  Recovering the rank
decomposition of a 3-tensor is NP-hard in the worst case; this instance is not
a worst case.  With R = n and A, B, C invertible the decomposition is unique by
Kruskal (2n + 2 <= 3n) and computable in polynomial time by Jennrich's
simultaneous diagonalisation:

    M(w) = sum_k w_k T[:,:,k] = A diag(C^T w) B^T
    M(w1) M(w2)^-1            = A diag(d1/d2) A^-1

so the columns of A are the eigenvectors of a pencil.  Over F_p the pencil's
characteristic polynomial splits completely -- probability ~1/n! for a random
matrix, which is the only structural tell left once the unfolding is full rank.

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

try:
    import cypari2
except ImportError:  # pragma: no cover
    sys.exit("cypari2 required (PARI factormod over F_p)")

SLUG = "12-lastpage"
HDR = struct.Struct("<4sIIIIQI")
IDX = struct.Struct("<QQ")


# --------------------------------------------------------------- F_p toolkit
def mm(X, Y, p):
    return ((X.astype(np.float64) @ Y.astype(np.float64)) % p).astype(np.int64)


def mv(X, y, p):
    return ((X.astype(np.float64) @ y.astype(np.float64)) % p).astype(np.int64)


def inv_elem(a, p):
    return pow(int(a) % p, p - 2, p)


def rref(M, p):
    M = np.array(M, dtype=np.int64) % p
    rows, cols = M.shape
    piv, r = [], 0
    for c in range(cols):
        if r == rows:
            break
        nz = np.nonzero(M[r:, c])[0]
        if nz.size == 0:
            continue
        i = r + int(nz[0])
        if i != r:
            M[[r, i]] = M[[i, r]]
        M[r, c:] = M[r, c:] * inv_elem(M[r, c], p) % p
        col = M[:, c].copy()
        col[r] = 0
        nzr = np.nonzero(col)[0]
        if nzr.size:
            M[nzr, c:] = (M[nzr, c:] - col[nzr, None] * M[r, c:]) % p
        piv.append(c)
        r += 1
    return M, piv


def nullspace(M, p):
    R, piv = rref(M, p)
    pivset = set(piv)
    free = [c for c in range(M.shape[1]) if c not in pivset]
    out = np.zeros((M.shape[1], len(free)), dtype=np.int64)
    for j, f in enumerate(free):
        out[f, j] = 1
        for i, c in enumerate(piv):
            out[c, j] = (-R[i, f]) % p
    return out


def inverse(M, p):
    n = M.shape[0]
    aug = np.concatenate([np.array(M, dtype=np.int64) % p, np.eye(n, dtype=np.int64)], 1)
    R, piv = rref(aug, p)
    if piv != list(range(n)):
        raise ValueError("singular")
    return R[:, n:]


# ------------------------------------------------------------------ container
def load_tensor(path: pathlib.Path):
    raw = np.memmap(path, dtype=np.uint8, mode="r")
    magic, ver, p, n, per, recs, ioff = HDR.unpack(bytes(raw[:32]))
    if magic != b"LPRC":
        raise SystemExit("not a records container")
    print(f"[00] container: p={p} n={n} per_record={per} records={recs}")
    flat = np.empty(n * n * n, dtype=np.int64)
    idx = np.frombuffer(bytes(raw[ioff:ioff + recs * 16]), dtype="<u8").reshape(recs, 2)
    for off, start in idx:
        off, start = int(off), int(start)
        chunk = np.frombuffer(bytes(raw[off:off + per * 4]), dtype="<u4")
        flat[start:start + per] = chunk
    del raw
    return p, n, flat.reshape(n, n, n)          # T[i, j, k], k fastest


# ----------------------------------------------------------------------- main
def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t_all = time.time()
    p, n, T = load_tensor(dist / "records.bin")
    pari = cypari2.Pari()
    pari.allocatemem(1 << 30, silent=True)

    # ---- 1. the probe everybody runs: mode-1 unfolding rank ---------------
    t = time.time()
    rng = np.random.default_rng(0xA11CE)
    cols = rng.choice(n * n, size=2 * n, replace=False)
    jj, kk = np.divmod(cols, n)
    sub = np.stack([T[:, int(j), int(k)] for j, k in zip(jj, kk)], axis=1)
    r1 = len(rref(sub, p)[1])
    print(f"[01] mode-1 unfolding rank = {r1} of {n} -- FULL, no low-rank tell "
          f"({time.time()-t:.1f}s)")

    Tf = T.reshape(n * n, n)
    I = np.eye(n, dtype=np.int64)
    for attempt in range(8):
        w1 = rng.integers(1, p, n, dtype=np.int64)
        w2 = rng.integers(1, p, n, dtype=np.int64)
        t = time.time()
        M1 = mv(Tf, w1, p).reshape(n, n)
        M2 = mv(Tf, w2, p).reshape(n, n)
        G = mm(M1, inverse(M2, p), p)
        print(f"[02] pencil G = M(w1) M(w2)^-1 built ({time.time()-t:.1f}s)")

        # charpoly of G via a Krylov minimal polynomial: n matvecs + one nullspace
        t = time.time()
        v = rng.integers(0, p, n, dtype=np.int64)
        K = np.empty((n, n + 1), dtype=np.int64)
        K[:, 0] = v
        for i in range(1, n + 1):
            K[:, i] = mv(G, K[:, i - 1], p)
        ns = nullspace(K, p)
        coeffs = ns[:, 0]
        deg = max(i for i in range(n + 1) if int(coeffs[i]) % p)
        print(f"[03] charpoly via Krylov, degree {deg} ({time.time()-t:.1f}s)")
        if deg != n:
            continue
        pol = pari.Pol([int(c) for c in coeffs[deg::-1]]) * pari(f"Mod(1,{p})")
        fa = pari.factor(pol)
        degs = [int(pari.poldegree(f)) for f in fa[0]]
        exps = [int(e) for e in fa[1]]
        print(f"[04] factors over F_{p}: {len(degs)} of them, "
              f"max degree {max(degs)}, max multiplicity {max(exps)}")
        if len(degs) == n and max(degs) == 1 and max(exps) == 1:
            roots = [(-int(pari.polcoef(f, 0).lift())) % p for f in fa[0]]
            break
        print("[04] pencil degenerate for this (w1,w2) -- redraw")
    else:
        raise SystemExit("pencil never split; this is not the intended instance")
    assert len(set(roots)) == n

    t = time.time()
    A = np.empty((n, n), dtype=np.int64)
    for r, lam in enumerate(roots):
        ker = nullspace((G - lam * I) % p, p)
        assert ker.shape[1] == 1, f"eigenspace {r} has dimension {ker.shape[1]}"
        A[:, r] = ker[:, 0]
    print(f"[05] {n} eigenvectors -> A ({time.time()-t:.1f}s)")

    t = time.time()
    Ainv = inverse(A, p)
    S0 = mm(Ainv, T[:, :, 0], p)                 # row r = C[0,r] * b_r
    B = np.empty((n, n), dtype=np.int64)
    piv = np.empty(n, dtype=np.int64)
    for r in range(n):
        row = S0[r]
        j = int(np.nonzero(row)[0][0])
        piv[r] = j
        B[:, r] = row * inv_elem(row[j], p) % p
    C = np.empty((n, n), dtype=np.int64)
    for k in range(n):
        Sk = mm(Ainv, T[:, :, k], p)
        C[k, :] = [int(Sk[r, piv[r]]) for r in range(n)]
    print(f"[06] B and C by two linear solves ({time.time()-t:.1f}s)")

    for k in (0, 1, n // 2, n - 1):
        assert np.array_equal(mm((A * C[k, :]) % p, B.T, p), T[:, :, k]), "reconstruction failed"
    print("[07] reconstruction verified on 4 slices")

    # ---- canonical order fixed by the jar resource ------------------------
    A, B, C = A % p, B % p, C % p
    for r in range(n):
        i = int(np.nonzero(A[:, r])[0][0]); a0 = int(A[i, r])
        A[:, r] = A[:, r] * inv_elem(a0, p) % p
        C[:, r] = C[:, r] * a0 % p
        j = int(np.nonzero(B[:, r])[0][0]); b0 = int(B[j, r])
        B[:, r] = B[:, r] * inv_elem(b0, p) % p
        C[:, r] = C[:, r] * b0 % p
    order = sorted(range(n), key=lambda r: (A[:, r].tobytes(), B[:, r].tobytes(),
                                            C[:, r].tobytes()))
    A, B, C = A[:, order], B[:, order], C[:, order]
    blob = b"".join(m[:, r].astype("<u4").tobytes()
                    for m in (A, B, C) for r in range(n))
    secret = hashlib.sha256(blob).digest()
    print(f"[08] canonical factor digest = {secret.hex()}")

    box = (dist / "lastpage.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    c = AES.new(hashlib.sha256(secret).digest(), AES.MODE_GCM, nonce=box[8:20])
    c.update(SLUG.encode())
    data = json.loads(c.decrypt_and_verify(box[20:-16], box[-16:]))
    print(f"[09] total {time.time()-t_all:.1f}s")
    print(data["flag"])
    assert data["flag"].startswith("Null0rigin{") and data["flag"].endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
