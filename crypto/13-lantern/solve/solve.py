#!/usr/bin/env python3
"""13-lantern -- solve. The meta.

This stage is keyed by seven NON-FLAG quantities, one internal secret per
prior stage. Seven flags open nothing here. Each secret has to be recovered in
the canonical form that stage's own artifact fixes -- and five of the seven are
ambiguous as recovered, with only the artifact deciding:

  I    the register seed's digit order (the framing fixes cell 0)
  II   the sponge state BEFORE the rate lanes were staged over, not the dumped one
  III  the generator matrix's column order and bit order (the wire decides both)
  IV   the held-back shelfmark's field width
  VI   the flip set or its scrambled complement (the unrank routine decides)

So this script re-runs the seven solves against the seven built artifacts and
takes the canonical bytes each one prints. There is no shortcut: the shares are
not in any file.

    share_i = first 8 bytes of SHA-256(canonical bytes of secret i)

notebooks.txt publishes a 64-bit tweak under each spine, and share_i + t_i is
the value at x = i of a degree-6 polynomial over Z/2^64. That is a RING, not a
field: Lagrange divides by the differences 1..6, and 2, 4 and 6 are not
invertible. Shamir libraries throw here, or return nonsense, and they are
right. v_2(det Vandermonde(1..7)) = 12 exactly, so f(0) comes back only modulo
2^52 and the last 12 bits are 4096 candidates against the GCM tag. That is the
only brute force on this board and it is bounded.

Run:  python3 solve/solve.py [dist_dir]
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

from Crypto.Cipher import AES

SLUG = "13-lantern"
M = 1 << 64
CHAIN = pathlib.Path(__file__).resolve().parent.parent.parent

STAGES = [
    ("I",    "06-bindery",   r"share bytes for the meta = ([0-9a-f]+)"),
    ("II",   "07-daybook",   r"share bytes for the meta = ([0-9a-f]+)"),
    ("III",  "08-errata",    r"share bytes for the meta = ([0-9a-f]+)"),
    ("IV",   "09-catalogue", r"share bytes for the meta = ([0-9a-f]+)"),
    ("V",    "10-carillon",  r"share bytes for the meta = ([0-9a-f]+)"),
    ("VI",   "11-cartouche", r"combinatorial rank = ([0-9a-f]+)"),
    ("VII",  "12-lastpage",  r"canonical factor digest = ([0-9a-f]+)"),
]


def vander(n=7):
    return [[pow(i, k) for k in range(n)] for i in range(1, n + 1)]


def det_int(m):
    n = len(m)
    if n == 1:
        return m[0][0]
    return sum((-1) ** j * m[0][j]
               * det_int([r[:j] + r[j + 1:] for r in m[1:]]) for j in range(n))


def cofactors_col0(V):
    return [(-1) ** i * det_int([r[1:] for k, r in enumerate(V) if k != i])
            for i in range(len(V))]


def v2(x: int) -> int:
    k = 0
    while x % 2 == 0:
        x //= 2
        k += 1
    return k


def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t0 = time.time()

    # ---- the seven internal secrets -------------------------------------
    canon = []
    for numeral, slug, pat in STAGES:
        t = time.time()
        # Each prior stage's solve takes its own dist dir. Pass the sibling of
        # OUR dist, so the meta validates against the same tree the player has
        # (SHIP/<slug>) rather than an author-side copy that may not exist.
        argv = [sys.executable, str(CHAIN / slug / "solve" / "solve.py")]
        sibling = dist.parent / slug
        if sibling.is_dir():
            argv.append(str(sibling))
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout + r.stderr)
            raise SystemExit(f"{slug} did not solve")
        m = re.search(pat, r.stdout)
        assert m, f"{slug}: no canonical share in its output"
        b = bytes.fromhex(m.group(1))
        canon.append(b)
        print(f"[0{len(canon)}] {numeral:<4} {slug:<13} {len(b):>3} B  "
              f"{b.hex()[:24]}...  ({time.time()-t:.0f}s)")
    assert not any(b"Null0rigin" in c for c in canon), "a flag reached the meta"

    shares = [int.from_bytes(hashlib.sha256(c).digest()[:8], "big") for c in canon]

    # ---- her shelf annotations -------------------------------------------
    nb = (dist / "notebooks.txt").read_text()
    tweaks = [int(x, 16) for x in re.findall(r"^\s+([0-9a-f]{16})\s*$", nb, re.M)]
    assert len(tweaks) == 7, f"expected seven tweaks, found {len(tweaks)}"
    y = [(shares[i] + tweaks[i]) % M for i in range(7)]
    print(f"[08] seven shares, seven tweaks; the values at x = 1..7 of a "
          f"degree-6 polynomial")

    # ---- Z/2^64 is a ring ------------------------------------------------
    V = vander()
    det = det_int(V)
    e = v2(det)
    print(f"[09] det Vandermonde(1..7) = {det} = 2^{e} * {det >> e}; "
          f"2, 4 and 6 are not invertible mod 2^64, so Lagrange does not close")
    assert e == 12
    C = cofactors_col0(V)
    N = sum(yi * ci for yi, ci in zip(y, C)) % M
    assert N % (1 << e) == 0, "the share vector is not in the image -- a share is wrong"
    mod = 1 << (64 - e)
    base = (N >> e) * pow((det >> e) % mod, -1, mod) % mod
    print(f"[10] f(0) = 0x{base:013x} mod 2^{64-e}; {M//mod} candidates for the "
          f"top {e} bits")

    box = (dist / "lantern.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    nonce, head, tag = box[8:20], box[20:36], box[-16:]
    want = b'{\n "flag"'
    t = time.time()
    seed = None
    for k in range(M // mod):
        cand = (base + k * mod).to_bytes(8, "big")
        c = AES.new(hashlib.sha256(cand).digest(), AES.MODE_GCM, nonce=nonce)
        c.update(SLUG.encode())
        if c.decrypt(head).startswith(want):
            seed = cand
            print(f"[11] candidate {k} of {M//mod} decrypts the first block "
                  f"({time.time()-t:.2f}s)")
            break
    assert seed is not None, "no candidate opened the archive"

    c = AES.new(hashlib.sha256(seed).digest(), AES.MODE_GCM, nonce=nonce)
    c.update(SLUG.encode())
    data = json.loads(c.decrypt_and_verify(box[20:-16], tag))
    print(f"[12] GCM tag verifies over {len(box):,} B; the proof is {len(data['proof']):,} B")
    print(f"[13] total {time.time()-t0:.0f}s")
    print(data["flag"])
    assert data["flag"].startswith("Null0rigin{") and data["flag"].endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
