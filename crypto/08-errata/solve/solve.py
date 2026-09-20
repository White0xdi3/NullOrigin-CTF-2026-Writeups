#!/usr/bin/env python3
"""08-errata -- solve.

No header, no protocol doc, no firmware. Everything below is read off the
capture.

  1. Channel map and bus phase: try all four (CPOL, CPHA), score by odd-parity success over 9-bit
     LSB-first words. Measured {40/40, 40/40, 0/40, 0/40}: bimodal, but only
     TWO distinct outcomes exist -- the decoder separates rising-edge from
     falling-edge sampling, so two of the four labels are cosmetic duplicates
     that decode byte-for-byte identically. gen.py builds CPOL=1/CPHA=1; the
     solver's tie-break reports CPOL=0/CPHA=0. Same bits either way.
  2. Group frames by (type, length). 1,467 heartbeat frames share a
     byte-identical 64-byte trailer while their ciphertexts differ wildly:
     the trailer cannot depend on the key. It is a GF(2)-linear map of the
     PLAINTEXT.
  3. Drop the heartbeats and what is left is one burst at the head of each of the 21 power-ups. Their
     lengths are [509, 510, 511, 512] -- only 10 of the 21 decode to a full,
     untruncated 512-frame burst; the rest lose 1-3 frames to decode noise.
     The 10 full-length bursts are byte-for-byte identical to each other: a walking-ones memory self-test.
     Its trailers, in capture order, ARE the columns of G. The self-test
     frames carry the SAME type byte and length as the heartbeats, so nothing
     but this structure locates them.
  4. The key-transfer frame is a different frame class. Its plaintext is
     G^-1 * trailer.

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

SLUG = "08-errata"
CH_SCLK, CH_MOSI, CH_CS = 0, 1, 2
CHUNK = 1 << 26


# ------------------------------------------------------------------ decoding
def find_frames(path: pathlib.Path):
    """Yield (start, stop) sample ranges where /CS is asserted."""
    raw = np.memmap(path, dtype=np.uint8, mode="r")
    n = raw.size
    spans, open_at, prev = [], None, 1
    for base in range(0, n, CHUNK):
        blk = np.asarray(raw[base:base + CHUNK])
        cs = (blk >> CH_CS) & 1
        edges = np.nonzero(np.diff(np.concatenate(([prev], cs))))[0]
        for e in edges:
            if cs[e] == 0:
                open_at = base + int(e)
            elif open_at is not None:
                spans.append((open_at, base + int(e)))
                open_at = None
        prev = int(cs[-1]) if cs.size else prev
    return raw, spans


def decode_span(raw, lo, hi, cpol, cpha):
    """9-bit LSB-first words with odd parity, sampled on the selected edge."""
    blk = np.asarray(raw[lo:hi])
    clk = (blk >> CH_SCLK) & 1
    mosi = (blk >> CH_MOSI) & 1
    d = np.diff(clk.astype(np.int8))
    rising = np.nonzero(d == 1)[0] + 1
    falling = np.nonzero(d == -1)[0] + 1
    # CPOL=0: idle low, first edge rising.  CPOL=1: idle high, first edge falling.
    # CPHA=0 samples the first edge of each period, CPHA=1 the second.
    first, second = (rising, falling) if cpol == 0 else (falling, rising)
    edges = first if cpha == 0 else second
    if edges.size < 9:
        return None
    bits = mosi[edges]
    nw = bits.size // 9
    if nw == 0:
        return None
    w = bits[:nw * 9].reshape(nw, 9)
    if not np.all((w.sum(axis=1) & 1) == 1):          # odd parity over 9 bits
        return None
    vals = (w[:, :8] * (1 << np.arange(8))).sum(axis=1).astype(np.uint8)
    return vals


def main() -> int:
    dist = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path(__file__).resolve().parent.parent / "dist")
    t0 = time.time()
    cap = dist / "bus.cap"
    print(f"[00] {cap.stat().st_size:,} samples, no header, 4 channels")
    raw, spans = find_frames(cap)
    print(f"[01] /CS asserted {len(spans)} times ({time.time()-t0:.1f}s)")

    # ---- 2. bus phase, by parity score on a sample of frames --------------
    probe = spans[:40]
    best, score = None, -1
    for cpol in (0, 1):
        for cpha in (0, 1):
            ok = sum(decode_span(raw, lo, hi, cpol, cpha) is not None for lo, hi in probe)
            print(f"[02] CPOL={cpol} CPHA={cpha}: {ok}/{len(probe)} frames pass parity")
            if ok > score:
                best, score = (cpol, cpha), ok
    cpol, cpha = best
    assert score == len(probe), "no bus phase decodes cleanly"
    print(f"[03] bus is CPOL={cpol} CPHA={cpha}, 9-bit LSB-first, odd parity")

    # ---- decode everything -------------------------------------------------
    t = time.time()
    frames = []
    for lo, hi in spans:
        v = decode_span(raw, lo, hi, cpol, cpha)
        if v is not None and v.size >= 3:
            frames.append(v)
    print(f"[04] {len(frames)} frames decoded ({time.time()-t:.1f}s)")

    classes: dict[tuple, list] = {}
    for v in frames:
        classes.setdefault((int(v[0]), int(v[1])), []).append(v)
    for k, g in sorted(classes.items()):
        print(f"[05] frame class type=0x{k[0]:02x} len={k[1]}: {len(g)} frames")

    main_type = max(classes, key=lambda k: len(classes[k]))
    body = classes[main_type]
    L = int(main_type[1])
    ct = np.stack([v[2:2 + L] for v in body])
    tr = np.stack([v[2 + L:2 + 2 * L] for v in body])

    # ---- the key-independence observation ---------------------------------
    uniq_tr, inv, cnt = np.unique(tr, axis=0, return_inverse=True, return_counts=True)
    big = int(np.argmax(cnt))
    same = np.nonzero(inv == big)[0]
    n_ct = np.unique(ct[same], axis=0).shape[0]
    print(f"[06] {same.size} frames share one byte-identical trailer while "
          f"carrying {n_ct} distinct ciphertexts -> the trailer is key-independent")
    assert n_ct > same.size // 2

    # ---- the walking-ones burst -------------------------------------------
    # drop the heartbeats (they all carry that one trailer); what is left is a
    # contiguous 512-frame burst at the head of every power-up
    rest = np.nonzero(inv != big)[0]
    runs, cur = [], [int(rest[0])]
    for a, b in zip(rest, rest[1:]):
        if b == a + 1:
            cur.append(int(b))
        else:
            runs.append(cur)
            cur = [int(b)]
    runs.append(cur)
    lens = sorted({len(r) for r in runs})
    print(f"[07] {len(runs)} contiguous non-heartbeat bursts, lengths {lens}")
    bursts = [r for r in runs if len(r) == 512]
    assert bursts, f"expected 512-frame bursts, found lengths {lens}"
    cand = bursts[0]
    G = np.stack([np.unpackbits(tr[i], bitorder="little") for i in cand], axis=1)
    # every power-up repeats the same self-test, so the column ORDER is not a
    # guess: it is confirmed by every other burst in the capture
    for other_burst in bursts[1:]:
        G2 = np.stack([np.unpackbits(tr[i], bitorder="little") for i in other_burst], axis=1)
        assert np.array_equal(G, G2), "bursts disagree -- not a repeatable self-test"
    print(f"[08] {len(bursts)} bursts, all byte-identical -> walking-ones order "
          f"confirmed; 512x512 GF(2) matrix built")

    # ---- invert G over GF(2) ------------------------------------------------
    t = time.time()
    n = 512
    A = np.concatenate([G.copy(), np.eye(n, dtype=np.uint8)], axis=1)
    r = 0
    for c in range(n):
        nz = np.nonzero(A[r:, c])[0]
        assert nz.size, f"G is singular at column {c} -- wrong burst"
        i = r + int(nz[0])
        if i != r:
            A[[r, i]] = A[[i, r]]
        sel = np.nonzero(A[:, c])[0]
        sel = sel[sel != r]
        A[sel] ^= A[r]
        r += 1
    Ginv = A[:, n:]
    print(f"[09] G is full rank; inverted in {time.time()-t:.2f}s")

    # ---- the key-transfer frame --------------------------------------------
    other = [k for k in classes if k != main_type]
    assert other, "no second frame class"
    kx = classes[other[0]][0]
    Lk = int(other[0][1])
    ktr = np.unpackbits(kx[2 + Lk:2 + 2 * Lk], bitorder="little")
    secret = np.packbits(((Ginv.astype(np.int64) @ ktr.astype(np.int64)) & 1)
                         .astype(np.uint8), bitorder="little").tobytes()
    print(f"[10] key-transfer plaintext = G^-1 * trailer = {secret.hex()[:32]}...")

    gcanon = hashlib.sha256(
        b"".join(np.packbits(G[:, i], bitorder="little").tobytes()
                 for i in range(512))).digest()
    print(f"[10b] share bytes for the meta = {gcanon.hex()}")

    box = (dist / "errata.sealed").read_bytes()
    assert box[:8] == b"nOrgBOX1"
    c = AES.new(hashlib.sha256(secret).digest(), AES.MODE_GCM, nonce=box[8:20])
    c.update(SLUG.encode())
    data = json.loads(c.decrypt_and_verify(box[20:-16], box[-16:]))
    print(f"[11] total {time.time()-t0:.1f}s")
    print(data["flag"])
    assert data["flag"].startswith("Null0rigin{") and data["flag"].endswith("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
